#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 选项
RECORD_SIGNAL_ON = True

# 参数
NUM_SAMPS = 4e4
TIMEOUT_DEVICE_SEARCH = 15
INTERVAL_MAIN_CYCLE = 0.02
TIMEOUT_ROS_FACTION_QUERY = 10000 # 不主动搜索阵营
INTERVAL_MAIN_CYCLE_DEVICE_CTRL = 12
TIMEOUT_FACTION_SHARCH = 5
TIMEOUT_INF_LEVEL = 10000 # 不主动搜索干扰等级
INTERVAL_IIO_INFO = 15

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

device_conf = DeviceConfig(
	device_sig=SERIAL_PLUTO_NANO_2,
	device_inf=SERIAL_PLUTO_NANO_1,
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

from enum import Enum
import json
import time
import threading
from queue import Queue, Empty
import logging
from util import _log, _makesure_path_exist

import rclpy

from extract_usb import *
from def_signal import *
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
	print(f"Publishing ROS2 message: {json_str}")
	logging.log(logging.INFO, f"Publishing ROS2 message: {json_str}")
	ros_node.publish_wireless_result(json_str)


def _build_ros_queue_callback(
	ros_queue: Queue[dict],
	name: str,
	last_decode_time: dict[str, float],
	status_lock: threading.Lock,
):
	def _on_frame_decoded(data_dict_list: list[dict]):
		now = time.time()
		with status_lock:
			last_decode_time[name] = now
		for data_dict in data_dict_list:
			ros_queue.put(data_dict)

	return _on_frame_decoded


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


def query_device_addr(device: str) -> str | None:
	"""进行usb地址查询 优先使用缓存过的 可能返回None"""
	if device == "rtlsdr":
		logging.warning("RTL-SDR is not supported by region_games flowgraph.")
		return None

	if device == device_conf.device_sig:
		cached_addr = device_conf.device_sig_addr
	elif device == device_conf.device_inf:
		cached_addr = device_conf.device_inf_addr
	else:
		cached_addr = device_conf.device_backup_addr

	if cached_addr is not None:
		print(f"Using cached USB address for {device}: {cached_addr}")
		logging.log(logging.INFO, f"Using cached USB address for {device}: {cached_addr}")
		return cached_addr

	if time.time() - last_get_iio_info_time < INTERVAL_IIO_INFO:
		_log(logging.INFO, "iio_info query too frequent")
		return None
	devices = get_all_pluto_devices(timeout=TIMEOUT_DEVICE_SEARCH)
	print(f"Found Pluto devices: {devices}")
	logging.log(logging.INFO, f"Found Pluto devices: {devices}")
	usb_name = get_pluto_usb_by_serial(devices, device)
	if usb_name is None:
		_log(logging.WARNING,f"Pluto device not found for serial {device}. ")

	if device == device_conf.device_sig:
		device_conf.device_sig_addr = usb_name
	elif device == device_conf.device_inf:
		device_conf.device_inf_addr = usb_name
	else:
		device_conf.device_backup_addr = usb_name
	return usb_name


def _start_region_top(
	zmq_addr: str,
	device_serial: str,
	center_freq: float,
	bandwidth: float,
	taps_pre,
	filename,
	num_samps=NUM_SAMPS,
) -> region_games.top | None:
	"""不会raise 但可能返回None"""
	pluto_addr = query_device_addr(device_serial)
	if pluto_addr is None:
		_log(logging.WARNING, "pluto_addr is None")
		return None
	flow = region_games.top(
		zmq_addr,
		pluto_addr,
		center_freq,
		bandwidth,
		TAPS_LPF,
		taps_pre,
		filename, 
		num_samps,
	)
	flow.start()
	return flow


def _stop_region_top(flow: region_games.top | None) -> None:
	if flow is None:
		return
	try:
		flow.stop()
	except Exception as exc:
		logging.warning("Failed to stop region_games flowgraph: %s", exc)


def main(
	devices: DeviceConfig,
	inf_level_timeout=TIMEOUT_INF_LEVEL,
	main_cycle_update_interval=INTERVAL_MAIN_CYCLE,
	faction_timeout=TIMEOUT_ROS_FACTION_QUERY,
	stop_event: threading.Event | None = None,
	main_cycle_device_ctrl_interval=INTERVAL_MAIN_CYCLE_DEVICE_CTRL,
) -> None:
	if not rclpy.ok():
		rclpy.init(args=None)

	status_lock = threading.Lock()
	last_decode_time: dict[str, float] = {"rx_sig": 0.0, "rx_inf": 0.0}
	ros_level_queue: Queue[int] = Queue()
	ros_publish_queue: Queue[dict] = Queue()
	last_device_ctrl_time = 0.0

	def _should_stop() -> bool:
		return stop_event is not None and stop_event.is_set()

	def _on_ros_encrypt_level_change(new_level: int) -> None:
		ros_level_queue.put(new_level)

	def _get_faction_with_timeout(
		node: WirelessRos2AdaptorNodeThreaded,
		timeout_sec: float,
	) -> Faction:
		start_time = time.time()
		while time.time() - start_time < timeout_sec:
			faction = node.get_faction(timeout=timeout_sec)
			if faction in (Faction.RED, Faction.BLUE) or _should_stop():
				return faction
		return faction

	def _wait_for_decode(name: str, timeout_sec: float) -> bool:
		start_time = time.time()
		while time.time() - start_time < timeout_sec:
			if _should_stop():
				return False
			with status_lock:
				last = last_decode_time.get(name, 0.0)
			if last > 0.0:
				return True
			time.sleep(0.05)
		return False

	def _restart_inf_top(level: int) -> None:
		nonlocal rx_inf_top, inf_level
		_stop_region_top(rx_inf_top)
		inf_level = level
		center_freq, bandwidth, taps_pre = _build_inf_params(inf_level, current_site)
		rx_inf_top = _start_region_top(
			ZMQ_ADDR_INF,
			devices.device_inf,
			center_freq,
			bandwidth,
			taps_pre,
		)
		with status_lock:
			last_decode_time["rx_inf"] = time.time()

	# Setup ROS
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
		print(f"ROS2 main node unavailable: {exc}")
		logging.error("ROS2 main node unavailable: %s", exc)

	# Start ZMQ decoders (each creates its own zmqServerRx)
	decoder_sig = frame_decoder_zmq(
		type="signal",
		zmq_address=ZMQ_ADDR_SIG,
		on_frame_decoded=_build_ros_queue_callback(
			ros_publish_queue,
			"rx_sig",
			last_decode_time,
			status_lock,
		),
	)
	decoder_inf = frame_decoder_zmq(
		type="jamming",
		zmq_address=ZMQ_ADDR_INF,
		on_frame_decoded=_build_ros_queue_callback(
			ros_publish_queue,
			"rx_inf",
			last_decode_time,
			status_lock,
		),
	)
	_ = (decoder_sig, decoder_inf)

	# Determine faction via decoding if ROS is unavailable
	rx_sig_top: region_games.top | None = None
	if current_site is None:
		print("Attempting to determine faction from signal decoding...")
		logging.log(logging.INFO, "Attempting to determine faction from signal decoding...")
		while True:
			if _should_stop():
				return
			for site in (CurrentSite.RED, CurrentSite.BLUE):
				if _should_stop():
					return
				with status_lock:
					last_decode_time["rx_sig"] = 0.0
				center_freq, bandwidth, taps_pre = _build_sig_params(site)
				rx_sig_top = _start_region_top(
					ZMQ_ADDR_SIG,
					devices.device_sig,
					center_freq,
					bandwidth,
					taps_pre,
				)
				decoded = _wait_for_decode("rx_sig", TIMEOUT_FACTION_SHARCH)
				if decoded:
					current_site = site
					break
				_stop_region_top(rx_sig_top)
				rx_sig_top = None
				time.sleep(0.5)
			if current_site is not None:
				logging.log(logging.INFO, "Determined faction from signal decoding: %s", current_site.name)
				print(f"Determined faction from signal decoding: {current_site.name}")
				break

	if current_site is None:
		current_site = CurrentSite.RED
		logging.warning("Faction still unknown; defaulting to RED.")

	if rx_sig_top is None:
		center_freq, bandwidth, taps_pre = _build_sig_params(current_site)
		rx_sig_top = _start_region_top(
			ZMQ_ADDR_SIG,
			devices.device_sig,
			center_freq,
			bandwidth,
			taps_pre,
		)

	inf_level = 1
	center_freq, bandwidth, taps_pre = _build_inf_params(inf_level, current_site)
	rx_inf_top = _start_region_top(
		ZMQ_ADDR_INF,
		devices.device_inf,
		center_freq,
		bandwidth,
		taps_pre,
	)
	with status_lock:
		last_decode_time["rx_inf"] = time.time()

	logging.info(
		"Main control started: rx_sig on %s, rx_inf on %s (inf level %d)",
		devices.device_sig,
		devices.device_inf,
		inf_level,
	)
	print(
		f"Main control started: rx_sig on {devices.device_sig}, rx_inf on {devices.device_inf} (inf level {inf_level})"
	)

	try:
		while True:
			if _should_stop():
				break

			# Publish ROS messages in main thread
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

			# Periodic device control for inf level updates
			if time.time() - last_device_ctrl_time >= main_cycle_device_ctrl_interval:
				if not ONLY_LEVEL_1:
					ros_level_applied = False
					try:
						while True:
							new_level = ros_level_queue.get_nowait()
							if new_level in (1, 2, 3) and new_level != inf_level:
								_restart_inf_top(new_level)
								ros_level_applied = True
								logging.info("rx_inf switched to level %s due to ROS command", inf_level)
								print(f"rx_inf switched to level {inf_level} due to ROS command")
					except Empty:
						pass

					if not ros_level_applied:
						with status_lock:
							inf_last = last_decode_time.get("rx_inf", time.time())
						if time.time() - inf_last >= inf_level_timeout:
							next_level = 1 if inf_level >= 2 else inf_level + 1
							_restart_inf_top(next_level)
							logging.info("rx_inf switched to next level %d due to timeout", inf_level)
							print(f"rx_inf switched to next level {inf_level} due to timeout")

				last_device_ctrl_time = time.time()

			time.sleep(main_cycle_update_interval)
	finally:
		_stop_region_top(rx_sig_top)
		_stop_region_top(rx_inf_top)
		if ros_node is not None:
			ros_node.stop()


if __name__ == "__main__":
	filename = f"logs/main_rx_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log"
	filepath = _makesure_path_exist(filename)
	logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=filepath, filemode='w')

	stop_event = threading.Event()
	try:
		main(device_conf, stop_event=stop_event)
	except KeyboardInterrupt:
		stop_event.set()
