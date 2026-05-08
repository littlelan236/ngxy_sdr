#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
import sys
import time
import numpy as np
import logging
from dataclasses import dataclass

import sys
# 强制处理 librtlsdr 的依赖冲突 (libusb 符号问题)
if sys.platform == "linux":
    # 优先加载正确的 libusb 避免 undefined symbol: libusb_dev_mem_free
    try:
        import ctypes
        # 尝试加载系统的 libusb
        for path in ["/usr/lib/x86_64-linux-gnu/libusb-1.0.so.0", "libusb-1.0.so.0"]:
            try:
                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                break
            except:
                continue
    except:
        pass



CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
	sys.path.insert(0, str(CURRENT_DIR))

from pluto_ctrl import pluto_ctrl_rx, rtl_sdr_ctrl
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

SYMBOLS_PER_SAMPLE = 52.0

@dataclass
class RxConfig:
	ip_addr : str | None = None
	sample_rate: float = 1e6
	center_freq: float = 433.2e6
	num_samps: int = 1e6
	rx_gain: float = 70.0
	agc_mode: str = "slow_attack"
	descriminator_gain: float = 1.0

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
        sample_rate=1e6,
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

def main(device, rx_config) -> None:
	"""
	主函数：初始化 SDR 接收器、信号处理模块和可视化界面，进入主循环处理数据并发布 ROS2 消息。
	@param device: SDR 设备类型， "pluto" 或 "rtlsdr"
	@param rx_config: 接收配置
	"""
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

	if device == "pluto":
		rx_ctrl = pluto_ctrl_rx(
			ip_addr=rx_config.ip_addr,
			sample_rate=rx_config.sample_rate,
			center_freq=rx_config.center_freq,
			num_samps=rx_config.num_samps,
			rx_hardwaregain_chan0=rx_config.rx_gain,
			agc_mode=rx_config.agc_mode,
		)
	else:
		rx_ctrl = rtl_sdr_ctrl(
			sample_rate=rx_config.sample_rate,
			center_freq=rx_config.center_freq,
			num_samps=rx_config.num_samps,
		 	rx_gain='auto' if rx_config.agc_mode != 'manual' else rx_config.rx_gain,
		)


	discriminator = QuadratureDiscriminator(
		QuadratureDiscriminatorConfig(gain=rx_config.descriminator_gain)
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
@dataclass
class SigTxConfig:
	center_freq: float
	sample_rate: float
	num_samps: int
	tx_gain: float | None = None
	iq_file: str | None = None

from enum import Enum
# 模拟发送的iq信号文件路径
class SimSigType(Enum):
	SIG1_PATH = "/home/ubuntu/radar2026/radio26/sig1.iq"
	SIG2_PATH = "/home/ubuntu/radar2026/radio26/sig2.iq"
	INF1_PATH = "/home/ubuntu/radar2026/radio26/inf1.iq"
	INF2_PATH = "/home/ubuntu/radar2026/radio26/inf2.iq"

from def_signal import *
# 模拟发送的iq信号配置 在本程序中仅支持发送信号源 使用device_sig
tx_config = SigTxConfig(
	center_freq=FC_RED,
	sample_rate=SAMP_RATE,
	num_samps=327680,
	tx_gain=-0.0, # -90 to 0
	iq_file=SimSigType.SIG1_PATH.value,
)
import adi
from main_rx_ctrl import get_all_pluto_devices, get_pluto_usb_by_serial, TIMEOUT_DEVICE_SEARCH, device_conf
def tx_sig(sigTxConfig: SigTxConfig) -> None:
	"""开启模拟的信号发送"""
	if not sigTxConfig.iq_file:
		raise ValueError("iq_file is required for tx_sig")
	devices = get_all_pluto_devices(timeout=TIMEOUT_DEVICE_SEARCH)
	print(f"Found Pluto devices: {devices}")
	logging.log(logging.INFO, f"Found Pluto devices: {devices}")
	serial = device_conf.device_inf
	usb_name = get_pluto_usb_by_serial(devices, serial)
	print(f"Using Pluto device with serial {serial} at USB address {usb_name} for transmission")
	logging.log(logging.INFO, f"Using Pluto device with serial {serial} at USB address {usb_name} for transmission")

	sdr = adi.Pluto(usb_name)
	sdr.sample_rate = int(sigTxConfig.sample_rate)
	sdr.tx_rf_bandwidth = int(sigTxConfig.sample_rate)
	sdr.tx_lo = int(sigTxConfig.center_freq)
	sdr.tx_hardwaregain_chan0 = int(sigTxConfig.tx_gain)
	sdr.tx_cyclic_buffer = True

	sample_count = int(sigTxConfig.num_samps)
	samples = np.fromfile(sigTxConfig.iq_file, dtype=np.complex64, count=sample_count)
	if samples.size == 0:
		raise ValueError(f"No samples loaded from {sigTxConfig.iq_file}")
	if samples.size < sample_count:
		logging.warning(
			"Requested %d samples but only %d available in %s",
			sample_count,
			samples.size,
			sigTxConfig.iq_file,
		)
	sdr.tx_buffer_size = int(samples.size)
	sdr.tx(samples)
	print("Started transmitting signal from file: %s", sigTxConfig.iq_file)
	logging.log(logging.INFO, "Started transmitting signal from file: %s", sigTxConfig.iq_file)


if __name__ == "__main__":
	LOG_FILE_PATH = CURRENT_DIR / f"main_rx_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.DEBUG, filename=LOG_FILE_PATH, filemode='w')
	rx_config = RxConfig(
		ip_addr="usb:1.19.5",
		sample_rate=1e6,
		center_freq=433.2e6,
		num_samps=100000,
		rx_gain=70.0,
		agc_mode="slow_attack",
		descriminator_gain=1.0,
	)
	try:
		main("pluto", rx_config)
	except KeyboardInterrupt:
		print("stopped")
