"""
和雷达主线程对接的模块
处理从zmq_server中读取的np.array[uint8]数据
将新读取的数据和之前的最后数个遗留数据拼接 然后转为比特流
使用np.correlate识别access code
然后解析OTA frame和串口协议帧
返回解析出的信息的dict 后续可改成接口的格式
"""
from crc import verify_crc16_check_sum, verify_crc8_check_sum
from zmq_server import zmq_server_rx
import numpy as np
from util import print_hex_by_byte, _reverse_string
import logging
import time
import threading
from frame_def import *

LEN_HEADER = LEN_SOF + LEN_DATA_LENGTH + LEN_SEQ + 1
ACCESS_JAMMING_NPARRAY_BITS = np.unpackbits(np.frombuffer(ACCESS_CODE_JAMMING.to_bytes(8, ENDIAN_OTA), dtype=np.uint8))
ACCESS_SIGNAL_NPARRAY_BITS = np.unpackbits(np.frombuffer(ACCESS_CODE_SIGNAL.to_bytes(8, ENDIAN_OTA), dtype=np.uint8))

class frame_decoder:
    def __init__(
        self,
        type = "signal", # signal或jamming 解析信息波还是干扰波
        len_history_bits = 27 * 8 - 1, # 每个空口帧为27bytes 每轮保留上一轮最后27*8-1bits
        len_history_payload = 44, # 串口协议帧最长为45bytes 每轮保留上一轮最后45bytes
        crc8_enabled = True, # 是否在串口帧帧头识别时启用CRC8校验
        crc16_enabled = True, # 是否在串口帧解析时启用CRC16校验
        update_interval = 0.005, # 更新buffer_bits并进行后续处理的频率
        buffer_payload_expire_time = 0.2, # 连续多长时间没有识别到有效空口帧 则清空buffer_payload 防止过时的数据被反复输出
        zmq_address = "tcp://127.0.0.1:2236",
        zmq_data_type = np.uint8,
        zmq_buffer_size = 500, # 理论上0.25秒的数据会占满500bytes
        zmq_read_data_interval = 0.005, # 从tcp buffer读取新数据的时间间隔
        on_frame_decoded = None, # 成功解析帧后的回调函数，参数为data_dict_list
    ):
        # 比特流缓冲区
        self._buffer_bits = np.array([], dtype=np.uint8)
        # 从空口帧中解析出的payload的bytes缓冲区
        self._buffer_payload = bytes()

        self._type = type
        self._crc8_enables = crc8_enabled
        self._crc16_enables = crc16_enabled
        self._update_interval = update_interval
        self._len_history_bits = len_history_bits
        self._len_history_payload = len_history_payload
        self._buffer_payload_expire_time = buffer_payload_expire_time
        self._last_ota_frame_synced_time = time.time() # 记录上一次识别到空口帧的时间
        self._on_frame_decoded = on_frame_decoded # 成功解析帧后的回调函数

        self._zmq_server = zmq_server_rx(
            zmq_address, 
            zmq_data_type,
            zmq_buffer_size,
            zmq_read_data_interval
        )
        thread = threading.Thread(target=self._worker)
        thread.start()

    # def _debug(self, bits):
    #     """测试用"""
    #     print("----------start------------")
    #     self.buffer_bits = bits
    #     # 将bits缓存中的信息 读取串口协议帧 存放到payload缓存中
    #     self._frame_sync_ota()
    #     print("----------buffer_payload------------")
    #     print_hex_by_byte(self.buffer_payload)
    #     # 将payload缓存中的信息进行串口信息帧识别与解析
    #     frames_serial = self._frame_sync_serial()
    #     print("----------frames_serial------------")
    #     print_hex_by_byte(frames_serial)
    #     if frames_serial is None:
    #         return
    #     # 解析串口帧信息
    #     data_dict_list = []
    #     for f in frames_serial:
    #         d = self._decode_frame_serial(f)
    #         if d is None:
    #             return
    #         data_dict_list.append(d)
    #     print(data_dict_list)
    #     print("test end")

    def set_crc16_enabled(self, enable):
        """开关crc16校验"""
        self._crc16_enables = enable

    def _read_data(self):
        """从zmq_server读取数据并转化为比特流 np.int8(bytes) -> np.int8(bits)"""
        # 删除buffer中除最后一段外的其他bit
        if len(self._buffer_bits) > self._len_history_bits:
            self._buffer_bits = self._buffer_bits[-self._len_history_bits:]
        # 将zmq_server中读取的字节流转换为比特流后进行拼接
        data = self._zmq_server.read_data()
        if data is not None:
            self._buffer_bits = np.concatenate([self._buffer_bits, np.unpackbits(data)])
        logging.log(logging.DEBUG, f"[frame decoder] read data  current buffer_bits size {len(self._buffer_bits)}")

    def _read_bytes_from_bits(self, bits: np.ndarray[np.uint8], start_bit: int, byte_count: int) -> bytes:
        """从比特流指定idx开始读连续的指定长度的bytes"""
        end_bit = start_bit + byte_count * 8
        if end_bit > len(bits):
            logging.log(logging.DEBUG, f"[frame_decoder] read bytes from bits: end index out of bound ({end_bit}/{len(bits)})")
            return bytes([])

        out = bytearray()
        for offset in range(byte_count):
            base = start_bit + offset * 8
            value = 0
            for bit_index in range(8):
                value = (value << 1) | bits[base + bit_index]
            out.append(value)
        return bytes(out)
    
    def _frame_sync_ota(self) -> list[bytes]:
        """
        将payload buffer中上一轮的数据除最后保留的部分外删除
        读取self.buffer_bits 使用np.correlate识别空口帧帧头 读取空口帧payload
        并转换为bytes结构 添加到payload_buffer中
        payload_buffer有超时清空机制 防止一直识别不到空口帧导致payload_buffer中的旧数据被反复读取
        """
        # 删除buffer中除最后一段外的其他bytes
        if len(self._buffer_payload) > self._len_history_payload:
            self._buffer_payload = self._buffer_payload[-self._len_history_payload:]

        # 缓冲区为空时直接返回
        if len(self._buffer_bits) == 0:
            return
        if self._type == "signal":
            access_corr = ACCESS_CORR_SIGNAL
            access = ACCESS_SIGNAL_NPARRAY_BITS
        else:
            access_corr = ACCESS_CORR_JAMMING
            access = ACCESS_JAMMING_NPARRAY_BITS
        # 计算信息比特流与比特流形式的access_code的互相关
        corr = np.correlate(self._buffer_bits, access, 'valid')
        # 经过计算 互相关值为32处为空口帧的帧头（两种accesscode均为32）
        idx_frame = np.argwhere(corr == access_corr).flatten()
        logging.log(logging.DEBUG, f"[frame_decoder] ota frame sync {len(idx_frame)} {idx_frame}")
        # 读取空口帧payload 转为bytes 并放在buffer_payload中
        synced_flag = False # 是否识别到有效帧
        for idx in idx_frame:
            p = self._read_bytes_from_bits(self._buffer_bits, idx + LEN_ACCESS * 8 + LEN_OTA_LENGTH * 2 * 8, LEN_OTA_PAYLOAD)
            if len(p) != 0:
                synced_flag = True
                logging.log(logging.INFO, f"[frame decoder] synced_flag True")
                self._buffer_payload = self._buffer_payload + p

        if synced_flag:
            # 更新上次有效识别时间
            self._last_ota_frame_synced_time = time.time()

        # 若长时间没有读到有效空口帧，则丢弃所有buffer_payload中的数据 （已经过时了）
        if time.time() - self._last_ota_frame_synced_time > self._buffer_payload_expire_time:
            self._buffer_payload = bytes()
            logging.log(logging.DEBUG, f"[frame decoder] buffer_payload expired")

        logging.log(logging.DEBUG, f"[frame decoder] frame sync ota  current buffer_payload size {len(self._buffer_payload)}")
    
    def _frame_sync_serial(self):
        """在payload buffer中识别串口帧"""
        if len(self._buffer_payload) == 0:
            return []
        
        idx = [i for i, b in enumerate(self._buffer_payload) if b == SOF]
        frames_serial = []

        # 构建frame_serial
        for i in idx:
            data_length = int.from_bytes(self._buffer_payload[i + LEN_SOF:i + LEN_SOF + LEN_DATA_LENGTH], ENDIAN)
            frame_length = LEN_HEADER + LEN_CMD_ID + data_length + 2
            if i + frame_length > len(self._buffer_payload):
                continue
            frames_serial.append(self._buffer_payload[i:i + frame_length])

        if self._crc8_enables:
            # 进行crc8校验 删除未通过校验的帧
            for f in frames_serial:
                if not verify_crc8_check_sum(f[:LEN_HEADER]):
                    logging.log(logging.INFO, "[frame_decoder]crc8 verify failed")
                    frames_serial.remove(f)
            return frames_serial
        else:
            return frames_serial
            # 不进行crc8校验 直接返回
    
    def _decode_frame_serial(self, frame_serial) -> dict | None:
        """
        将串口帧中有效信息解析出来
        """
        if self._crc16_enables:
            if not verify_crc16_check_sum(frame_serial):
                logging.log(logging.INFO, "[frame_decoder]crc16 verify failed")
                return None
        data_length = int.from_bytes(frame_serial[LEN_SOF:LEN_SOF + LEN_DATA_LENGTH], ENDIAN)
        bias_cmd_id = LEN_HEADER
        cmd_id = int.from_bytes(frame_serial[bias_cmd_id:bias_cmd_id + LEN_CMD_ID], ENDIAN)
        bias_data = LEN_HEADER + LEN_CMD_ID
        data = frame_serial[bias_data:bias_data + data_length]
        
        # 将bytes解析成dict
        for key, value in CMD_OPTIONS.items():
            if cmd_id == value[0]:
                cmd_name = key
        if cmd_name is None:
            logging.log(logging.INFO, f"[frame_decoder]cmd name not found{key, value}")
            return None
        # 加载对应命令码的帧结构
        fields = SERIAL_FIELDS[cmd_name]
        data_dict = dict()
        offset = 0
        # 从bytes中解析信息为dict
        for name, length in fields:
            raw = data[offset:offset + length]
            if name == "key":
                value = str(raw)
                if ENDIAN_DATA == "little":
                    # 翻转字符串
                    value = _reverse_string(value)
            else:
                value = int.from_bytes(raw, ENDIAN_DATA)
            data_dict[name] = value
            offset += length
        return data_dict
        
    def _worker(self):
        """主要任务函数"""
        while(True):
            time_start = time.time()

            # 将zmq_server中缓存读取到bits缓存中
            self._read_data()
            # 将bits缓存中的信息 读取串口协议帧 存放到payload缓存中
            self._frame_sync_ota()
            # 将payload缓存中的信息进行串口信息帧识别与解析
            frames_serial = self._frame_sync_serial()
            if frames_serial is None or len(frames_serial) == 0:
                logging.log(logging.DEBUG, f"[frame_decoder] frames serial is None")
                continue
            else:
                logging.log(logging.INFO, f"[frame_decoder] frames serial detected {len(frames_serial)}")
            # 解析串口帧信息
            data_dict_list = []
            for f in frames_serial:
                d = self._decode_frame_serial(f)
                if d is None:
                    logging.log(logging.INFO, f"[frame_decoder] frame serial decode failed")
                    continue
                data_dict_list.append(d)
                logging.log(logging.INFO, f"[frame_decoder] frame serial decode success")
            
            # 调用回调函数进行后续处理
            if data_dict_list and self._on_frame_decoded:
                try:
                    self._on_frame_decoded(data_dict_list)
                except Exception as e:
                    logging.log(logging.WARNING, f"[frame_decoder] callback error: {e}")

            time_sleep = self._update_interval - (time.time() - time_start)
            if time_sleep > 0:
                time.sleep(time_sleep)


if __name__ == "__main__": # 测试代码
    from frame_coder import build_frame_ota_jamming, build_frame_ota_signal, _generate_payload_random
    from util import print_hex_by_byte

    # frames = build_frame_ota_jamming("RM2026")

    frames = []
    frames += build_frame_ota_signal(_generate_payload_random(), seq=0)
    frames += build_frame_ota_signal(_generate_payload_random(), seq=1)
    frames += build_frame_ota_signal(_generate_payload_random(), seq=2)

    for f in frames:
        print_hex_by_byte(f)
    print("----------------")

    bs = np.array([], dtype=np.uint8)
    for f in frames:
        b =  np.unpackbits(np.frombuffer(f, dtype=np.uint8))
        bs = np.concat([bs, b])

    print(bs)
    print("----------------")

    decoder = frame_decoder(type="signal")
    decoder._debug(bs)
