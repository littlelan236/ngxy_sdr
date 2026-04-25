"""Direct-mode decoder optimized for bursty, large bit chunks.

This decoder is designed for pipelines where push_bits is called infrequently
(e.g. every ~1s) but each call carries a large number of bits (1e4~1e5+).

Key differences from the legacy decoder:
- No ZMQ worker thread.
- Bit buffer keeps only a short carry window required for cross-chunk OTA sync.
- OTA payload extraction is done per incoming chunk (+carry), then payload bytes
  are appended to a serial-byte parser buffer.
- Serial parser keeps only incomplete tail, avoiding repeated rescans.
"""

from __future__ import annotations

import logging
from typing import Iterable

import numpy as np

from crc import verify_crc16_check_sum, verify_crc8_check_sum
from def_frame import (
    ACCESS_CODE_JAMMING,
    ACCESS_CODE_SIGNAL,
    ACCESS_CORR_JAMMING,
    ACCESS_CORR_SIGNAL,
    CMD_OPTIONS,
    ENDIAN,
    ENDIAN_DATA,
    ENDIAN_OTA,
    LEN_ACCESS,
    LEN_CMD_ID,
    LEN_DATA_LENGTH,
    LEN_HEADER,
    LEN_OTA_LENGTH,
    LEN_OTA_PAYLOAD,
    LEN_SEQ,
    LEN_SOF,
    SERIAL_FIELDS,
    SOF,
)
from util import _reverse_string


_ACCESS_BITS_SIGNAL = np.unpackbits(
    np.frombuffer(ACCESS_CODE_SIGNAL.to_bytes(8, ENDIAN_OTA), dtype=np.uint8)
)
_ACCESS_BITS_JAMMING = np.unpackbits(
    np.frombuffer(ACCESS_CODE_JAMMING.to_bytes(8, ENDIAN_OTA), dtype=np.uint8)
)


class frame_decoder_direct:
    """Frame decoder tailored for large, sparse direct bit input."""

    def __init__(
        self,
        type: str = "signal",
        crc8_enabled: bool = True,
        crc16_enabled: bool = True,
        on_frame_decoded=None,
        payload_tail_limit: int = 4096,
    ):
        if type not in ("signal", "jamming"):
            raise ValueError(f"Unsupported type: {type}")

        self._type = type
        self._crc8_enabled = bool(crc8_enabled)
        self._crc16_enabled = bool(crc16_enabled)
        self._on_frame_decoded = on_frame_decoded
        self._payload_tail_limit = int(payload_tail_limit)

        if self._type == "signal":
            self._access_bits = _ACCESS_BITS_SIGNAL
            self._access_corr = ACCESS_CORR_SIGNAL
        else:
            self._access_bits = _ACCESS_BITS_JAMMING
            self._access_corr = ACCESS_CORR_JAMMING

        self._payload_start_bits = (LEN_ACCESS + LEN_OTA_LENGTH * 2) * 8
        self._payload_bits = LEN_OTA_PAYLOAD * 8

        # Carry enough bits so a frame split across chunk boundary can be recovered.
        self._bit_carry_len = self._payload_start_bits + self._payload_bits - 1
        self._bit_carry = np.array([], dtype=np.uint8)

        # Payload byte stream carry for serial frame parser.
        self._payload_buffer = bytearray()

    @staticmethod
    def _normalize_bits(bits: np.ndarray | Iterable[int]) -> np.ndarray:
        arr = np.asarray(bits, dtype=np.uint8).reshape(-1)
        if arr.size == 0:
            return arr
        # Ensure strict bit values 0/1.
        return np.bitwise_and(arr, 1)

    def _extract_ota_payloads(self, bits_stream: np.ndarray) -> list[bytes]:
        if bits_stream.size < self._access_bits.size:
            return []

        corr = np.correlate(bits_stream, self._access_bits, mode="valid")
        starts = np.flatnonzero(corr == self._access_corr)
        if starts.size == 0:
            return []

        payloads: list[bytes] = []
        for idx in starts:
            p0 = int(idx) + self._payload_start_bits
            p1 = p0 + self._payload_bits
            if p1 > bits_stream.size:
                continue
            payload_bytes = np.packbits(bits_stream[p0:p1]).tobytes()
            if len(payload_bytes) == LEN_OTA_PAYLOAD:
                payloads.append(payload_bytes)
        return payloads
    
    def _decode_frame_serial(self, frame_serial: bytes) -> dict | None:
        if self._crc16_enabled and not verify_crc16_check_sum(frame_serial, ENDIAN):
            logging.log(logging.DEBUG, "[frame_decoder_direct] crc16 verify failed")
            return None

        data_length = int.from_bytes(
            frame_serial[LEN_SOF:LEN_SOF + LEN_DATA_LENGTH], ENDIAN
        )
        logging.log(logging.DEBUG, f"[frame_decoder_direct] decoded frame with data_length: {data_length}")
        bias_cmd_id = LEN_HEADER
        cmd_id = int.from_bytes(frame_serial[bias_cmd_id:bias_cmd_id + LEN_CMD_ID], ENDIAN)

        cmd_name = None
        for key, value in CMD_OPTIONS.items():
            if cmd_id == value[0]:
                cmd_name = key
                break
        if cmd_name is None:
            logging.log(logging.INFO, "[frame_decoder_direct] cmd name not found")
            return None

        bias_data = LEN_HEADER + LEN_CMD_ID
        data = frame_serial[bias_data:bias_data + data_length]
        fields = SERIAL_FIELDS[cmd_name]
        logging.log(logging.DEBUG, f"[frame_decoder_direct] parsing cmd: {cmd_name} with fields: {fields}")

        data_dict = {}
        offset = 0
        for name, length in fields:
            raw = data[offset:offset + length]
            if len(raw) != length:
                logging.log(
                    logging.WARNING,
                    f"[frame_decoder_direct] field length mismatch: {name} expect {length} got {len(raw)}",
                )
                return None

            if name == "key":
                try:
                    value = raw.decode("ascii", errors="ignore")
                except Exception:
                    value = str(raw)
                if ENDIAN_DATA == "little":
                    value = _reverse_string(value)
            elif name == "macro_bits":
                value = bytes(raw)
            else:
                value = int.from_bytes(raw, ENDIAN_DATA)

            data_dict[name] = value
            offset += length

        return data_dict

    def _scan_serial_frames(self) -> list[dict]:
        if len(self._payload_buffer) == 0:
            return []

        payload = bytes(self._payload_buffer)
        out: list[dict] = []
        cursor = 0

        while cursor < len(payload):
            sof_idx = payload.find(bytes([SOF]), cursor)
            if sof_idx < 0:
                break

            if len(payload) - sof_idx < LEN_HEADER:
                break

            data_length = int.from_bytes(
                payload[sof_idx + LEN_SOF:sof_idx + LEN_SOF + LEN_DATA_LENGTH], ENDIAN
            )
            frame_length = LEN_HEADER + LEN_CMD_ID + data_length + 2
            if frame_length < LEN_HEADER + LEN_CMD_ID + 2:
                cursor = sof_idx + 1
                continue

            if len(payload) - sof_idx < frame_length:
                break

            frame = payload[sof_idx:sof_idx + frame_length]
            logging.log(logging.DEBUG, f"[frame_decoder_direct] found frame candidate at idx {sof_idx} with length {frame_length}")
            if self._crc8_enabled and not verify_crc8_check_sum(frame[:LEN_HEADER]):
                cursor = sof_idx + 1
                logging.log(logging.DEBUG, f"[frame_decoder_direct] crc8 verify failed")
                continue

            decoded = self._decode_frame_serial(frame)
            if decoded is not None:
                out.append(decoded)
            cursor = sof_idx + frame_length

        # Keep only unconsumed tail for next push.
        self._payload_buffer = bytearray(payload[cursor:])
        if len(self._payload_buffer) > self._payload_tail_limit:
            self._payload_buffer = self._payload_buffer[-self._payload_tail_limit:]

        return out

    def push_bits(self, bits: np.ndarray | list | tuple) -> list[dict]:
        """Push one large direct bit chunk and decode available frames immediately."""

        chunk = self._normalize_bits(bits)
        if chunk.size == 0:
            return []
        logging.log(logging.DEBUG, f"[frame_decoder_direct] input bits chunk size: {chunk.size}")

        if self._bit_carry.size == 0:
            stream = chunk
        else:
            stream = np.concatenate([self._bit_carry, chunk])
            logging.log(logging.DEBUG, f"[frame_decoder_direct] concat stream size: {stream.size}")

        payloads = self._extract_ota_payloads(stream)
        for p in payloads:
            self._payload_buffer.extend(p)
        if len(payloads) > 0:
            logging.log(logging.DEBUG, f"[frame_decoder_direct] extracted {len(payloads)} OTA payloads")
        else:
            logging.log(logging.DEBUG, f"[frame_decoder_direct] no OTA payload extracted")
        
        logging.log(logging.DEBUG, f"[frame_decoder_direct] payload buffer size: {len(self._payload_buffer)}")

        # Update bit carry for cross-chunk frame recovery.
        if stream.size > self._bit_carry_len:
            self._bit_carry = stream[-self._bit_carry_len:].copy()
        else:
            self._bit_carry = stream.copy()
        logging.log(logging.DEBUG, f"[frame_decoder_direct] updated bit carry size: {self._bit_carry.size}")

        decoded = self._scan_serial_frames()
        logging.log(logging.DEBUG, f"[frame_decoder_direct] decoded frames count: {len(decoded)}")
        if decoded and self._on_frame_decoded:
            try:
                self._on_frame_decoded(decoded)
            except Exception as exc:
                logging.log(logging.WARNING, f"[frame_decoder_direct] callback error: {exc}")

        return decoded
