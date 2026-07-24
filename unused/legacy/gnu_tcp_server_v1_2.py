import zmq
import numpy as np
import time
import threading


class gnu_tcp_server:

    def __init__(
        self,
        address_recv = "tcp://127.0.0.1:2235",
        address_send = "tcp://127.0.0.1:2236",
        recv_data_type = np.float32,
        recv_data_buffer_size = 262144,
        recv_tcp_buffer_refresh_time = 0.1
    ):
        """
        TCP服务器 用于接收GNU Radio发送的数据
        GNU Radio中使用ZMQ PUB块并配置地址即可
        默认地址为"tcp://127.0.0.1:2235"(gnu->python)与"tcp://127.0.0.1:2236"(python->gnu)
        Params:
            address: 地址字符串 与gnu中PUB块的地址相同 如 "tcp://127.0.0.1:2236"
            data_type: 数据类型 默认为np.complex64 若为浮点型应为np.float32
            recv_data_buffer_size: 接收信息缓冲区有效长度 在缓冲区中数据大于该值时 才能调用read_data()读取最前面该长度的信息
            recv_tcp_buffer_refresh_time: 每过一段时间重新建立SUB连接 使PUB端积压的信息被清空 防止PUB端阻塞严重
        Returns:
            data: np.array
        """
        self.recv_tcp_buffer_refresh_time = recv_tcp_buffer_refresh_time
        self.addr_recv = address_recv
        self.context_pub = zmq.Context()
        self.socket_pub = self.context_pub.socket(zmq.PUB)
        self.socket_pub.bind(address_send)
        self.recv_data_type = recv_data_type
        self.recv_data_buffer_size = recv_data_buffer_size
        self.recv_data_buffer = np.array([], dtype=recv_data_type)
        thread = threading.Thread(target=self._receive_data_thread)
        thread.start()

    def _receive_data_thread(self):
        while True:
            time_start = time.time()
            time_end = time_start + self.recv_tcp_buffer_refresh_time
            self.context_sub = zmq.Context()
            self.socket_sub = self.context_sub.socket(zmq.SUB)
            self.socket_sub.connect(self.addr_recv)
            self.socket_sub.setsockopt(zmq.SUBSCRIBE, b"")
            while time.time() < time_end:
                if not self._receive_data():
                    time.sleep(0.01)

    def _receive_data(self):
        """
        接收数据
        Returns:
            bool 是否接收到数据
        """
        if self.socket_sub.poll(10) != 0:  # check if there is a message on the socket
            msg = self.socket_sub.recv()  # grab the message
            data = np.frombuffer(
                msg, dtype=self.recv_data_type, count=-1
            )  # make sure to use correct data type (complex64 or float32); '-1' means read all data in the buffer
            self.recv_data_buffer = np.concatenate(
                [self.recv_data_buffer, np.array(data)]
            )
            return True
        else:
            return False

    def read_data(self):
        """
        从缓冲区中读取数据
        若缓冲区中数据足够 返回数据
        否则返回None
        """
        if len(self.recv_data_buffer) >= self.recv_data_buffer_size:
            data = self.recv_data_buffer[: self.recv_data_buffer_size]
            self.recv_data_buffer = self.recv_data_buffer[self.recv_data_buffer_size :]
            return data
        else:
            return None

    def send_data(self, data):
        """
        发送数据
        """
        self.socket_pub.send(data)


# 示例程序
if __name__ == "__main__":
    server = gnu_tcp_server(recv_data_type=np.complex64)
    data_send = np.ones(1000, dtype=np.float32)
    for i in range(len(data_send)):
        data_send[i] = i
    while True:
        server.send_data(data_send)
        data_recv = server.read_data()
        if data_recv is not None:
            print(data_recv[:10])
        else:
            time.sleep(0.01)
