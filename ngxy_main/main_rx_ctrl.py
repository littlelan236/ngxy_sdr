#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 选项
VISUALIZE_ON = True
RECORD_SIGNAL_ON = True
SIGNAL_TX_ON = False

# 参数
NUM_SAMPS = 1e5 # 10Hz

THRESHOLD_ERR_COUNT = 10
TIMEOUT_DEVICE_SEARCH = 15
INTERVAL_MAIN_CYCLE = 0.1
TIMEOUT_ROS_FACTION_QUERY = 5
INTERVAL_MAIN_CYCLE_DEVICE_CTRL = 5.0
TIMEOUT_INF_LEVEL = 5
TIMEOUT_STOP_WORKER_JOIN = 2.0
TIMEOUT_ENSURE_WORKER_STOPPED = 3.0
INTERVAL_GET_IIO_INFO = 5.0

from dataclasses import dataclass
from extract_usb import *
@dataclass
class DeviceConfig:
	device_sig : str
	device_inf : str
	device_backup : str
	device_sig_addr : str | None
	device_inf_addr : str | None
	device_backup_addr : str | None

# 配置设备使用
# pluto设备使用序列号
# rtlsdr用字符串"rtlsdr"
device_conf = DeviceConfig(
	device_sig=SERIAL_PLUTO_NANO_2,
	device_inf=SERIAL_PLUTO_SDR,
	# device_sig=SERIAL_PLUTO_SDR,
	# device_inf=SERIAL_PLUTO_NANO_2,
	device_backup="rtlsdr",
	device_sig_addr=None,
	device_inf_addr=None,
	device_backup_addr=None,
)

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
# 模拟发送的iq信号配置 
# 当前的设置是，在检测到阵营信息后切换为tx_config_1
# 使用inf设备进行发送
tx_config = SigTxConfig(
	center_freq=FC_RED,
	sample_rate=SAMP_RATE,
	num_samps=327680,
	tx_gain=-0.0, # -90 to 0
	iq_file=SimSigType.SIG1_PATH.value,
)

tx_config_1 = SigTxConfig(
	center_freq=FC_RED_1,
	sample_rate=SAMP_RATE,
	num_samps=327680,
	tx_gain=-0.0, # -90 to 0
	iq_file=SimSigType.INF1_PATH.value,
)


# ------分界线------

# 避免反复尝试iio_info导致延迟过大
last_get_iio_info_time = 0

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

import json
import gc
from collections.abc import Callable
from pathlib import Path
import sys
import time
import threading
from queue import Queue, Empty
import numpy as np
import logging
from PyQt5 import QtWidgets
import rclpy
import adi


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
from wireless_ros2_adaptor import WirelessRos2AdaptorNodeThreaded, Faction

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
	device : str | None = None # pluto设备的序列号 或 "rtlsdr"
	type : str = "sig" # 或"inf"
	center_freq: float = FC_RED
	sample_rate: float = SAMP_RATE
	num_samps: int = NUM_SAMPS
	rx_gain: float | None = None 
	agc_mode: str = "slow_attack"
	discriminator_gain: float = 1.0

# Qt可视化图表配置 两个线程都是用同样的配置
qt_gui_configs = [
	# 时域图
	ChartConfig(
		num_series=1,
		buffer_size=1024,
		autoscale=False,
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


def _publish_ros_messages(ros_node, data_dict: dict) -> None:
	json_str = json.dumps(data_dict, default=_json_default, ensure_ascii=False)
	print(f"Publishing ROS2 message: {json_str}")
	logging.log(logging.INFO, f"Publishing ROS2 message: {json_str}")
	ros_node.publish_wireless_result(json_str)


def _build_ros_queue_callback(ros_queue: Queue[list[dict]]):
	def _on_frame_decoded(data_dict_list: list[dict]):
		for dict in data_dict_list:
			ros_queue.put(dict)

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
	# if pre_taps is not None:
	# 	filtered_iq = apply_fft_filter(complex_samples, pre_taps)
	# else:
	# 	filtered_iq = complex_samples
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
		 inf_level_timeout=TIMEOUT_INF_LEVEL, 
		 device_search_timeout=TIMEOUT_DEVICE_SEARCH, 
		 main_cycle_update_interval=INTERVAL_MAIN_CYCLE,
		 faction_timeout=TIMEOUT_ROS_FACTION_QUERY,
		 qt_apps: dict[str, ScrollChartsApp] | None = None,
		 stop_event: threading.Event | None = None,
		main_cycle_device_ctrl_interval = INTERVAL_MAIN_CYCLE_DEVICE_CTRL)-> None:
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
	# 初始化 ROS
	if not rclpy.ok():
		rclpy.init(args=None)

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
	ros_publish_queue: Queue[list[dict]] = Queue()
	last_device_ctrl_time = 0 #  上次控制设备的时间戳，用于避免过于频繁地切换设备
	qt_apps = qt_apps or {}
	main_device_map = {
		"rx_sig": devices.device_sig,
		"rx_inf": devices.device_inf,
	}
	# 将多次故障的设备记录下来
	error_counts: dict[str, int] = {}
	error_logged: set[str] = set()
	error_log_path = CURRENT_DIR / "error"
	for device in (devices.device_sig, devices.device_inf, devices.device_backup):
		if device:
			error_counts.setdefault(device, 0)

	def _should_stop() -> bool:
		return stop_event is not None and stop_event.is_set()

	def _on_ros_encrypt_level_change(new_level: int) -> None:
		ros_level_queue.put(new_level)

	def _record_device_error(device: str | None) -> None:
		if not device:
			return
		count = error_counts.get(device, 0) + 1
		error_counts[device] = count
		if count > THRESHOLD_ERR_COUNT and device not in error_logged:
			try:
				with error_log_path.open("a", encoding="utf-8") as handle:
					handle.write(f"{device}\n")
				error_logged.add(device)
			except Exception as exc:
				logging.warning("Failed to record device error for %s: %s", device, exc)

	def _build_sig_config(device: str, site: CurrentSite) -> RxConfig:
		return RxConfig(
			device=device,
			type="sig",
			center_freq=FC_RED if site == CurrentSite.RED else FC_BLUE,
			discriminator_gain=GAIN_SIG,
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
			discriminator_gain=gain_map[level],
		)

	def _worker_thread(
		name: str,
		rx_config: RxConfig,
		stop_event: threading.Event,
		on_decoded: Callable[[list], None] | None,
		qt_app: ScrollChartsApp | None,
		ros_queue: Queue[list[dict]],
	):
		try:
			with status_lock:
				thread_status[name] = "running"
			work(
				rx_config,
				search_timeout=device_search_timeout,
				stop_event=stop_event,
				on_decoded=on_decoded,
				qt_app=qt_app,
				visualize_on=VISUALIZE_ON,
				ros_publish_queue=ros_queue,
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

	def _clear_worker_queues(worker_name: str) -> None:
		other_errors: list[tuple[str, Exception]] = []
		try:
			while True:
				name, exc = exception_queue.get_nowait()
				if name != worker_name:
					other_errors.append((name, exc))
		except Empty:
			pass
		finally:
			for item in other_errors:
				exception_queue.put(item)

		other_decodes: list[tuple[str, float]] = []
		try:
			while True:
				name, ts = last_decode_time_queue.get_nowait()
				if name != worker_name:
					other_decodes.append((name, ts))
		except Empty:
			pass
		finally:
			for item in other_decodes:
				last_decode_time_queue.put(item)

	def _start_worker(name: str, rx_config: RxConfig) -> None:
		_clear_worker_queues(name)
		print(f"Starting worker {name} with device {rx_config.device}...")
		logging.log(logging.INFO, f"Starting worker {name} with device {rx_config.device}...")
		stop_event = threading.Event()
		qt_app = qt_apps.get(name) if VISUALIZE_ON else None

		def _on_decoded(_frames: list) -> None:
			last_decode_time_queue.put((name, time.time()))

		thread = threading.Thread(
			target=_worker_thread,
			name=name,
			args=(name, rx_config, stop_event, _on_decoded, qt_app, ros_publish_queue),
			daemon=False,
		)
		with status_lock:
			thread_threads[name] = thread
			thread_stop_events[name] = stop_event
			thread_devices[name] = rx_config.device
			thread_status[name] = "starting"
			last_decode_time[name] = time.time()
			restart_attempted.setdefault(name, False)
		thread.start()

	def _stop_worker(name: str, join_timeout: float = TIMEOUT_STOP_WORKER_JOIN) -> bool:
		print(f"Stopping worker {name}...")
		logging.log(logging.INFO, f"Stopping worker {name}...")
		with status_lock:
			stop_event = thread_stop_events.get(name)
			thread = thread_threads.get(name)
			device = thread_devices.get(name)
		if stop_event is not None:
			stop_event.set()
		if thread is not None:
			thread.join(timeout=join_timeout)
			if thread.is_alive() and device and device != "rtlsdr":
				_force_release_pluto(device)
				thread.join(timeout=join_timeout)
			return not thread.is_alive()
		return True

	def _ensure_worker_stopped(name: str, total_timeout: float = TIMEOUT_ENSURE_WORKER_STOPPED) -> bool:
		stopped = _stop_worker(name)
		if stopped:
			return True
		deadline = time.time() + total_timeout
		while time.time() < deadline:
			with status_lock:
				thread = thread_threads.get(name)
			if thread is None or not thread.is_alive():
				return True
			thread.join(timeout=1)
		return False


	def _force_release_pluto(serial: str, retries: int = 2) -> bool:
		for _ in range(retries):
			try:
				usb_name = query_device_addr(RxConfig(device=serial, type="sig" if serial == devices.device_sig else "inf")) # 这里的type其实无所谓
				if usb_name is None:
					return False
				sdr = adi.Pluto(usb_name)
				for attr in ("tx_destroy_buffer", "rx_destroy_buffer"):
					fn = getattr(sdr, attr, None)
					if callable(fn):
						try:
							fn()
						except Exception:
							pass
				del sdr
				gc.collect()
				return True
			except Exception as exc:
				logging.warning("force release pluto failed for %s: %s", serial, exc)
				time.sleep(0.2)
		return False

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
			if _should_stop():
				return False, None
			try:
				while True:
					name, ts = last_decode_time_queue.get_nowait()
					with status_lock:
						last_decode_time[name] = ts
						restart_attempted[name] = False
					if name == worker_name:
						print(f"Worker {name} reported successful decode")
						logging.log(logging.INFO, f"Worker {name} reported successful decode")
						return True, None
			except Empty:
				pass

			other_errors: list[tuple[str, Exception]] = []
			try:
				while True:
					name, exc = exception_queue.get_nowait()
					if name == worker_name:
						print(f"Worker {name} reported error: {exc}")
						logging.log(logging.INFO, f"Worker {name} reported error: {exc}")
						return False, exc
					other_errors.append((name, exc))
			except Empty:
				pass
			finally:
				for item in other_errors:
					exception_queue.put(item)

			time.sleep(0.05)
		if time.time() - start_time < timeout_sec:
			print(f"Timeout waiting for decode from {worker_name}, timeout after {time.time() - start_time:.2f} seconds")
			logging.log(logging.INFO, f"Timeout waiting for decode from {worker_name}, timeout after {time.time() - start_time:.2f} seconds")
		return False, None

	def _get_faction_with_timeout(
		node: WirelessRos2AdaptorNodeThreaded,
		timeout_sec: float,
	) -> Faction:
		start_time = time.time()
		while time.time() - start_time < timeout_sec:
			faction = node.get_faction(timeout=faction_timeout)
			if faction in (Faction.RED, Faction.BLUE) or _should_stop():
				return faction
		return faction

	def _probe_faction_site(site: CurrentSite) -> CurrentSite | None:
		primary_device = devices.device_sig
		backup_device = (
			devices.device_backup
			if devices.device_backup and devices.device_backup != primary_device
			else None
		)
		logging.info("Probing faction candidate: %s (primary=%s, backup=%s)", site.name, primary_device, backup_device)
		print(f"Probing faction candidate: {site.name} (primary={primary_device}, backup={backup_device})")

		rx_conf_sig = _build_sig_config(primary_device, site)
		_start_worker("rx_sig", rx_conf_sig)
		decoded, error = _wait_for_decode_or_error("rx_sig", inf_level_timeout)
		stopped = _ensure_worker_stopped("rx_sig")
		with status_lock:
			worker_failed = thread_status.get("rx_sig") == "error"
		primary_failed = (error is not None) or worker_failed
		if not stopped:
			logging.warning("rx_sig did not stop cleanly; skipping probe for %s", site.name)
			return None
		if decoded:
			return site

		if primary_failed and backup_device is not None:
			print(
				f"Primary device {primary_device} failed for {site.name}, switching to backup device {backup_device}..."
			)
			logging.info(
				"Primary device %s failed for %s, switching to backup device %s",
				primary_device,
				site.name,
				backup_device,
			)
			rx_conf_sig = _build_sig_config(backup_device, site)
			_start_worker("rx_sig", rx_conf_sig)
			decoded, _ = _wait_for_decode_or_error("rx_sig", inf_level_timeout)
			stopped = _ensure_worker_stopped("rx_sig")
			if not stopped:
				logging.warning("rx_sig did not stop cleanly; skipping backup probe for %s", site.name)
				return None
			if decoded:
				return site

		return None
	
	# 尝试使用ros获取当前阵营信息
	current_site: CurrentSite | None = None
	ros_node = None
	try:
		ros_node = WirelessRos2AdaptorNodeThreaded(
			on_encrypt_level_change_callback=_on_ros_encrypt_level_change,
			node_name="main_node",
		)
		ros_node.start()
		print("ROS2 main node started")
		logging.info("ROS2 main node started")
		faction = _get_faction_with_timeout(ros_node, faction_timeout)
		print(f"Got faction from ROS node: {faction}")
		logging.log(logging.INFO, f"Got faction from ROS node: {faction}")
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
	except Exception as exc:
		ros_node = None
		print("ROS2 main node unavailable: %s", exc)
		logging.error("ROS2 main node unavailable: %s", exc)

	# 若未成功获取阵营信息（超时），则尝试对红蓝方信息波进行解调，成功则确定当前阵营信息
	# 反复轮询尝试，包括主设备故障时启用备用设备的逻辑，直到成功解析才会往下走
	if current_site is None:
		print("Attempting to determine faction from signal decoding...")
		logging.log(logging.INFO, "Attempting to determine faction from signal decoding...")
		while True:
			if _should_stop():
				return
			for site in (CurrentSite.RED, CurrentSite.BLUE):
				if _should_stop():
					return
				probe_result = _probe_faction_site(site)
				if probe_result is not None:
					current_site = probe_result
					break
			if current_site is not None:
				logging.log(logging.INFO, "Determined faction from signal decoding: %s", current_site.name)
				print(f"Determined faction from signal decoding: {current_site.name}")
				break

	# 接收设备配置
	inf_level = 1
	rx_conf_sig = _build_sig_config(devices.device_sig, current_site)
	rx_conf_inf = _build_inf_config(inf_level, devices.device_inf, current_site)

	# 开始发射干扰波
	# if SIGNAL_TX_ON:
	# 	tx_ctrl(tx_config_1)

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
		# 先清空当前消息队列
		_clear_worker_queues("rx_sig")
		_clear_worker_queues("rx_inf")
		
		while True:
			if _should_stop():
				break
			# 处理子线程上报的 ROS 发布消息
			if ros_node is not None:
				try:
					while True:
						data_dict = ros_publish_queue.get_nowait()
						_publish_ros_messages(ros_node, data_dict)
				except Empty:
					pass
			else:
				try:
					while True:
						ros_publish_queue.get_nowait()
				except Empty:
					pass
			# 更新解析时间
			try:
				while True:
					name, ts = last_decode_time_queue.get_nowait()
					with status_lock:
						last_decode_time[name] = ts
						restart_attempted[name] = False
			except Empty:
				pass

			# 每两轮操作设备起停设置一个时间间隔，避免过于频繁地切换设备
			if time.time() - last_device_ctrl_time >= 2 * main_cycle_device_ctrl_interval:

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
						_record_device_error(current_device)
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
							stopped = _ensure_worker_stopped("rx_inf")
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
							stopped = _ensure_worker_stopped("rx_inf")
							if stopped:
								inf_level = 1 if inf_level >= 3 else inf_level + 1
								rx_conf_inf = _build_inf_config(inf_level, inf_device, current_site)
								_start_worker("rx_inf", rx_conf_inf)
								logging.info("rx_inf switched to next level %d due to timeout", inf_level)
								print(f"rx_inf switched to next level {inf_level} due to timeout")

				# 在处理完所有报错后，对于未在正常工作的线程尝试执行一次启动
				with status_lock:
					rx_sig_thread = thread_threads.get("rx_sig")
					rx_inf_thread = thread_threads.get("rx_inf")
					rx_sig_running = rx_sig_thread is not None and rx_sig_thread.is_alive()
					rx_inf_running = rx_inf_thread is not None and rx_inf_thread.is_alive()
				if not rx_sig_running:
					logging.log(logging.INFO, "rx_sig is not running, attempting to restart...")
					print("rx_sig is not running, attempting to restart...")
					_start_worker("rx_sig", rx_conf_sig)
				if not rx_inf_running:
					logging.log(logging.INFO, "rx_inf is not running, attempting to restart...")
					print("rx_inf is not running, attempting to restart...")
					_start_worker("rx_inf", rx_conf_inf)

				# 更新设备控制时间戳
				last_device_ctrl_time = time.time()

			time.sleep(main_cycle_update_interval)
	finally:
		with status_lock:
			worker_names = list(thread_threads.keys())
		for name in worker_names:
			_stop_worker(name)
		if ros_node is not None:
			ros_node.stop()


def query_device_addr(rx_config: RxConfig) -> str:
	# 先尝试从已获取到的usb地址中找到对应序列号的设备，避免重复搜索
	device = rx_config.device
	if device == "rtlsdr":
		print("Using RTL-SDR device, no need to query USB address.")
		logging.log(logging.INFO, "Using RTL-SDR device, no need to query USB address.")
		return None
	if rx_config.device == device_conf.device_sig:
		addr = device_conf.device_sig_addr
	elif rx_config.device == device_conf.device_inf:
		addr = device_conf.device_inf_addr
	else:
		addr = device_conf.device_backup_addr

	if addr is not None:
		print(f"Using cached USB address for {device}: {addr}")
		logging.log(logging.INFO, f"Using cached USB address for {device}: {addr}")
		return addr

	devices = get_all_pluto_devices(timeout=TIMEOUT_DEVICE_SEARCH)
	print(f"Found Pluto devices: {devices}")
	logging.log(logging.INFO, f"Found Pluto devices: {devices}")
	serial = device
	usb_name = get_pluto_usb_by_serial(devices, serial)
	if usb_name is None:
		raise ValueError(
			f"Pluto device not found for serial {serial}. "
			"Check iio_info -s output and USB connection."
		)
	else:
		# 将找到的地址缓存起来，避免下次重复搜索
		if rx_config.device == device_conf.device_sig:
			device_conf.device_sig_addr = usb_name
		elif rx_config.device == device_conf.device_inf:
			device_conf.device_inf_addr = usb_name
		else:
			device_conf.device_backup_addr = usb_name
	return usb_name

def work(
	rx_config:RxConfig,
	stop_event: threading.Event | None = None,
	on_decoded: Callable[[list], None] | None = None,
	qt_app: ScrollChartsApp | None = None,
	visualize_on: bool = VISUALIZE_ON,
	ros_publish_queue: Queue[list[dict]] | None = None,
) -> None:
	"""
	接收信号线程
	包括硬件控制 信号处理 发送ros信息 可视化
	"""
	visualize_on = bool(visualize_on and qt_app is not None)

	device = rx_config.device
	if device != "rtlsdr": # 使用pluto 需要先用序列号提取对应的iio_context的usb标识
		usb_name = query_device_addr(rx_config)
			
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

	decoder_type = "signal" if rx_config.type == "sig" else "jamming" if rx_config.type == "inf" else rx_config.type
	decoder = frame_decoder_direct(
		type=decoder_type,
		on_frame_decoded=_build_ros_queue_callback(ros_publish_queue) if ros_publish_queue else None,
		crc16_enabled=True,
	)

	logging.log(logging.INFO, f"Worker started with config: {rx_config}")
	print(f"Worker started with config: {rx_config}")

	try:
		record_file = None
		try:
			if RECORD_SIGNAL_ON:
				timestamp = time.strftime("%Y%m%d_%H%M%S")
				filename = f"record_{rx_config.type}_{rx_config.center_freq}_{timestamp}.iq"
				print(f"Recording signal to {filename}")
				record_file = open(filename, "wb")
				logging.log(logging.INFO, f"Recording signal to {filename}")
				print(f"Recording signal to {filename}")
			while True:
				# 线程退出逻辑
				if stop_event is not None and stop_event.is_set():
					rx_ctrl.close() if device != "rtlsdr" else None
					break
				samples = rx_ctrl.rx()
				if record_file is not None and samples is not None:
					samples.tofile(record_file)
				if samples is None:
					time.sleep(0.01)
					continue

				pre_taps = TAPS_LPF_PRE if rx_config.type == "sig" else (
					TAPS_LPF_PRE_1 if rx_config.type == "inf" and rx_config.center_freq in (FC_RED_1, FC_BLUE_1) else (
						TAPS_LPF_PRE_2 if rx_config.type == "inf" and rx_config.center_freq in (FC_RED_2, FC_BLUE_2) else 
						TAPS_LPF_PRE_3
					)
				)
				bits, decoded_frames = process_chunk(
					samples=samples,
					pre_taps=pre_taps,
					post_taps=TAPS_LPF,
					discriminator=discriminator,
					symbol_sync=symbol_sync,
					decoder=decoder,
					qt_app=qt_app,
					visualize_on=visualize_on,
				)

				if bits.size == 0:
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
		try:
			close_fn = getattr(rx_ctrl, "close", None)
			if callable(close_fn):
				close_fn()
		except Exception:
			pass

# 用于发射信号的全局sdr对象
sdr = None

def tx_ctrl(tx_config: SigTxConfig) -> None:
	global sdr
	if sdr is not None:
		sdr.tx_destroy_buffer()
	else:
		usb_name = query_device_addr(RxConfig(device=device_conf.device_inf, type="inf"))
		sdr = adi.Pluto(usb_name)

	if not tx_config.iq_file:
		raise ValueError("iq_file is required for tx_sig")

	sdr.sample_rate = int(tx_config.sample_rate)
	sdr.tx_rf_bandwidth = int(tx_config.sample_rate)
	sdr.tx_lo = int(tx_config.center_freq)
	sdr.tx_hardwaregain_chan0 = int(0.0)
	sdr.tx_cyclic_buffer = True
	

	sample_count = int(tx_config.num_samps)
	samples = np.fromfile(tx_config.iq_file, dtype=np.complex64, count=sample_count)
	if samples.size == 0:
		raise ValueError(f"No samples loaded from {tx_config.iq_file}")
	if samples.size < sample_count:
		logging.warning(
			"Requested %d samples but only %d available in %s",
			sample_count,
			samples.size,
			tx_config.iq_file,
		)
	sdr.tx_buffer_size = int(samples.size)
	samples *= 2 ** 14
	sdr.tx(samples)
	print("Started transmitting signal from file: %s", tx_config.iq_file)
	logging.log(logging.INFO, "Started transmitting signal from file: %s", tx_config.iq_file)

if __name__ == "__main__":
	LOG_FILE_PATH = CURRENT_DIR / f"main_rx_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=LOG_FILE_PATH, filemode='w')

	if SIGNAL_TX_ON:
		tx_ctrl(tx_config)

	if VISUALIZE_ON:
		app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
		qt_apps = {
			"rx_sig": ScrollChartsApp(qt_gui_configs, uniform_height=320),
			"rx_inf": ScrollChartsApp(qt_gui_configs, uniform_height=320),
		}
		qt_apps["rx_sig"].window.setWindowTitle("rx_sig")
		qt_apps["rx_inf"].window.setWindowTitle("rx_inf")
		qt_apps["rx_sig"].show()
		qt_apps["rx_inf"].show()

		stop_event = threading.Event()
		
		app.aboutToQuit.connect(stop_event.set)

		main_thread = threading.Thread(
			target=main,
			args=(device_conf,),
			kwargs={"qt_apps": qt_apps, "stop_event": stop_event},
			daemon=False,
		)
		main_thread.start()
		try:
			app.exec_()
		except KeyboardInterrupt:
			stop_event.set()
			app.quit()
		finally:
			stop_event.set()
			main_thread.join(timeout=3.0)
	else:
		stop_event = threading.Event()
		try:
			main(device_conf, stop_event=stop_event)
		except KeyboardInterrupt:
			stop_event.set()