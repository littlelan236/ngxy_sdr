#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
import sys
import time

import numpy as np


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
	sys.path.insert(0, str(CURRENT_DIR))

from pluto_ctrl import pluto_ctrl_rx
from fftfilter import apply_fft_filter
from frame_decoder import frame_decoder
from def_status import dict_to_dataclass
from quadrate_discriminator import QuadratureDiscriminator, QuadratureDiscriminatorConfig
from symbol_sync import MMSymbolSynchronizer, MMSymbolSyncConfig, bpsk_bits_from_symbols
from def_taps import TAPS_LPF_PRE, TAPS_LPF

try:
	from wireless_ros2_adaptor import WirelessRos2AdaptorNodeThreaded
except Exception:
	WirelessRos2AdaptorNodeThreaded = None


SAMPLE_RATE = 1_000_000
CENTER_FREQ = 433_200_000
NUM_SAMPS = 32768
RX_GAIN = 70.0
AGC_MODE = "slow_attack"

SYMBOLS_PER_SAMPLE = 52.0
DISCRIMINATOR_GAIN = 1.0


def _json_default(value):
	if isinstance(value, Enum):
		return value.value
	if isinstance(value, (bytes, bytearray)):
		return list(value)
	return str(value)


def _build_ros_publisher_callback(ros_node):
	def _on_frame_decoded(data_dict_list: list[dict]):
		for data_dict in data_dict_list:
			status_obj = dict_to_dataclass(data_dict)
			if status_obj is None:
				continue

			msg_dict = {
				"type": type(status_obj).__name__,
				"data": status_obj,
			}
			json_str = json.dumps(msg_dict, default=_json_default, ensure_ascii=False)
			ros_node.publish_wireless_result(json_str)

	return _on_frame_decoded


def _to_1d_array(samples: np.ndarray | list | tuple) -> np.ndarray:
	array = np.asarray(samples)
	if array.ndim == 0:
		return array.reshape(1)
	if array.ndim != 1:
		return array.reshape(-1)
	return array


def process_chunk(
	samples: np.ndarray,
	pre_taps: np.ndarray,
	post_taps: np.ndarray,
	discriminator: QuadratureDiscriminator,
	symbol_sync: MMSymbolSynchronizer,
) -> np.ndarray:
	"""处理单个采样块并返回最终 bits。"""

	complex_samples = _to_1d_array(samples).astype(np.complex128, copy=False)
	filtered_iq = apply_fft_filter(complex_samples, pre_taps)
	demodulated = discriminator.process(filtered_iq)
	filtered_audio = apply_fft_filter(demodulated, post_taps)
	synced_symbols = symbol_sync.process(filtered_audio)
	return bpsk_bits_from_symbols(synced_symbols)


def main() -> None:
	ros_node = None
	if WirelessRos2AdaptorNodeThreaded is not None:
		try:
			ros_node = WirelessRos2AdaptorNodeThreaded()
			ros_node.start()
			print("ROS2 wireless adaptor started")
		except Exception as exc:
			ros_node = None
			print(f"ROS2 adaptor unavailable: {exc}")

	rx_ctrl = pluto_ctrl_rx(
		sample_rate=SAMPLE_RATE,
		center_freq=CENTER_FREQ,
		num_samps=NUM_SAMPS,
		rx_hardwaregain_chan0=RX_GAIN,
		agc_mode=AGC_MODE,
	)

	discriminator = QuadratureDiscriminator(
		QuadratureDiscriminatorConfig(gain=DISCRIMINATOR_GAIN)
	)
	symbol_sync = MMSymbolSynchronizer(
		MMSymbolSyncConfig(omega=SYMBOLS_PER_SAMPLE)
	)
	decoder = frame_decoder(
		type="signal",
		bits_source="direct",
		on_frame_decoded=_build_ros_publisher_callback(ros_node) if ros_node else None,
	)

	print("main_rx started, press Ctrl+C to stop.")

	try:
		while True:
			samples = rx_ctrl.rx()
			if samples is None:
				time.sleep(0.01)
				continue

			bits = process_chunk(
				samples=samples,
				pre_taps=TAPS_LPF_PRE,
				post_taps=TAPS_LPF,
				discriminator=discriminator,
				symbol_sync=symbol_sync,
			)

			if bits.size == 0:
				continue

			decoded_frames = decoder.push_bits(bits)
			if decoded_frames:
				print(f"frames({len(decoded_frames)}): {decoded_frames}")
	finally:
		if ros_node is not None:
			ros_node.stop()


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("stopped")
