#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 选边
CURRENT_SITE = CurrentSite.RED

# 选项
VISUALIZE_ON = True
RECORD_SIGNAL_ON = True

# 参数
NUM_SAMPS = 1e5 # 10Hz

from dataclasses import dataclass
from extract_usb import *
@dataclass
class DeviceConfig:
	device_sig : str
	device_inf : str
	device_backup : str

# 配置设备使用
# pluto设备使用序列号
# rtlsdr用字符串"rtlsdr"
device_conf = DeviceConfig(
	device_sig=SERIAL_PLUTO_NANO_2,
	device_inf=SERIAL_PLUTO_SDR,
	device_backup="rtlsdr"
)

# ------分界线------

from __future__ import annotations

import json
from enum import Enum
from collections.abc import Callable
from pathlib import Path
import sys
import time
import threading
from queue import Queue, Empty
import numpy as np
import logging


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
	sys.path.insert(0, str(CURRENT_DIR))

from pluto_ctrl import pluto_ctrl_rx, rtl_sdr_ctrl
from fftfilter import apply_fft_filter
from frame_decoder_direct import frame_decoder_direct
from def_status import dict_to_dataclass
from quadrate_discriminator import QuadratureDiscriminator, QuadratureDiscriminatorConfig
from symbol_sync import MMSymbolSynchronizer, MMSymbolSyncConfig, bpsk_bits_from_symbols
from def_taps import *
from def_signal import *

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

# 接收信号的子线程的配置模版
@dataclass
class RxConfig:
	device : str = "pluto" # 或"rtlsdr"
	type : str = "sig" # 或"inf"
	center_freq: float
	sample_rate: float = SAMP_RATE
	num_samps: int = NUM_SAMPS
	rx_gain: float | None = None 
	agc_mode: str = "slow_attack"
	descriminator_gain: float = 1.0

# Qt可视化图表配置 两个线程都是用同样的配置
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
	# 频域图 滤波前与滤波后
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
	decoder: frame_decoder_direct | None = None,
	qt_app: ScrollChartsApp | None = None,
	visualize_on=False,
) -> tuple[np.ndarray, list]:
	"""处理单个采样块，返回 bits 与 decoded_frames，同时进行可视化"""

	complex_samples = _to_1d_array(samples).astype(np.complex128, copy=False)
	qt_app.add_values(0, complex_samples) if qt_app and visualize_on else None
	filtered_iq = apply_fft_filter(complex_samples, pre_taps)
	qt_app.add_values(1, [complex_samples, filtered_iq]) if qt_app and visualize_on else None
	demodulated = discriminator.process(filtered_iq)
	filtered_audio = apply_fft_filter(demodulated, post_taps)
	qt_app.add_values(2, [demodulated, filtered_audio]) if qt_app and visualize_on else None
	synced_symbols = symbol_sync.process(filtered_audio)
	qt_app.add_values(3, synced_symbols) if qt_app and visualize_on else None
	bits = bpsk_bits_from_symbols(synced_symbols)
	decoded_frames = []
	if decoder is not None and bits.size > 0:
		decoded_frames = decoder.push_bits(bits)
	return bits, decoded_frames

def main(devices:DeviceConfig, 
		 device_timeout=20, 
		 inf_level_timeout=5, 
		 device_search_timeout=10, 
		 main_cycle_update_interval=0.5) -> None:
	"""
	负责管理信号接收的两个子线程
	@param devices: 配置设备使用
	@param device_timeout: sdr设备断连多长时间后切换到备用设备
	@param inf_level_timeout: 干扰波多长时间解析失败切换干扰等级
	@param device_search_timeout: iio_info搜索设备的超时时间
	@main_cycle_update_interval: 主循环时间间隔
	"""
	# 线程间共享状态与异常上报
	status_lock = threading.Lock()
	thread_status = {}
	thread_threads = {}
	thread_stop_events = {}
	thread_devices = {}
	last_decode_time = {}
	exception_queue: Queue[tuple[str, Exception]] = Queue()
	decode_queue: Queue[tuple[str, float]] = Queue()

	def _build_sig_config(device: str) -> RxConfig:
		return RxConfig(
			device=device,
			type="sig",
			center_freq=FC_RED if CURRENT_SITE == CurrentSite.RED else FC_BLUE,
			descriminator_gain=GAIN_SIG,
		)

	def _build_inf_config(level: int, device: str) -> RxConfig:
		if CURRENT_SITE == CurrentSite.RED:
			freq_map = {1: FC_RED_1, 2: FC_RED_2, 3: FC_RED_3}
		else:
			freq_map = {1: FC_BLUE_1, 2: FC_BLUE_2, 3: FC_BLUE_3}
		gain_map = {1: GAIN_1, 2: GAIN_2, 3: GAIN_3}
		return RxConfig(
			device=device,
			type="inf",
			center_freq=freq_map[level],
			descriminator_gain=gain_map[level],
		)

	def _worker_thread(
		name: str,
		rx_config: RxConfig,
		stop_event: threading.Event,
		on_decoded: Callable[[list], None] | None,
	):
		try:
			with status_lock:
				thread_status[name] = "running"
			work(
				rx_config,
				search_timeout=device_search_timeout,
				stop_event=stop_event,
				on_decoded=on_decoded,
			)
		except Exception as exc:
			exception_queue.put((name, exc))
			with status_lock:
				thread_status[name] = "error"
			logging.exception("worker %s failed", name)
		else:
			with status_lock:
				thread_status[name] = "stopped"

	def _start_worker(name: str, rx_config: RxConfig) -> None:
		stop_event = threading.Event()

		def _on_decoded(_frames: list) -> None:
			decode_queue.put((name, time.time()))

		thread = threading.Thread(
			target=_worker_thread,
			name=name,
			args=(name, rx_config, stop_event, _on_decoded),
			daemon=True,
		)
		with status_lock:
			thread_threads[name] = thread
			thread_stop_events[name] = stop_event
			thread_devices[name] = rx_config.device
			thread_status[name] = "starting"
			last_decode_time[name] = time.time()
		thread.start()

	def _stop_worker(name: str, join_timeout: float = 2.0) -> bool:
		with status_lock:
			stop_event = thread_stop_events.get(name)
			thread = thread_threads.get(name)
		if stop_event is not None:
			stop_event.set()
		if thread is not None:
			thread.join(timeout=join_timeout)
			return not thread.is_alive()
		return True

	def _backup_in_use_by() -> str | None:
		with status_lock:
			for name, device in thread_devices.items():
				thread = thread_threads.get(name)
				if thread is not None and thread.is_alive() and device == devices.device_backup:
					return name
		return None

	# 接收设备配置
	inf_level = 1
	rx_conf_sig = _build_sig_config(devices.device_sig)
	rx_conf_inf = _build_inf_config(inf_level, devices.device_inf)

	_start_worker("rx_sig", rx_conf_sig)
	_start_worker("rx_inf", rx_conf_inf)

	# 主循环
	while True:
		# 更新解析时间
		try:
			while True:
				name, ts = decode_queue.get_nowait()
				with status_lock:
					last_decode_time[name] = ts
		except Empty:
			pass

		# 处理异常，必要时切换到备用设备
		try:
			while True:
				name, exc = exception_queue.get_nowait()
				print(f"Worker {name} error: {exc}")
				logging.error("Worker %s error: %s", name, exc)

				backup_owner = _backup_in_use_by()
				if (
					devices.device_backup
					and backup_owner is None
				):
					_stop_worker(name)
					if name == "rx_inf":
						rx_conf_inf = _build_inf_config(inf_level, devices.device_backup)
						_start_worker("rx_inf", rx_conf_inf)
					else:
						rx_conf_sig = _build_sig_config(devices.device_backup)
						_start_worker("rx_sig", rx_conf_sig)
		except Empty:
			pass

		# 干扰等级轮换
		with status_lock:
			inf_thread = thread_threads.get("rx_inf")
			inf_last = last_decode_time.get("rx_inf", time.time())
			inf_device = thread_devices.get("rx_inf", devices.device_inf)
		if inf_thread is not None and inf_thread.is_alive():
			if time.time() - inf_last >= inf_level_timeout:
				stopped = _stop_worker("rx_inf")
				if stopped:
					inf_level = 1 if inf_level >= 3 else inf_level + 1
					rx_conf_inf = _build_inf_config(inf_level, inf_device)
					_start_worker("rx_inf", rx_conf_inf)

		time.sleep(main_cycle_update_interval)


def work(
	rx_config:RxConfig,
	search_timeout=10,
	stop_event: threading.Event | None = None,
	on_decoded: Callable[[list], None] | None = None,
) -> None:
	"""
	接收信号线程
	包括硬件控制 信号处理 发送ros信息 可视化
	"""
	# 初始化qt可视化
	qt_app = ScrollChartsApp(qt_gui_configs, uniform_height=320)
	qt_app.show()

	# 初始化ros通信节点
	ros_node = None
	if WirelessRos2AdaptorNodeThreaded is not None:
		try:
			ros_node = WirelessRos2AdaptorNodeThreaded()
			ros_node.start()
			print("ROS2 wireless adaptor started")
		except Exception as exc:
			ros_node = None
			print(f"ROS2 adaptor unavailable: {exc}")

	device = rx_config.device
	if device != "rtlsdr": # 使用pluto 需要先用序列号提取对应的iio_context的usb标识
		devices = get_all_pluto_devices(timeout=search_timeout)
		serial = device_conf.device_sig if device == "pluto" else device
		usb_name = get_pluto_usb_by_serial(devices, serial)
		rx_ctrl = pluto_ctrl_rx(
			ip_addr=usb_name,
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
		QuadratureDiscriminatorConfig(gain=rx_config.discriminator_gain)
	)
	symbol_sync = MMSymbolSynchronizer(
		MMSymbolSyncConfig(omega=SPS)
	)

	# 预热可能存在的 JIT 路径，避免首包处理时出现明显卡顿。
	try:
		discriminator.process(np.zeros(32, dtype=np.complex128))
		symbol_sync.process(np.zeros(256, dtype=np.float64))
		symbol_sync.reset()
	except Exception:
		pass

	decoder = frame_decoder_direct(
		type=rx_config.type,
		on_frame_decoded=_build_ros_publisher_callback(ros_node) if ros_node else None,
		crc16_enabled=True,
	)

	print("main_rx started, press Ctrl+C to stop.")

	try:
		while True:
			if stop_event is not None and stop_event.is_set():
				break
			qt_app.process_events()
			samples = rx_ctrl.rx()
			if samples is None:
				qt_app.process_events()
				time.sleep(0.01)
				print("maincycle continue")
				continue

			bits, decoded_frames = process_chunk(
				samples=samples,
				pre_taps=TAPS_LPF_PRE,
				post_taps=TAPS_LPF,
				discriminator=discriminator,
				symbol_sync=symbol_sync,
				decoder=decoder,
				qt_app=qt_app,
			)

			print(f"maincycle running...{time.time():.2f}")
			qt_app.process_events()

			if bits.size == 0:
				qt_app.process_events()
				continue

			if decoded_frames:
				if on_decoded is not None:
					on_decoded(decoded_frames)
				print(f"frames({len(decoded_frames)}): {decoded_frames}")
	finally:
		if ros_node is not None:
			ros_node.stop()

