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
    def __init__(
        self,
        type: str = "signal",
        crc8_enabled: bool = True,
        crc16_enabled: bool = True,
        on_frame_decoded=None,
        payload_tail_limit: int = 50,
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

    def _extract_ota_payloads(self, bits_stream: np.ndarray) -> tuple[list[bytes], int]:
        if bits_stream.size < self._access_bits.size:
            return [], 0

        corr = np.correlate(bits_stream, self._access_bits, mode="valid")
        starts = np.flatnonzero(corr == self._access_corr)
        if starts.size == 0:
            return [], 0

        # 使用consume逻辑，返回完整payload列表和最后消费位置，避免重复处理重叠的帧头
        payloads: list[bytes] = []
        last_consumed_end = 0
        earliest_incomplete_start: int | None = None
        for idx in starts:
            p0 = int(idx) + self._payload_start_bits
            p1 = p0 + self._payload_bits
            if p1 > bits_stream.size:
                if earliest_incomplete_start is None or int(idx) < earliest_incomplete_start:
                    earliest_incomplete_start = int(idx)
                continue
            payload_bytes = np.packbits(bits_stream[p0:p1]).tobytes()
            if len(payload_bytes) == LEN_OTA_PAYLOAD:
                payloads.append(payload_bytes)
                if p1 > last_consumed_end:
                    last_consumed_end = p1

        if earliest_incomplete_start is not None:
            carry_start = max(last_consumed_end, earliest_incomplete_start)
        else:
            carry_start = last_consumed_end

        return payloads, carry_start
    
    def _decode_frame_serial(self, frame_serial: bytes) -> dict | None:
        if self._crc16_enabled and not verify_crc16_check_sum(frame_serial, ENDIAN):
            logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] crc16 verify failed")
            return None

        data_length = int.from_bytes(
            frame_serial[LEN_SOF:LEN_SOF + LEN_DATA_LENGTH], ENDIAN
        )
        logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] decoded frame with data_length: {data_length}")
        bias_cmd_id = LEN_HEADER
        cmd_id = int.from_bytes(frame_serial[bias_cmd_id:bias_cmd_id + LEN_CMD_ID], ENDIAN)

        cmd_name = None
        for key, value in CMD_OPTIONS.items():
            if cmd_id == value[0]:
                cmd_name = key
                break
        if cmd_name is None:
            logging.log(logging.INFO, f"[frame_decoder_direct][{self._type}] cmd name not found")
            return None

        bias_data = LEN_HEADER + LEN_CMD_ID
        data = frame_serial[bias_data:bias_data + data_length]
        fields = SERIAL_FIELDS[cmd_name]
        logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] parsing cmd: {cmd_name}")

        data_dict = {}
        offset = 0
        for name, length in fields:
            raw = data[offset:offset + length]
            if len(raw) != length:
                logging.log(
                    logging.WARNING,
                    f"[frame_decoder_direct][{self._type}] field length mismatch: {name} expect {length} got {len(raw)}",
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
        logging.info(f"[frame_decoder_direct][{self._type}] DECODE SERIAL:payload buffer of size {len(self._payload_buffer)}")

        payload = bytes(self._payload_buffer)
        out: list[dict] = []
        cursor = 0

        while cursor < len(payload):
            sof_idx = payload.find(bytes([SOF]), cursor)
            logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] searching for SOF from idx {cursor}, found at {sof_idx}")
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
            logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] found frame candidate at idx {sof_idx} with length {frame_length}")
            if self._crc8_enabled and not verify_crc8_check_sum(frame[:LEN_HEADER]):
                cursor = sof_idx + 1
                logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] crc8 verify failed")
                continue

            decoded = self._decode_frame_serial(frame)
            if decoded is not None:
                out.append(decoded)
            cursor = sof_idx + frame_length

        # Keep only unconsumed tail for next push.
        self._payload_buffer = bytearray(payload[cursor:])
        if len(self._payload_buffer) > self._payload_tail_limit:
            self._payload_buffer = self._payload_buffer[-self._payload_tail_limit:]
        logging.debug(f"[frame_decoder_direct][{self._type}] cut payload buffer size: {len(self._payload_buffer)}")

        return out

    def push_bits(self, bits: np.ndarray | list | tuple) -> list[dict]:
        """外部调用接口 将输入的比特流进行空口帧识别、串口帧识别 返回解析出的信息（字典格式）"""

        chunk = self._normalize_bits(bits)
        if chunk.size == 0:
            return []
        logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] input bits chunk size: {chunk.size}")

        if self._bit_carry.size == 0:
            stream = chunk
        else:
            stream = np.concatenate([self._bit_carry, chunk])
            logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] concat stream size: {stream.size}")

        payloads, carry_start = self._extract_ota_payloads(stream)
        for p in payloads:
            self._payload_buffer.extend(p)
        if len(payloads) > 0:
            logging.log(logging.INFO, f"[frame_decoder_direct][{self._type}] extracted {len(payloads)} OTA payloads")
        else:
            logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] no OTA payload extracted")
        
        logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] payload buffer size: {len(self._payload_buffer)}")

        # 仅保留未完成/未识别出的尾部 bits，避免重复保存已消费的内容
        if carry_start >= stream.size:
            self._bit_carry = np.array([], dtype=np.uint8)
        else:
            self._bit_carry = stream[carry_start:].copy()

        if self._bit_carry.size > self._bit_carry_len:
            self._bit_carry = self._bit_carry[-self._bit_carry_len:].copy()
        logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] updated bit carry size: {self._bit_carry.size}")

        decoded = self._scan_serial_frames()
        if len(decoded) > 0:
            logging.log(logging.INFO, f"[frame_decoder_direct][{self._type}] decoded frames count: {len(decoded)}")
        else:
            logging.log(logging.DEBUG, f"[frame_decoder_direct][{self._type}] decoded frames count 0")
        if decoded and self._on_frame_decoded:
            try:
                self._on_frame_decoded(decoded)
            except Exception as exc:
                logging.log(logging.WARNING, f"[frame_decoder_direct][{self._type}] callback error: {exc}")

        return decoded
