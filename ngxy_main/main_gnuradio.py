#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# amplifier: 给原本用作backup的板子接上amplifier，当backup空闲且当前等级已经为三级时，使用amplifier支路尝试进行解析
# 为了避免潜在的串口通信问题，每次检验Queue中重复信息，重复信息直接丢弃

# 选项
RECORD_SIGNAL_ON = True

# 参数
NUM_SAMPS = 4e4
TIMEOUT_DEVICE_SEARCH = 15
INTERVAL_MAIN_CYCLE = 0.02
TIMEOUT_ROS_FACTION_QUERY = 10000 # 不主动搜索阵营
# TIMEOUT_ROS_FACTION_QUERY = 3
INTERVAL_MAIN_CYCLE_DEVICE_CTRL = 12
TIMEOUT_FACTION_SHARCH = 5
# TIMEOUT_FACTION_SHARCH = 10000 # always red
# TIMEOUT_INF_LEVEL = 10000 # 不主动搜索干扰等级
# TIMEOUT_INF_LEVEL = 20
TIMEOUT_INF_LEVEL = 10000 # 不主动搜索干扰等级
INTERVAL_IIO_INFO = 15
TIMEOUT_JOIN = 2
# keep lv1时 剩余时间与基地血量的升级条件
THRES_REMAINING_TIME_SEC = 120
THRES_BASE_HP = 2000
KEEP_LV1_ON = False

SEND_KEY_MAX_FPS = 1
ZMQ_ADDR_SIG = "tcp://127.0.0.1:2236"
ZMQ_ADDR_INF = "tcp://127.0.0.1:2235"

# 设备配置
from dataclasses import dataclass
@dataclass
class DeviceConfig:
	device_sig: str
	device_inf: str
	device_backup: str
	device_sig_addr: str | None
	device_inf_addr: str | None
	device_backup_addr: str | None

from extract_usb import *
device_conf = DeviceConfig(
	device_sig=SERIAL_PLUTO_NANO_2,
	device_inf=SERIAL_PLUTO_NANO_1,	
	# device_inf=SERIAL_PLUTO_SDR,
	device_backup=SERIAL_PLUTO_NANO_0,
	device_sig_addr=None,
	device_inf_addr=None,
	device_backup_addr=None,
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


from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
	sys.path.insert(0, str(CURRENT_DIR))

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
	sys.path.insert(0, str(WORKSPACE_ROOT))

import argparse
from enum import Enum
import json
import time
import threading
from queue import Queue, Empty
import logging
from util import _log, _makesure_path_exist

import rclpy

from def_signal import *
BW_SIG /= 2
BW_1 /= 2
BW_2 /= 2
BW_3 /= 2
from def_taps import *
import region_games
from frame_decoder_zmq import frame_decoder_zmq
from wireless_ros2_adaptor import WirelessRos2AdaptorNodeThreaded, Faction

region_games.VISUALIZE_ON = False


def _json_default(value):
	if isinstance(value, Enum):
		return value.value
	if isinstance(value, (bytes, bytearray)):
		return list(value)
	return str(value)


def _publish_ros_messages(ros_node, data_dict: dict) -> None:
	json_str = json.dumps(data_dict, default=_json_default, ensure_ascii=False)
	_log(logging.INFO, f"Publishing ROS2 message: {json_str}")
	ros_node.publish_wireless_result(json_str)


def _build_sig_params(site: CurrentSite) -> tuple[float, float, object]:
	center_freq = FC_RED if site == CurrentSite.RED else FC_BLUE
	return center_freq, BW_SIG, TAPS_LPF_PRE


def _build_inf_params(level: int, site: CurrentSite) -> tuple[float, float, object]:
	if site == CurrentSite.RED:
		freq_map = {1: FC_RED_1, 2: FC_RED_2, 3: FC_RED_3}
	else:
		freq_map = {1: FC_BLUE_1, 2: FC_BLUE_2, 3: FC_BLUE_3}
	bw_map = {1: BW_1, 2: BW_2, 3: BW_3}
	taps_map = {1: TAPS_LPF_PRE_1, 2: TAPS_LPF_PRE_2, 3: TAPS_LPF_PRE_3}
	if level not in freq_map:
		_log(logging.WARNING, f"level{level}is not valid")
		return freq_map[1], bw_map[1], taps_map[1]
	return freq_map[level], bw_map[level], taps_map[level]


def _clear_cached_device_addr(device: str) -> None:
	if device == device_conf.device_sig:
		device_conf.device_sig_addr = None
	elif device == device_conf.device_inf:
		device_conf.device_inf_addr = None
	else:
		device_conf.device_backup_addr = None


def _cache_all_device_addrs(devices: list[tuple[str, str]]) -> None:
	device_lookup = {serial.lower(): usb_addr for serial, usb_addr in devices}
	device_conf.device_sig_addr = device_lookup.get(device_conf.device_sig.lower())
	device_conf.device_inf_addr = device_lookup.get(device_conf.device_inf.lower())
	device_conf.device_backup_addr = device_lookup.get(device_conf.device_backup.lower())


def query_device_addr(device: str, force_refresh: bool = False) -> str | None:
	"""进行usb地址查询 优先使用缓存过的 可能返回None"""
	global last_get_iio_info_time
	if device == "rtlsdr":
		_log(logging.WARNING, "RTL-SDR is not supported by region_games flowgraph.")
		return None

	if device == device_conf.device_sig:
		cached_addr = device_conf.device_sig_addr
	elif device == device_conf.device_inf:
		cached_addr = device_conf.device_inf_addr
	else:
		cached_addr = device_conf.device_backup_addr
		
	if force_refresh:
		_clear_cached_device_addr(device)
		cached_addr = None

	if cached_addr is not None:
		_log(logging.INFO, f"Using cached USB address for {device}: {cached_addr}")
		return cached_addr

	if (not force_refresh) and (time.time() - last_get_iio_info_time < INTERVAL_IIO_INFO):
		_log(logging.INFO, "iio_info query too frequent")
		return None
	devices = get_all_pluto_devices(timeout=TIMEOUT_DEVICE_SEARCH)
	last_get_iio_info_time = time.time()
	_cache_all_device_addrs(devices)
	_log(logging.INFO, f"Found Pluto devices: {devices}")
	usb_name = get_pluto_usb_by_serial(devices, device)
	if usb_name is None:
		_log(logging.WARNING,f"Pluto device not found for serial {device}. ")
	return usb_name


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser()
	parser.add_argument("--keep-lv1", action=argparse.BooleanOptionalAction, default=False, help="保持一级不自动升级")
	return parser


def apply_cli_args(args: argparse.Namespace) -> None:
	global KEEP_LV1_ON
	KEEP_LV1_ON = bool(args.keep_lv1)
	if KEEP_LV1_ON:
		_log(logging.INFO, "Keeping level 1 for inf device as per CLI argument")

def main(
	devices: DeviceConfig,
	inf_level_timeout=TIMEOUT_INF_LEVEL,
	main_cycle_update_interval=INTERVAL_MAIN_CYCLE,
	faction_timeout=TIMEOUT_ROS_FACTION_QUERY,
	stop_event: threading.Event | None = None,
	main_cycle_device_ctrl_interval=INTERVAL_MAIN_CYCLE_DEVICE_CTRL,
) -> None:
	# 初始化ROS
	if not rclpy.ok():
		rclpy.init(args=None)

	status_lock = threading.Lock()
	process_wrappers: dict[str, object] = {}
	process_devices: dict[str, str] = {}
	restart_attempted: dict[str, bool] = {}
	last_decode_time: dict[str, float] = {}
	decoder_objects: dict[str, frame_decoder_zmq] = {}
	ros_level_queue: Queue[int] = Queue()
	ros_publish_queue: Queue[dict] = Queue()
	last_device_ctrl_time = 0.0
	current_site: CurrentSite | None = None
	ros_node = None
	main_device_map = {
		"rx_sig": devices.device_sig,
		"rx_inf": devices.device_inf,
	}
	# 将多次故障设备记录下来
	error_counts: dict[str, int] = {}
	error_logged: set[str] = set()
	error_log_path = CURRENT_DIR / "error"
	for device in (devices.device_sig, devices.device_inf, devices.device_backup):
		if device:
			error_counts.setdefault(device, 0)
	# 已为三级干扰的标志
	is_level_3 = False

	def _should_stop() -> bool:
		return stop_event is not None and stop_event.is_set()

	def _on_ros_encrypt_level_change(new_level: int) -> None:
		ros_level_queue.put(new_level)
		if new_level == 3:
			nonlocal is_level_3
			is_level_3 = True

	def _record_device_error(device: str | None) -> None:
		if not device:
			return
		count = error_counts.get(device, 0) + 1 
		if count > 5 and device not in error_logged:
			try:
				const_name = None
				for name, val in globals().items():
					if name.startswith("SERIAL_") and val == device:
						const_name = name
						break
				to_write = const_name if const_name is not None else device
				with error_log_path.open("a", encoding="utf-8") as handle:
					handle.write(f"{time.time()},{to_write}\n")
				error_logged.add(device)
			except Exception as exc:
				_log(logging.WARNING, f"Failed to record device error for {device}: {exc}")

	def _build_sig_config(device: str, site: CurrentSite) -> tuple[str, float, float, object, str]:
		center_freq, bandwidth, taps_pre = _build_sig_params(site)
		return device, center_freq, bandwidth, taps_pre, ZMQ_ADDR_SIG

	def _build_inf_config(level: int, device: str, site: CurrentSite) -> tuple[str, float, float, object, str]:
		center_freq, bandwidth, taps_pre = _build_inf_params(level, site)
		return device, center_freq, bandwidth, taps_pre, ZMQ_ADDR_INF

	def _process_alive(name: str) -> bool:
		with status_lock:
			wrapper = process_wrappers.get(name)
		if wrapper is None:
			return False
		process = getattr(wrapper, "process", None)
		return process is not None and process.is_alive()

	def _backup_in_use_by() -> str | None:
		with status_lock:
			for name, device in process_devices.items():
				wrapper = process_wrappers.get(name)
				process = getattr(wrapper, "process", None)
				if process is not None and process.is_alive() and device == devices.device_backup:
					return name
		return None

	def _stop_process(name: str, join_timeout: float = TIMEOUT_JOIN) -> bool:
		with status_lock:
			wrapper = process_wrappers.get(name)
		if wrapper is None:
			return True
		stop_fn = getattr(wrapper, "stop", None)
		if callable(stop_fn):
			try:
				stop_fn(timeout=join_timeout, force_kill=True)
			except Exception as exc:
				_log(logging.WARNING, f"Failed to stop {name} cleanly with timeout args: {exc}")
				process = getattr(wrapper, "process", None)
				if process is not None:
					try:
						stop_event = getattr(wrapper, "_stop_event", None)
						if stop_event is not None:
							stop_event.set()
						process.join(timeout=join_timeout)
						if process.is_alive():
							process.terminate()
							process.join(timeout=join_timeout)
					except Exception:
						pass
		return not _process_alive(name)

	def _ensure_process_stopped(name: str, total_timeout: float = TIMEOUT_JOIN) -> bool:
		stopped = _stop_process(name)
		if stopped:
			return True
		deadline = time.time() + total_timeout
		while time.time() < deadline:
			if not _process_alive(name):
				return True
			time.sleep(0.1)
		return False

	def _build_decoder_callback(name: str, decoder_type: str, keep_lv1_on):
		def _on_frame_decoded(data_dict_list: list[dict]) -> None:
			now = time.time()
			with status_lock:
				last_decode_time[name] = now
				restart_attempted[name] = False
			# 保持一级逻辑 若为干扰波解析器且_levelup_decicer返回False 则不进行上传
			if decoder_type == "jamming" and not _levelup_decider(ros_node, keep_lv1_on):
				pass
			else:
				for data_dict in data_dict_list:
					ros_publish_queue.put(data_dict)

		return _on_frame_decoded

	def _start_decoder(name: str, zmq_addr: str, decoder_type: str) -> None:
		with status_lock:
			decoder = decoder_objects.get(name)
			if decoder is not None:
				return
			emit_max_fps = SEND_KEY_MAX_FPS if decoder_type == "jamming" else None
			decoder_objects[name] = frame_decoder_zmq(
				type=decoder_type,
				zmq_address=zmq_addr,
				on_frame_decoded=_build_decoder_callback(name, decoder_type, KEEP_LV1_ON),
				crc16_enabled=True,
				emit_max_fps=emit_max_fps,
			)
			_log(logging.INFO, f"Started {name} [{decoder_type}] decoder thread with ZMQ address {zmq_addr}")

	def _start_process(name: str, device_serial: str, site: CurrentSite, level: int = 1) -> bool:
		if _should_stop():
			return False
		_stop_process(name)
		if name in ("rx_sig", "rs_sig_amplifier"):
			device_serial, center_freq, bandwidth, taps_pre, zmq_addr = _build_sig_config(device_serial, site)
		else:
			device_serial, center_freq, bandwidth, taps_pre, zmq_addr = _build_inf_config(level, device_serial, site)
		_log(logging.INFO, f"Starting {name} with device {device_serial} at freq {center_freq} Hz, bandwidth {bandwidth} Hz, level {level}")
		pluto_addr = query_device_addr(device_serial)
		if pluto_addr is None:
			_log(logging.WARNING, f"No USB address for {name} on {device_serial}, forcing iio_info refresh")
			pluto_addr = query_device_addr(device_serial, force_refresh=True)
			if pluto_addr is None:
				_record_device_error(device_serial)
				return False
		filename = None
		if RECORD_SIGNAL_ON:
			filename = f"rec/{name}_{center_freq}_{time.strftime('%Y-%m-%d_%H-%M-%S')}.iq"

		def _launch_with_addr(addr: str):
			wrapper = region_games.top_thread_wrapper(
				zmq_addr,
				addr,
				center_freq,
				bandwidth,
				TAPS_LPF,
				taps_pre,
				filename,
				NUM_SAMPS,
			)
			try:
				wrapper.start()
			except Exception as exc:
				_log(logging.WARNING, f"Failed to start {name} on {device_serial} ({addr}): {exc}")
				return None
			time.sleep(0.2)
			if not wrapper.is_alive():
				_log(logging.WARNING, f"{name} exited immediately after start on {device_serial} ({addr})")
				return None
			return wrapper

		wrapper = _launch_with_addr(pluto_addr)
		if wrapper is None:
			_log(logging.WARNING, f"Retrying {name} with refreshed USB address for {device_serial}")
			fresh_addr = query_device_addr(device_serial, force_refresh=True)
			if fresh_addr is None:
				_record_device_error(device_serial)
				return False
			wrapper = _launch_with_addr(fresh_addr)
			if wrapper is None:
				_record_device_error(device_serial)
				return False
		with status_lock:
			process_wrappers[name] = wrapper
			process_devices[name] = device_serial
			last_decode_time[name] = time.time()
			restart_attempted.setdefault(name, False)
		return True

	def _wait_for_decode_or_process_dead(worker_name: str, timeout_sec: float) -> bool:
		start_time = time.time()
		while time.time() - start_time < timeout_sec:
			if _should_stop():
				return False, None
			with status_lock:
				last_time = last_decode_time.get(worker_name, 0.0)
			if last_time >= start_time:
				return True, None
			if not _process_alive(worker_name):
				return False, "err"
			time.sleep(0.05)
		return False, None

	def _get_faction_with_timeout(node: WirelessRos2AdaptorNodeThreaded, timeout_sec: float) -> Faction | None:
		start_time = time.time()
		faction = None
		while time.time() - start_time < timeout_sec:
			faction = node.get_faction(timeout=timeout_sec)
			if faction in (Faction.RED, Faction.BLUE) or _should_stop():
				return faction
		return faction

	def _probe_faction_site(site: CurrentSite) -> CurrentSite | None:
		primary_device = devices.device_inf
		backup_device = devices.device_backup if devices.device_backup and devices.device_backup != primary_device else None
		_log(logging.INFO, f"Probing faction candidate: {site.name} (primary={primary_device}, backup={backup_device})")

		if not _start_process("rx_inf", primary_device, site):
			_record_device_error(primary_device)
			if backup_device is not None and _start_process("rx_inf", backup_device, site, level=1):
				_log(logging.INFO, f"Primary device {primary_device} produced err, switching to backup device {backup_device}")
				decoded, err = _wait_for_decode_or_process_dead("rx_inf", TIMEOUT_FACTION_SHARCH)
				_ensure_process_stopped("rx_inf")
				if decoded:
					return site
				_record_device_error(backup_device)
			return None

		decoded, err = _wait_for_decode_or_process_dead("rx_inf", TIMEOUT_FACTION_SHARCH)
		stopped = _ensure_process_stopped("rx_inf")
		if decoded:
			return site
		if not stopped:
			_log(logging.WARNING, f"rx_inf did not stop cleanly; retrying probe for {site.name}")

		if backup_device is not None and err:
			_log(logging.INFO, f"Primary device {primary_device} produced err, switching to backup device {backup_device}")
			if _start_process("rx_inf", backup_device, site, level=1):
				decoded, err = _wait_for_decode_or_process_dead("rx_inf", TIMEOUT_FACTION_SHARCH)
				_ensure_process_stopped("rx_inf")
				if decoded:
					return site
				_record_device_error(backup_device)
		return None
	
	def _levelup_decider(ros_node: WirelessRos2AdaptorNodeThreaded, keep_lv1_on) -> bool:
		"""根据KEEP_LV1_ON和ROS查询得到的剩余时间与基地血量决定是否升级"""
		if keep_lv1_on:
			if ros_node.get_remaining_seconds() > THRES_REMAINING_TIME_SEC and ros_node.get_alley_base_HP() > THRES_BASE_HP:
				return True
			return False
		else:  # 不开启升级
			return True

	# ----------------------------
	# 启动decoder
	_start_decoder("rx_sig", ZMQ_ADDR_SIG, "signal")
	_start_decoder("rx_inf", ZMQ_ADDR_INF, "jamming")

	# 尝试ros获取阵营信息
	try:
		ros_node = WirelessRos2AdaptorNodeThreaded(
			on_encrypt_level_change_callback=_on_ros_encrypt_level_change,
			node_name="main_node",
		)
		ros_node.start()
		_log(logging.INFO, "ROS2 main node started")
		faction = _get_faction_with_timeout(ros_node, faction_timeout)
		_log(logging.INFO, f"Got faction from ROS node: {faction}")
		if faction == Faction.RED:
			current_site = CurrentSite.RED
			_log(logging.INFO, "Determined faction from ROS node: RED")
		elif faction == Faction.BLUE:
			current_site = CurrentSite.BLUE
			_log(logging.INFO, "Determined faction from ROS node: BLUE")
		else:
			_log(logging.WARNING, f"Failed to determine faction from ROS node, got: {faction}")
	except Exception as exc:
		ros_node = None
		_log(logging.ERROR, f"ROS2 main node unavailable: {exc}")

	# ros获取阵营信息失败 尝试解干扰波获取阵营信息
	if current_site is None:
		_log(logging.INFO, "Attempting to determine faction from signal decoding...")
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
				_log(logging.INFO, f"Determined faction from signal decoding: {current_site.name}")
				break
			time.sleep(0.5)

	# 正式启动
	inf_level = 1
	if not _start_process("rx_sig", devices.device_sig, current_site):
		if devices.device_backup and devices.device_backup != devices.device_sig:
			_start_process("rx_sig", devices.device_backup, current_site)
	if not _start_process("rx_inf", devices.device_inf, current_site, inf_level):
		if devices.device_backup and devices.device_backup != devices.device_inf:
			_start_process("rx_inf", devices.device_backup, current_site, inf_level)

	_log(logging.INFO, f"Main control started with initial config: rx_sig on {process_devices.get('rx_sig', devices.device_sig)}, rx_inf on {process_devices.get('rx_inf', devices.device_inf)} (inf level {inf_level})")

	try:
		#  刷新ros队列
		ros_publish_queue = Queue()
		while True:
			if _should_stop():
				break

			# 发布ROS信息
			if ros_node is not None:
				# print("====================================")
				# print(ros_publish_queue.qsize())
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
			
			# ROS切换干扰等级逻辑 不受INTERVAL_DEVICE_CTRL的控制
			ros_level_applied = False
			try:
				while True:
					new_level = ros_level_queue.get_nowait()
					# print("====================================")
					# print(f"Received new encrypt level from ROS: {new_level}")
					if new_level in (1, 2, 3) and new_level != inf_level:
						stopped = _ensure_process_stopped("rx_inf")
						if stopped:
							inf_level = new_level
							with status_lock:
								inf_device = process_devices.get("rx_inf", devices.device_inf)
							_start_process("rx_inf", inf_device, current_site, inf_level)
							with status_lock:
								last_decode_time["rx_inf"] = time.time()
							ros_level_applied = True
							_log(logging.INFO, f"rx_inf switched to level {inf_level} due to ROS command")
			except Empty:
				pass

			# 每两轮操作设备起停设置一个时间间隔，避免过于频繁地切换设备
			if time.time() - last_device_ctrl_time >= main_cycle_device_ctrl_interval:
				for name in ("rx_sig", "rx_inf"):
					# 查看当前进程是否存活，存活则继续使用当前设备；不存活则记录错误并尝试切换设备
					if _process_alive(name):
						continue
					# 进程不存活
					# print("============================")
					# print(f"{name}dead")
					with status_lock:
						current_device = process_devices.get(name)
					_record_device_error(current_device)
					backup_owner = _backup_in_use_by()
					# 尝试切换备用设备
					if devices.device_backup and backup_owner is None and current_device != devices.device_backup:
						if name == "rx_inf":
							_start_process("rx_inf", devices.device_backup, current_site, inf_level)
						else:
							_start_process("rx_sig", devices.device_backup, current_site)
							_log(logging.INFO, f"Switched {name} to backup device: {devices.device_backup}")
					# 备用设备被占用 尝试重启一次主要设备
					elif backup_owner is not None and current_device == main_device_map.get(name):
						with status_lock:
							already_tried = restart_attempted.get(name, False)
						if not already_tried:
							with status_lock:
								restart_attempted[name] = True
							if name == "rx_inf":
								_start_process("rx_inf", current_device, current_site, inf_level)
							else:
								_start_process("rx_sig", current_device, current_site)
					# 备用设备出故障 尝试退回主要设备
					elif current_device == devices.device_backup:
						if name == "rx_inf":
							_start_process("rx_inf", main_device_map.get(name), current_site, inf_level)
						else:
							_start_process("rx_sig", main_device_map.get(name), current_site)

				# 当干扰等级达到三级且 backup 空闲时，启动额外的 rs_sig_amplifier 接收通路
				backup_owner = _backup_in_use_by()
				if devices.device_backup and inf_level == 3 and backup_owner is None and not _process_alive("rs_sig_amplifier"):
					if _start_process("rs_sig_amplifier", devices.device_backup, current_site):
						_log(logging.INFO, f"Started rs_sig_amplifier on backup device: {devices.device_backup}")

				# 未解出也未收到ROS指令时的自动切换逻辑
				if not ros_level_applied:
					with status_lock:
						inf_wrapper = process_wrappers.get("rx_inf")
						inf_last = last_decode_time.get("rx_inf", time.time())
						inf_device = process_devices.get("rx_inf", devices.device_inf)
					process = getattr(inf_wrapper, "process", None) if inf_wrapper is not None else None
					if process is not None and process.is_alive():
						if time.time() - inf_last >= inf_level_timeout:
							stopped = _ensure_process_stopped("rx_inf")
							if stopped:
								inf_level = 1 if inf_level >= 2 else inf_level + 1
								_start_process("rx_inf", inf_device, current_site, inf_level)
								_log(logging.INFO, f"rx_inf switched to next level {inf_level} due to timeout")

				#  最后检查一遍是否还是有设备未在运行 如果有则尝试重启
				with status_lock:
					rx_sig_wrapper = process_wrappers.get("rx_sig")
					rx_inf_wrapper = process_wrappers.get("rx_inf")
					rx_sig_running = rx_sig_wrapper is not None and getattr(rx_sig_wrapper, "process", None) is not None and rx_sig_wrapper.process.is_alive()
					rx_inf_running = rx_inf_wrapper is not None and getattr(rx_inf_wrapper, "process", None) is not None and rx_inf_wrapper.process.is_alive()
				if not rx_sig_running:
					_log(logging.INFO, "rx_sig is not running, attempting to restart...")
					_start_process("rx_sig", process_devices.get("rx_sig", devices.device_sig), current_site)
				if not rx_inf_running:
					_log(logging.INFO, "rx_inf is not running, attempting to restart...")
					_start_process("rx_inf", process_devices.get("rx_inf", devices.device_inf), current_site, inf_level)

				last_device_ctrl_time = time.time()
				# 防止过时消息
				ros_publish_queue = Queue()

			time.sleep(main_cycle_update_interval)
	finally:
		with status_lock:
			worker_names = list(process_wrappers.keys())
		for name in worker_names:
			_stop_process(name)
		if ros_node is not None:
			ros_node.stop()

if __name__ == "__main__":
	filename = f"logs/main_rx_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
	filepath = _makesure_path_exist(filename)
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=filepath, filemode='w')

	stop_event = threading.Event()
	try:
		args = build_arg_parser().parse_args()
		apply_cli_args(args)
		main(device_conf, stop_event=stop_event)
	except KeyboardInterrupt:
		stop_event.set()
