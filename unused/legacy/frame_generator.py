"""Frame generator for the serial protocol shown in the spec image.

Frame layout:
- frame_header (5 bytes): SOF(1) + data_length(2) + seq(1) + CRC8(1)
- cmd_id (2 bytes)
- data (n bytes)
- frame_tail (2 bytes): CRC16 of the whole frame except these 2 bytes
"""

from __future__ import annotations

import random
from typing import Iterable

try:
	from .crc import append_crc8_check_sum, append_crc16_check_sum, verify_crc8_check_sum, verify_crc16_check_sum
except ImportError:
	from crc import append_crc8_check_sum, append_crc16_check_sum, verify_crc8_check_sum, verify_crc16_check_sum


SOF_DEFAULT = 0xA5
SIM_CMD_ID = 0x0A06
SIM_DATA_FIXED = bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60])
CMD_ID_POSITIONS = 0x0A01
CMD_ID_POSITIONS_FIELD_COUNT = 12
CMD_ID_HP = 0x0A02
CMD_ID_AMMO = 0x0A03
CMD_ID_RESOURCE = 0x0A04

CMD_ID_HP_FIELD_COUNT = 6
CMD_ID_AMMO_FIELD_COUNT = 5


def _to_bytes(data: bytes | bytearray | Iterable[int]) -> bytes:
	if isinstance(data, (bytes, bytearray)):
		return bytes(data)
	return bytes((value & 0xFF) for value in data)


def generate_frame(
	cmd_id: int,
	data: bytes | bytearray | Iterable[int],
	seq: int,
	sof: int = SOF_DEFAULT,
) -> bytes:
	"""Generate a complete protocol frame.

	`data_length` is the length of `data` only, consistent with the spec table.
	All multi-byte fields are encoded big-endian.
	"""
	if not 0 <= sof <= 0xFF:
		raise ValueError("sof must be in range 0..255")
	if not 0 <= seq <= 0xFF:
		raise ValueError("seq must be in range 0..255")
	if not 0 <= cmd_id <= 0xFFFF:
		raise ValueError("cmd_id must be in range 0..65535")

	payload = _to_bytes(data)
	data_length = len(payload)
	if data_length > 0xFFFF:
		raise ValueError("data too long, max 65535 bytes")

	# Build 5-byte header: SOF + data_length(2) + seq + CRC8.
	header_without_crc8 = bytes([sof]) + data_length.to_bytes(2, "big") + bytes([seq])
	header = append_crc8_check_sum(header_without_crc8 + b"\x00")

	# Build frame and append CRC16 at the tail (high byte first, then low byte).
	frame_without_crc16 = header + cmd_id.to_bytes(2, "big") + payload
	frame = append_crc16_check_sum(frame_without_crc16 + b"\x00\x00")
	return frame


def bytes_to_hex(data: bytes) -> str:
	"""Format bytes as uppercase hex string with spaces."""
	return " ".join(f"{byte:02X}" for byte in data)


def bytes_to_bits(data: bytes | bytearray | Iterable[int]) -> list[int]:
	"""Convert byte stream to bit list (MSB first per byte)."""
	payload = _to_bytes(data)
	bits: list[int] = []
	for byte in payload:
		for shift in range(7, -1, -1):
			bits.append((byte >> shift) & 0x01)
	return bits


def bits_to_string(bits: Iterable[int]) -> str:
	"""Format bit list as a compact '0101...' string."""
	return "".join("1" if int(bit) else "0" for bit in bits)


def generate_repeated_frame_stream(
	frame_count: int,
	start_seq: int = 0,
	data_value: bytes | bytearray | Iterable[int] = SIM_DATA_FIXED,
	cmd_id: int = SIM_CMD_ID,
) -> bytes:
	"""Generate continuous stream by repeating one frame pattern.

	Rules requested:
	- cmd_id fixed to 0x0A06 by default
	- seq increments for each frame
	- data is a fixed 6-byte value
	"""
	if frame_count <= 0:
		return b""

	payload = _to_bytes(data_value)
	if len(payload) != 6:
		raise ValueError("data_value must be exactly 6 bytes")

	stream = bytearray()
	for index in range(frame_count):
		seq = (start_seq + index) & 0xFF
		stream.extend(generate_frame(cmd_id=cmd_id, data=payload, seq=seq))
	return bytes(stream)


def generate_repeated_frame_bitstream(
	frame_count: int,
	start_seq: int = 0,
	data_value: bytes | bytearray | Iterable[int] = SIM_DATA_FIXED,
	cmd_id: int = SIM_CMD_ID,
) -> list[int]:
	"""Generate repeated frames and return as continuous bit stream."""
	stream = generate_repeated_frame_stream(
		frame_count=frame_count,
		start_seq=start_seq,
		data_value=data_value,
		cmd_id=cmd_id,
	)
	return bytes_to_bits(stream)


def _generate_cmd_0a01_random_data(
	rng: random.Random,
	field_count: int = CMD_ID_POSITIONS_FIELD_COUNT,
	value_min: int = -300,
	value_max: int = 300,
) -> bytes:
	"""Build cmd=0x0A01 data payload: 12 fields, each 2-byte signed big-endian."""
	if field_count <= 0:
		return b""
	if value_min > value_max:
		raise ValueError("value_min must be <= value_max")

	# Clamp into int16 range to ensure 2-byte signed encoding is valid.
	low = max(-32768, value_min)
	high = min(32767, value_max)
	if low > high:
		raise ValueError("value range is outside int16")

	payload = bytearray()
	for _ in range(field_count):
		value = rng.randint(low, high)
		payload.extend(int(value).to_bytes(2, byteorder="big", signed=True))
	return bytes(payload)


def _generate_uint16_fields(
	rng: random.Random,
	field_count: int,
	value_min: int,
	value_max: int,
) -> bytes:
	if field_count <= 0:
		return b""
	if value_min > value_max:
		raise ValueError("value_min must be <= value_max")

	low = max(0, value_min)
	high = min(0xFFFF, value_max)
	if low > high:
		raise ValueError("value range is outside uint16")

	payload = bytearray()
	for _ in range(field_count):
		payload.extend(int(rng.randint(low, high)).to_bytes(2, byteorder="big", signed=False))
	return bytes(payload)


def _generate_cmd_0a02_random_data(
	rng: random.Random,
	value_min: int = 0,
	value_max: int = 500,
) -> bytes:
	"""Build cmd=0x0A02 payload: 6 fields, each 2-byte unsigned big-endian."""
	return _generate_uint16_fields(
		rng=rng,
		field_count=CMD_ID_HP_FIELD_COUNT,
		value_min=value_min,
		value_max=value_max,
	)


def _generate_cmd_0a03_random_data(
	rng: random.Random,
	value_min: int = 0,
	value_max: int = 100,
) -> bytes:
	"""Build cmd=0x0A03 payload: 5 fields, each 2-byte unsigned big-endian."""
	return _generate_uint16_fields(
		rng=rng,
		field_count=CMD_ID_AMMO_FIELD_COUNT,
		value_min=value_min,
		value_max=value_max,
	)


def _generate_cmd_0a04_random_data(
	rng: random.Random,
	remaining_coins_max: int = 500,
	total_coins_max: int = 1000,
) -> bytes:
	"""Build cmd=0x0A04 payload: 2-byte remain + 2-byte total + 4-byte status mask.

	Status mask uses the low 16 bits according to the spec picture.
	"""
	remain = rng.randint(0, max(0, min(0xFFFF, remaining_coins_max)))
	total = rng.randint(remain, max(remain, min(0xFFFF, total_coins_max)))

	status = 0
	status |= rng.randint(0, 1) << 0   # bit0
	status |= rng.randint(0, 2) << 1   # bit1-2
	status |= rng.randint(0, 1) << 3   # bit3
	status |= rng.randint(0, 2) << 4   # bit4-5
	status |= rng.randint(0, 2) << 6   # bit6-7
	status |= rng.randint(0, 1) << 8   # bit8
	status |= rng.randint(0, 1) << 9   # bit9
	status |= rng.randint(0, 1) << 10  # bit10
	status |= rng.randint(0, 1) << 11  # bit11
	status |= rng.randint(0, 1) << 12  # bit12
	status |= rng.randint(0, 1) << 13  # bit13
	status |= rng.randint(0, 1) << 14  # bit14
	status |= rng.randint(0, 1) << 15  # bit15

	return (
		remain.to_bytes(2, byteorder="big", signed=False)
		+ total.to_bytes(2, byteorder="big", signed=False)
		+ status.to_bytes(4, byteorder="big", signed=False)
	)


def generate_random_cmd0a01_frame_stream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	value_min: int = -300,
	value_max: int = 300,
) -> bytes:
	"""Generate continuous stream of cmd=0x0A01 frames with random data per frame.

	Data format follows the table in the image:
	- 12 fields
	- each field uses 2 bytes
	- total payload length = 24 bytes
	"""
	if frame_count <= 0:
		return b""

	rng = random.Random(seed)
	stream = bytearray()
	for index in range(frame_count):
		seq = (start_seq + index) & 0xFF
		payload = _generate_cmd_0a01_random_data(
			rng=rng,
			field_count=CMD_ID_POSITIONS_FIELD_COUNT,
			value_min=value_min,
			value_max=value_max,
		)
		stream.extend(generate_frame(cmd_id=CMD_ID_POSITIONS, data=payload, seq=seq))
	return bytes(stream)


def generate_random_cmd0a01_bitstream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	value_min: int = -300,
	value_max: int = 300,
) -> list[int]:
	"""Generate continuous bitstream of cmd=0x0A01 frames with random payload."""
	stream = generate_random_cmd0a01_frame_stream(
		frame_count=frame_count,
		start_seq=start_seq,
		seed=seed,
		value_min=value_min,
		value_max=value_max,
	)
	return bytes_to_bits(stream)


def generate_random_cmd0a02_frame_stream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	value_min: int = 0,
	value_max: int = 500,
) -> bytes:
	"""Generate cmd=0x0A02 stream with random per-frame HP-style fields."""
	if frame_count <= 0:
		return b""

	rng = random.Random(seed)
	stream = bytearray()
	for index in range(frame_count):
		seq = (start_seq + index) & 0xFF
		payload = _generate_cmd_0a02_random_data(rng=rng, value_min=value_min, value_max=value_max)
		stream.extend(generate_frame(cmd_id=CMD_ID_HP, data=payload, seq=seq))
	return bytes(stream)


def generate_random_cmd0a02_bitstream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	value_min: int = 0,
	value_max: int = 500,
) -> list[int]:
	"""Generate continuous bitstream of cmd=0x0A02 frames."""
	stream = generate_random_cmd0a02_frame_stream(
		frame_count=frame_count,
		start_seq=start_seq,
		seed=seed,
		value_min=value_min,
		value_max=value_max,
	)
	return bytes_to_bits(stream)


def generate_random_cmd0a03_frame_stream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	value_min: int = 0,
	value_max: int = 100,
) -> bytes:
	"""Generate cmd=0x0A03 stream with random per-frame ammo-style fields."""
	if frame_count <= 0:
		return b""

	rng = random.Random(seed)
	stream = bytearray()
	for index in range(frame_count):
		seq = (start_seq + index) & 0xFF
		payload = _generate_cmd_0a03_random_data(rng=rng, value_min=value_min, value_max=value_max)
		stream.extend(generate_frame(cmd_id=CMD_ID_AMMO, data=payload, seq=seq))
	return bytes(stream)


def generate_random_cmd0a03_bitstream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	value_min: int = 0,
	value_max: int = 100,
) -> list[int]:
	"""Generate continuous bitstream of cmd=0x0A03 frames."""
	stream = generate_random_cmd0a03_frame_stream(
		frame_count=frame_count,
		start_seq=start_seq,
		seed=seed,
		value_min=value_min,
		value_max=value_max,
	)
	return bytes_to_bits(stream)


def generate_random_cmd0a04_frame_stream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	remaining_coins_max: int = 500,
	total_coins_max: int = 1000,
) -> bytes:
	"""Generate cmd=0x0A04 stream with random per-frame resource status fields."""
	if frame_count <= 0:
		return b""

	rng = random.Random(seed)
	stream = bytearray()
	for index in range(frame_count):
		seq = (start_seq + index) & 0xFF
		payload = _generate_cmd_0a04_random_data(
			rng=rng,
			remaining_coins_max=remaining_coins_max,
			total_coins_max=total_coins_max,
		)
		stream.extend(generate_frame(cmd_id=CMD_ID_RESOURCE, data=payload, seq=seq))
	return bytes(stream)


def generate_random_cmd0a04_bitstream(
	frame_count: int,
	start_seq: int = 0,
	seed: int | None = None,
	remaining_coins_max: int = 500,
	total_coins_max: int = 1000,
) -> list[int]:
	"""Generate continuous bitstream of cmd=0x0A04 frames."""
	stream = generate_random_cmd0a04_frame_stream(
		frame_count=frame_count,
		start_seq=start_seq,
		seed=seed,
		remaining_coins_max=remaining_coins_max,
		total_coins_max=total_coins_max,
	)
	return bytes_to_bits(stream)


def generate_looped_examples_stream(
	cycle_count: int,
	start_seq: int = 0,
	seed: int | None = None,
) -> bytes:
	"""Generate one long byte stream by looping frame types from example2 to example6.

	Per cycle, append frames in this order:
	1) example3: cmd 0x0A01 random positions frame
	2) example4: cmd 0x0A02 random hp frame
	3) example5: cmd 0x0A03 random ammo frame
	4) example6: cmd 0x0A04 random resource frame
	"""
	if cycle_count <= 0:
		return b""

	rng = random.Random(seed)
	seq = start_seq & 0xFF
	stream = bytearray()

	for _ in range(cycle_count):
		stream.extend(generate_frame(cmd_id=CMD_ID_POSITIONS, data=_generate_cmd_0a01_random_data(rng), seq=seq))
		seq = (seq + 1) & 0xFF

		stream.extend(generate_frame(cmd_id=CMD_ID_HP, data=_generate_cmd_0a02_random_data(rng), seq=seq))
		seq = (seq + 1) & 0xFF

		stream.extend(generate_frame(cmd_id=CMD_ID_AMMO, data=_generate_cmd_0a03_random_data(rng), seq=seq))
		seq = (seq + 1) & 0xFF

		stream.extend(generate_frame(cmd_id=CMD_ID_RESOURCE, data=_generate_cmd_0a04_random_data(rng), seq=seq))
		seq = (seq + 1) & 0xFF

	return bytes(stream)


def generate_looped_examples_bitstream(
	cycle_count: int,
	start_seq: int = 0,
	seed: int | None = None,
) -> list[int]:
	"""Generate one long bitstream by looping frame types from example2 to example6."""
	stream = generate_looped_examples_stream(
		cycle_count=cycle_count,
		start_seq=start_seq,
		seed=seed,
	)
	return bytes_to_bits(stream)


if __name__ == "__main__":
	# Example 1: generate one complete frame.
	one_frame = generate_frame(cmd_id=SIM_CMD_ID, data=SIM_DATA_FIXED, seq=1)
	print("Generated one frame:")
	print(bytes_to_hex(one_frame))
	print(f"Length: {len(one_frame)} bytes")
	print(f"Header CRC8 valid: {verify_crc8_check_sum(one_frame[:5])}")
	print(f"Frame CRC16 valid: {verify_crc16_check_sum(one_frame)}")

	# Example 2: generate repeated continuous stream.
	stream = generate_repeated_frame_stream(frame_count=3, start_seq=1)
	bitstream = generate_repeated_frame_bitstream(frame_count=3, start_seq=1)
	print("\nRepeated stream (3 frames):")
	print(bytes_to_hex(stream))
	print(f"Byte length: {len(stream)}")
	print(f"Bit length: {len(bitstream)}")
	print(f"First 64 bits: {bits_to_string(bitstream[:64])}")

	# Example 3: cmd=0x0A01 with random 24-byte payload per frame.
	random_stream = generate_random_cmd0a01_frame_stream(frame_count=2, start_seq=1, seed=20260312)
	random_bitstream = generate_random_cmd0a01_bitstream(frame_count=2, start_seq=1, seed=20260312)
	print("\nRandom cmd=0x0A01 stream (2 frames):")
	print(bytes_to_hex(random_stream))
	print(f"Byte length: {len(random_stream)}")
	print(f"Bit length: {len(random_bitstream)}")
	print(f"First 64 bits: {bits_to_string(random_bitstream[:64])}")

	# Example 4: random cmd=0x0A02 stream/bitstream.
	random_0a02_stream = generate_random_cmd0a02_frame_stream(frame_count=2, start_seq=20, seed=20260312)
	random_0a02_bits = generate_random_cmd0a02_bitstream(frame_count=2, start_seq=20, seed=20260312)
	print("\nRandom cmd=0x0A02 stream (2 frames):")
	print(bytes_to_hex(random_0a02_stream))
	print(f"Bit length: {len(random_0a02_bits)}")

	# Example 5: random cmd=0x0A03 stream/bitstream.
	random_0a03_stream = generate_random_cmd0a03_frame_stream(frame_count=2, start_seq=30, seed=20260312)
	random_0a03_bits = generate_random_cmd0a03_bitstream(frame_count=2, start_seq=30, seed=20260312)
	print("\nRandom cmd=0x0A03 stream (2 frames):")
	print(bytes_to_hex(random_0a03_stream))
	print(f"Bit length: {len(random_0a03_bits)}")

	# Example 6: random cmd=0x0A04 stream/bitstream.
	random_0a04_stream = generate_random_cmd0a04_frame_stream(frame_count=2, start_seq=40, seed=20260312)
	random_0a04_bits = generate_random_cmd0a04_bitstream(frame_count=2, start_seq=40, seed=20260312)
	print("\nRandom cmd=0x0A04 stream (2 frames):")
	print(bytes_to_hex(random_0a04_stream))
	print(f"Bit length: {len(random_0a04_bits)}")

	# Example 7: one long stream by looping example2~example6.
	looped_stream = generate_looped_examples_stream(cycle_count=3, start_seq=50, seed=20260312)
	looped_bits = generate_looped_examples_bitstream(cycle_count=3, start_seq=50, seed=20260312)
	print("\nLooped example2~6 stream (3 cycles):")
	print(bytes_to_hex(looped_stream))
	print(f"Byte length: {len(looped_stream)}")
	print(f"Bit length: {len(looped_bits)}")
	print(f"First 64 bits: {bits_to_string(looped_bits[:64])}")

