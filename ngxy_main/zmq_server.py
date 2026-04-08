import zmq
import numpy as np
import time
import threading
import json
import dataclasses
import util # 日志初始化在里面执行
import logging
from status_def import dict_to_dataclass, BaseStatus

class zmqServerTx:
    """
    发送np.ndarray或dataclass(会自动转换为JSON字符串)的字节流
    """
    def __init__(
        self,
        address = "tcp://127.0.0.1:2235"
    ):
        self._address = address
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.PUB)
        self._socket.bind(address)

    def send_data(self, data):
        """发送数据，如果是 dataclass 则自动序列化为 JSON 字节"""
        if isinstance(data, BaseStatus):
            data_dict = dataclasses.asdict(data)
        if isinstance(data, dict):
            data_dict = data
            data_str = json.dumps(data_dict)
            data_bytes = data_str.encode('utf-8')
            self._socket.send(data_bytes)
        else:
            self._socket.send(data)

class zmqServerRx:
    """
    接收数据并存入buffer，提供接口将buffer中的数据取出
    若数据类型为 dataclass 则自动尝试解析JSON并转换为对应的 dataclass 实例
    """ 
    def __init__(
        self,
        address,
        data_type: np.dtype | str = "dataclass", # "dataclass"表示接收 dataclass 类型数据
        buffer_size = 32767, # buffer最大字节数 超过后会丢弃最老的数据 为保证实时性应设小一点
        read_data_interval = 0.001, # 轮询时间间隔 单位秒
    ):
        self._data_type = data_type
        self._buffer_size = buffer_size
        self._read_buffer_interval = read_data_interval

        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.connect(address)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")

        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        """将zmq缓冲区的数据读到buffer中"""
        while not self._stop_event.is_set():
            if self._socket.poll() != 0:
                time_start = time.time()

                msg = self._socket.recv()
                with self._lock:
                    logging.log(logging.DEBUG, f"[{time.time()}][zmq_server_rx] read from zmq buffer {len(msg)}")
                    self._buffer.extend(msg)
                    len_exceed_data = len(self._buffer) - self._buffer_size
                    if len_exceed_data > 0: # buffer大小超过上限
                        logging.log(logging.WARNING, f"[{time.time()}][zmq_server_rx] buffer size exceeded" + str(len_exceed_data))
                        self._buffer = self._buffer[len_exceed_data:] # 清理最老的数据

                time_sleep = self._read_buffer_interval - (time.time() - time_start)
                if time_sleep > 0:
                    time.sleep(time_sleep)
    
    def read_data(self) -> np.ndarray | BaseStatus | None:
        """
        将buffer中的数据全部取出 并从buffer中移除这些数据
        若数据类型为 dataclass 则自动尝试解析buffer中的JSON字符串并转换为对应的 dataclass 实例
        """
        with self._lock:
            if len(self._buffer) == 0:
                return None
            data_bytes = bytes(self._buffer)
            self._buffer.clear()

        if isinstance(self._data_type, str):
            if self._data_type == "dataclass":
                # 尝试作为 JSON 解析并转换为 dataclass
                try:
                    data_str = data_bytes.decode('utf-8')
                    data_dict = json.loads(data_str)
                    result = dict_to_dataclass(data_dict)
                    if result is not None:
                        logging.log(logging.DEBUG, f"[{time.time()}][zmq_server_rx] parsed dataclass: {type(result).__name__}")
                        return result
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                    pass
                # 如果解析失败，返回 None 或错误，这里选择返回 None
                return None
        else:
            # 返回 ndarray
            data_array = np.frombuffer(data_bytes, dtype=self._data_type)
            logging.log(logging.DEBUG, f"[{time.time()}][zmq_server_rx] read from zmq server buffer {len(data_array)}")
            return data_array

    def stop(self):
        """停止后台 zmq 接收线程"""
        self._stop_event.set()
        self._thread.join(timeout=1)