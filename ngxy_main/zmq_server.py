"""
现有问题 若read_data过慢 zmq内部会积压数据包 导致后续解码出的数据延迟非常大
但是没有好办法检测zmq内部积压情况
将每次读取的bit数log出来也不行 gnuradio自动生成大小不等的数据包 一包一包发 收的时候就算产生了积压log出来也只是每一包的数据量
1M采样率 52sps下 当read_data的间隔在0.005s时能正常工作 再长了就不好说了
"""

"""
gnuradio和python进行通信的class
rx端gnuradio将pack bits后的字节流传进python (gnuradio解调完后为1bit/byte数据流 pack8bits后为字节流 字节流发给python)
tx端干扰信号走gnuradio的filesource接pulutosink 
信息信号走zmq传到gnuradio中 gnuradio接filesink 单开一个python线程控制pluto读iq文件来循环发送
"""

import zmq
import numpy as np
import time
import threading
import util # 日志初始化在里面执行
import logging

class zmq_server_tx:
    """向gnuradio传输待发送的数据"""
    def __init__(
        self,
        address = "tcp://127.0.0.1:2235"
    ):
        self._address = address
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.PUB)
        self._socket.bind(address)

    def send_data(self, data):
        """发送数据"""
        self._socket.send(data)

class zmq_server_rx:
    """
    从gnuradio接收数据
    理论接受速率为19230bits/s 2044byte/s 经过计算 信息波是不循环发送 也就是说解析信息帧的效率必须达到2044byte/s
    gnuradio返回的数据应该是bytes 对应np.int8 但是实际按np.uint8读取 方便后续处理
    接收的数据存放在buffer中
    buffer在被读取的时候自动将读取到的数据清除（在读取端应该设置一定历史记忆大小-按串口规则算一下 读取后要以10Hz的量为处理单位）
    buffer在每次读取新数据时 将超过大小上线的最老数据丢弃 防止内存溢出
    """ 
    def __init__(
        self,
        address,
        data_type,
        buffer_size, # 理论上0.25秒的数据会占满500bytes
        read_data_interval # 从tcp buffer读取新数据的时间间隔
    ):
        self._data_type = data_type
        self._buffer_size = buffer_size
        self._read_buffer_interval = read_data_interval

        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.connect(address)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")

        self._buffer = np.array([], dtype=data_type)
        thread = threading.Thread(target=self._worker)
        self._lock = threading.Lock()
        thread.start()

    def _worker(self):
        """将tcp缓冲区的数据读到buffer中"""
        while True:
            if self._socket.poll() != 0:
                time_start = time.time()

                msg = self._socket.recv()
                with self._lock:
                    data = np.frombuffer(
                        msg, dtype=self._data_type, count=-1
                    )
                    logging.log(logging.DEBUG, f"[{time.time()}][zmq_server_rx] read from zmq buffer {len(data)}")
                    self._buffer = np.concatenate(
                        [self._buffer, np.array(data)]
                    )
                    len_exceed_data = len(self._buffer) - self._buffer_size
                    if len_exceed_data > 0: # buffer大小超过上限
                        logging.log(logging.WARNING, f"[{time.time()}][zmq_server_rx] buffer size exceeded" + str(len_exceed_data))
                        self._buffer = self._buffer[len_exceed_data:] # 清理最老的数据

                time_sleep = self._read_buffer_interval - (time.time() - time_start)
                if time_sleep > 0:
                    time.sleep(time_sleep)
    
    def read_data(self) -> np.ndarray[np.uint8]:
        """将buffer中的数据全部取出 并从buffer中移除这些数据"""
        if len(self._buffer) != 0:
            logging.log(logging.DEBUG, f"[{time.time()}][zmq_server_rx] read from zmq server buffer {len(self._buffer)}")
            temp = self._buffer
            with self._lock:
                self._buffer = np.array([], dtype=self._data_type)
            return temp