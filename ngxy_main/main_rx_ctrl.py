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
	from wireless_ros2_adaptor import WirelessRos2AdaptorNodeThreaded, Faction
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
	if len(decoded_frames) > 0:
		logging.log(logging.INFO, f"frame decoded: {decoded_frames}")
	logging.log(logging.DEBUG, f"Processed chunk: {len(complex_samples)} samples, {len(bits)} bits, {len(decoded_frames)} frames decoded")
	return bits, decoded_frames

def main(devices:DeviceConfig, 
		 inf_level_timeout=5, 
		 device_search_timeout=10, 
		 main_cycle_update_interval=0.5,
		 faction_timeout=15) -> None:
	"""
	负责管理信号接收的两个子线程
	在默认的接收设备报错时，切换到备用设备
	若备用设备已占用，则尝试重启当前设备一次
	备用设备报错会一直尝试重启
	@param devices: 配置设备使用
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
	restart_attempted = {}
	exception_queue: Queue[tuple[str, Exception]] = Queue()
	last_decode_time_queue: Queue[tuple[str, float]] = Queue()
	ros_level_queue: Queue[int] = Queue()
	main_device_map = {
		"rx_sig": devices.device_sig,
		"rx_inf": devices.device_inf,
	}

	def _on_ros_encrypt_level_change(new_level: int) -> None:
		ros_level_queue.put(new_level)

	def _build_sig_config(device: str, site: CurrentSite) -> RxConfig:
		return RxConfig(
			device=device,
			type="sig",
			center_freq=FC_RED if site == CurrentSite.RED else FC_BLUE,
			descriminator_gain=GAIN_SIG,
		)

	def _build_inf_config(level: int, device: str, site: CurrentSite) -> RxConfig:
		if site == CurrentSite.RED:
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
			print(f"worker {name} failed: {exc}")
		else:
			with status_lock:
				thread_status[name] = "stopped"

	def _start_worker(name: str, rx_config: RxConfig) -> None:
		print(f"Starting worker {name} with device {rx_config.device}...")
		logging.log(logging.INFO, f"Starting worker {name} with device {rx_config.device}...")
		stop_event = threading.Event()

		def _on_decoded(_frames: list) -> None:
			last_decode_time_queue.put((name, time.time()))

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
			restart_attempted.setdefault(name, False)
		thread.start()

	def _stop_worker(name: str, join_timeout: float = 2.0) -> bool:
		print(f"Stopping worker {name}...")
		logging.log(logging.INFO, f"Stopping worker {name}...")
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
		print("Checking if backup device is in use...")
		logging.log(logging.INFO, "Checking if backup device is in use...")
		with status_lock:
			for name, device in thread_devices.items():
				thread = thread_threads.get(name)
				if thread is not None and thread.is_alive() and device == devices.device_backup:
					print(f"Backup device is currently in use by {name}")
					logging.log(logging.INFO, f"Backup device is currently in use by {name}")
					return name
		return None

	def _wait_for_decode_or_error(
		worker_name: str,
		timeout_sec: float,
	) -> tuple[bool, Exception | None]:
		start_time = time.time()
		while time.time() - start_time < timeout_sec:
			try:
				while True:
					name, ts = last_decode_time_queue.get_nowait()
					with status_lock:
						last_decode_time[name] = ts
						restart_attempted[name] = False
					if name == worker_name:
						return True, None
			except Empty:
				pass

			other_errors: list[tuple[str, Exception]] = []
			try:
				while True:
					name, exc = exception_queue.get_nowait()
					if name == worker_name:
						return False, exc
					other_errors.append((name, exc))
			except Empty:
				pass
			finally:
				for item in other_errors:
					exception_queue.put(item)

			time.sleep(0.05)
		return False, None

	def _get_faction_with_timeout(
		node: WirelessRos2AdaptorNodeThreaded,
		timeout_sec: float,
	) -> Faction:
		result: dict[str, Faction] = {"faction": Faction.UNKNOWN}
		done = threading.Event()

		def _worker() -> None:
			try:
				result["faction"] = node.get_faction()
			except Exception as exc:
				logging.error("Faction query failed: %s", exc)
			finally:
				done.set()

		thread = threading.Thread(target=_worker, daemon=True)
		thread.start()
		done.wait(timeout=timeout_sec)
		if not done.is_set():
			logging.warning("Faction query timed out after %.2f seconds", timeout_sec)
			return Faction.UNKNOWN
		return result["faction"]

	# 尝试使用ros获取当前阵营信息
	current_site: CurrentSite | None = None
	if WirelessRos2AdaptorNodeThreaded is not None:
		faction_node = None
		try:
			faction_node = WirelessRos2AdaptorNodeThreaded(namespace="main_ctrl_faction")
			faction_node.start()
			faction = _get_faction_with_timeout(faction_node, faction_timeout)
			if faction == Faction.RED:
				current_site = CurrentSite.RED
				logging.log(logging.INFO, "Determined faction from ROS node: RED")
				print("Determined faction from ROS node: RED")
			elif faction == Faction.BLUE:
				current_site = CurrentSite.BLUE
				logging.log(logging.INFO, "Determined faction from ROS node: BLUE")
				print("Determined faction from ROS node: BLUE")
			else:
				logging.warning("Failed to determine faction from ROS node, got: %s", faction)
				print(f"Failed to determine faction from ROS node, got: {faction}")
		# 关闭ros节点
		finally:
			if faction_node is not None:
				faction_node.stop()

	# 若未成功获取阵营信息（超时），则尝试对红蓝方信息波进行解调，成功则确定当前阵营信息
	# 反复轮询尝试，包括主设备故障时启用备用设备的逻辑，直到成功解析才会往下走
	if current_site is None:
		probe_timeout = inf_level_timeout
		while True:
			for site in (CurrentSite.RED, CurrentSite.BLUE):
				device_candidates = [devices.device_sig]
				if (
					devices.device_backup
					and devices.device_backup != devices.device_sig
				):
					device_candidates.append(devices.device_backup)
				for device in device_candidates:
					rx_conf_sig = _build_sig_config(device, site)
					_start_worker("rx_sig", rx_conf_sig)
					decoded, error = _wait_for_decode_or_error("rx_sig", probe_timeout)
					_stop_worker("rx_sig")
					if decoded:
						current_site = site
						break
					if error is not None and device == devices.device_sig:
						continue
				if current_site is not None:
					break
			if current_site is not None:
				logging.log(logging.INFO, "Determined faction from ROS node: %s", current_site.name)
				print(f"Determined faction from ROS node: {current_site.name}")
				break

	# 接收设备配置
	inf_level = 1
	rx_conf_sig = _build_sig_config(devices.device_sig, current_site)
	rx_conf_inf = _build_inf_config(inf_level, devices.device_inf, current_site)

	# 启用监听ros节点进程监听干扰等级
	ros_listener = None
	if WirelessRos2AdaptorNodeThreaded is not None:
		try:
			ros_listener = WirelessRos2AdaptorNodeThreaded(
				on_encrypt_level_change_callback=_on_ros_encrypt_level_change,
				namespace="main_ctrl",
			)
			ros_listener.start()
			logging.info("ROS2 level listener started")
		except Exception as exc:
			ros_listener = None
			logging.error("ROS2 level listener unavailable: %s", exc)

	# 启动信息波解析/干扰波解析的两个线程
	with status_lock:
		rx_sig_thread = thread_threads.get("rx_sig")
	if rx_sig_thread is None or not rx_sig_thread.is_alive():
		_start_worker("rx_sig", rx_conf_sig)
	else:
		_stop_worker("rx_sig")
		_start_worker("rx_sig", rx_conf_sig)
	_start_worker("rx_inf", rx_conf_inf)

	logging.info("Main control started with initial config: rx_sig on %s, rx_inf on %s (inf level %d)", rx_conf_sig.device, rx_conf_inf.device, inf_level)
	print(f"Main control started with initial config: rx_sig on {rx_conf_sig.device}, rx_inf on {rx_conf_inf.device} (inf level {inf_level})")
	
	# 主循环
	try:
		while True:
			# 更新解析时间
			try:
				while True:
					name, ts = last_decode_time_queue.get_nowait()
					with status_lock:
						last_decode_time[name] = ts
						restart_attempted[name] = False
			except Empty:
				pass
			# 处理异常，必要时切换到备用设备
			try:
				while True:
					name, exc = exception_queue.get_nowait()
					print(f"Worker {name} error: {exc}")
					logging.error("Worker %s error: %s", name, exc)
					print(f"Attempting to switch {name} to backup device...")
					logging.log(logging.INFO, f"Worker {name} error: {exc}, attempting to switch to backup device if available.")

					with status_lock:
						current_device = thread_devices.get(name)
					backup_owner = _backup_in_use_by()
					# 当备用设备空闲时，直接将出现问题的线程切换至备用设备
					if devices.device_backup and backup_owner is None:
						_stop_worker(name)
						if name == "rx_inf":
							rx_conf_inf = _build_inf_config(inf_level, devices.device_backup, current_site)
							_start_worker("rx_inf", rx_conf_inf)
						else:
							rx_conf_sig = _build_sig_config(devices.device_backup, current_site)
							_start_worker("rx_sig", rx_conf_sig)
						print(f"Switched {name} to backup device: {devices.device_backup}")
						logging.info(f"Switched {name} to backup device: {devices.device_backup}")
					# 若当前备用设备被占用，尝试重启一次当前设备
					elif backup_owner is not None and current_device == main_device_map.get(name):
						logging.log(logging.INFO, f"Backup device {devices.device_backup} is currently in use by {backup_owner}, attempting to restart current device {current_device} for {name}.")	
						print(f"Backup device {devices.device_backup} is currently in use by {backup_owner}, attempting to restart current device {current_device} for {name}...")
						with status_lock:
							already_tried = restart_attempted.get(name, False)
						if not already_tried:
							with status_lock:
								restart_attempted[name] = True
							_stop_worker(name)
							main_device = main_device_map.get(name)
							if name == "rx_inf":
								rx_conf_inf = _build_inf_config(inf_level, main_device, current_site)
								_start_worker("rx_inf", rx_conf_inf)
							else:
								rx_conf_sig = _build_sig_config(main_device, current_site)
								_start_worker("rx_sig", rx_conf_sig)
			except Empty:
				pass

			# 处理 ROS 干扰等级变化
			ros_level_applied = False
			try:
				while True:
					new_level = ros_level_queue.get_nowait()
					if new_level in (1, 2, 3) and new_level != inf_level:
						stopped = _stop_worker("rx_inf")
						if stopped:
							inf_level = new_level
							with status_lock:
								inf_device = thread_devices.get("rx_inf", devices.device_inf)
							rx_conf_inf = _build_inf_config(inf_level, inf_device, current_site)
							_start_worker("rx_inf", rx_conf_inf)
							with status_lock:
								last_decode_time["rx_inf"] = time.time()
							ros_level_applied = True
							logging.info("rx_inf switched to level %s due to ROS command", inf_level)
							print(f"rx_inf switched to level {inf_level} due to ROS command")
			except Empty:
				pass

			# 干扰等级轮换
			if not ros_level_applied:
				with status_lock:
					inf_thread = thread_threads.get("rx_inf")
					inf_last = last_decode_time.get("rx_inf", time.time())
					inf_device = thread_devices.get("rx_inf", devices.device_inf)
				if inf_thread is not None and inf_thread.is_alive():
					if time.time() - inf_last >= inf_level_timeout:
						stopped = _stop_worker("rx_inf")
						if stopped:
							inf_level = 1 if inf_level >= 3 else inf_level + 1
							rx_conf_inf = _build_inf_config(inf_level, inf_device, current_site)
							_start_worker("rx_inf", rx_conf_inf)
							logging.info("rx_inf switched to next level %d due to timeout", inf_level)
							print(f"rx_inf switched to next level {inf_level} due to timeout")

			time.sleep(main_cycle_update_interval)
	finally:
		if ros_listener is not None:
			ros_listener.stop()


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
			ros_node = WirelessRos2AdaptorNodeThreaded(namespace=f"worker_{rx_config.type}")
			ros_node.start()
			print("ROS2 wireless adaptor started")
			logging.info("ROS2 wireless adaptor started")
		except Exception as exc:
			ros_node = None
			print(f"ROS2 adaptor unavailable: {exc}")
			logging.log(logging.ERROR, f"ROS2 adaptor unavailable: {exc}")

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

	logging.log(logging.INFO, f"Worker started with config: {rx_config}")
	print(f"Worker started with config: {rx_config}")

	try:
		record_file = None
		try:
			if RECORD_SIGNAL_ON:
				timestamp = time.strftime("%Y%m%d_%H%M%S")
				filename = f"record_{rx_config.type}_{timestamp}.iq"
				print(f"Recording signal to {filename}")
				record_file = open(filename, "wb")
				logging.log(logging.INFO, f"Recording signal to {filename}")
				print(f"Recording signal to {filename}")
			while True:
				if stop_event is not None and stop_event.is_set():
					break
				qt_app.process_events()
				samples = rx_ctrl.rx()
				if record_file is not None and samples is not None:
					samples.tofile(record_file)
				if samples is None:
					qt_app.process_events()
					time.sleep(0.01)
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

				qt_app.process_events()

				if bits.size == 0:
					qt_app.process_events()
					continue

				if decoded_frames:
					if on_decoded is not None:
						on_decoded(decoded_frames)
		finally:
			if record_file is not None:
				record_file.close()
				logging.log(logging.INFO, "Finished recording signal.")
				print("Finished recording signal.")
	finally:
		if ros_node is not None:
			ros_node.stop()

if __name__ == "__main__":
	main(device_conf)