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
from frame_decoder_direct import frame_decoder_direct
from def_status import dict_to_dataclass
from quadrate_discriminator import QuadratureDiscriminator, QuadratureDiscriminatorConfig
from symbol_sync import MMSymbolSynchronizer, MMSymbolSyncConfig, bpsk_bits_from_symbols
from def_taps import TAPS_LPF_PRE, TAPS_LPF

try:
	from wireless_ros2_adaptor import WirelessRos2AdaptorNodeThreaded
except Exception:
	WirelessRos2AdaptorNodeThreaded = None

# Ensure workspace root is importable when running this file directly.
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from pyqt_scroll_charts import ChartConfig, ScrollChartsApp
except ImportError:
    from pyqt_scroll_charts import ChartConfig, ScrollChartsApp

PLUTO_IP_ADDR_RX1 = "ip:192.168.2.5"
SAMPLE_RATE = 1e6
CENTER_FREQ = 433.2e6
NUM_SAMPS = 1e6
RX_GAIN = 70.0
AGC_MODE = "slow_attack"

SYMBOLS_PER_SAMPLE = 52.0
DISCRIMINATOR_GAIN = 1.0

qt_gui_configs = [
    # 时域图
    ChartConfig(
        num_series=1,
        buffer_size=1024,
		autoscale=True,
        y_range=(-2.0, 2.0),
        hline_values=[0.0],
        title='原始信号',
        plot_mode='time',
    ),
    # 频域图
    ChartConfig(
        num_series=2,
        buffer_size=4096,
        y_range=(-90.0, 0.0),
        hline_values=[],
        title='信号频谱',
        plot_mode='fft',
        sample_rate=SAMPLE_RATE,
        fft_size=1024,
        fft_shift=True,
        fft_db=True,
    ),
	# 正交鉴频后与二次滤波后
	ChartConfig(
        num_series=2,
        buffer_size=1024,
		autoscale=True,
        y_range=(-2.0, 2.0),
        hline_values=[0.0],
        title='正交鉴频',
        plot_mode='time',
    ),
	# 同步后
	ChartConfig(
        num_series=1,
        buffer_size=128,
		autoscale=False,
        y_range=(-2.0, 2.0),
        hline_values=[0.0],
        title='同步后符号',
        plot_mode='time',
    ),
]


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
			print(f"Publishing ROS2 message: {json_str}")
			logging.log(logging.INFO, f"Publishing ROS2 message: {json_str}")
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
	qt_app: ScrollChartsApp | None = None,
) -> np.ndarray:
	"""处理单个采样块并返回最终 bits。同时进行可视化"""

	complex_samples = _to_1d_array(samples).astype(np.complex128, copy=False)
	print(complex_samples.shape, complex_samples.dtype)
	qt_app.add_values(0, complex_samples) if qt_app else None
	filtered_iq = apply_fft_filter(complex_samples, pre_taps)
	qt_app.add_values(1, [complex_samples, filtered_iq]) if qt_app else None
	demodulated = discriminator.process(filtered_iq)
	filtered_audio = apply_fft_filter(demodulated, post_taps)
	qt_app.add_values(2, [demodulated, filtered_audio]) if qt_app else None
	synced_symbols = symbol_sync.process(filtered_audio)
	qt_app.add_values(3, synced_symbols) if qt_app else None
	return bpsk_bits_from_symbols(synced_symbols)

def main() -> None:
	qt_app = ScrollChartsApp(qt_gui_configs, uniform_height=320)
	qt_app.show()

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
		ip_addr=PLUTO_IP_ADDR_RX1,
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

	# 预热可能存在的 JIT 路径，避免首包处理时出现明显卡顿。
	try:
		discriminator.process(np.zeros(32, dtype=np.complex128))
		symbol_sync.process(np.zeros(256, dtype=np.float64))
		symbol_sync.reset()
	except Exception:
		pass

	decoder = frame_decoder_direct(
		type="signal",
		on_frame_decoded=_build_ros_publisher_callback(ros_node) if ros_node else None,
		crc16_enabled=False,
	)

	print("main_rx started, press Ctrl+C to stop.")

	try:
		while True:
			qt_app.process_events()
			samples = rx_ctrl.rx()
			if samples is None:
				qt_app.process_events()
				time.sleep(0.01)
				print("maincycle continue")
				continue

			bits = process_chunk(
				samples=samples,
				pre_taps=TAPS_LPF_PRE,
				post_taps=TAPS_LPF,
				discriminator=discriminator,
				symbol_sync=symbol_sync,
				qt_app=qt_app,
			)

			print(f"maincycle running...{time.time():.2f}")
			qt_app.process_events()

			if bits.size == 0:
				qt_app.process_events()
				continue

			decoded_frames = decoder.push_bits(bits)
			if decoded_frames:
				print(f"frames({len(decoded_frames)}): {decoded_frames}")
	finally:
		if ros_node is not None:
			ros_node.stop()


if __name__ == "__main__":
	import logging
	LOG_FILE_PATH = CURRENT_DIR / f"main_rx_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.DEBUG, filename=LOG_FILE_PATH, filemode='w')
	try:
		main()
	except KeyboardInterrupt:
		print("stopped")
