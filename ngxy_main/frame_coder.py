import numpy as np
import random

from crc import append_crc8_check_sum, append_crc16_check_sum, verify_crc8_check_sum, verify_crc16_check_sum
from util import print_hex_by_byte, _reverse_string
from frame_def import (CMD_OPTIONS, SERIAL_FIELDS, SOF, ACCESS_CODE_SIGNAL, ACCESS_CODE_JAMMING,
                       LEN_OTA_PAYLOAD, ENDIAN, ENDIAN_DATA, ENDIAN_OTA,
                       LEN_SOF, LEN_CMD_ID, LEN_DATA_LENGTH, LEN_SEQ, LEN_ACCESS, LEN_OTA_LENGTH)

def _generate_payload_random():
    """生成字典形式的payload {cmd_name:{xx:xx}} 数据为随机值"""
    output = {}
    for cmd_name, fields in SERIAL_FIELDS.items():
            config = {field_name: random.randint(0, 255) for field_name, _ in fields}
            output[cmd_name] = config
    return output

def _encode_payload(cmd_option, payload):
    """将字典形式的payload打包成串口协议中payload格式"""
    fields = SERIAL_FIELDS.get(cmd_option)
    if not fields:
        # log("[warning][frame_coder] Unknown cmd_option in encode_payload")
        return bytearray([0])
    # 初始化字节数组
    out = bytearray()
    # payload必须是dict，且字段名必须与协议定义一致，否则缺失字段按0填充，多余字段忽略
    if not isinstance(payload, dict):
        # log("[warning][frame_coder] Payload for serial encoding should be a dict")
        return bytearray([0])
    for name, size in fields:
        # 将payload字典中对应字段的值转换为bytes并添加到out中
        # 整数直接转换 干扰波秘钥的字符串转化成字节数组
        v = payload.get(name, 0)
        if name == "key":
            s = str(v)[:size].ljust(size, "\0")
            if ENDIAN_DATA == "little": # 小端序下翻转
                s = _reverse_string(s)
            out += bytes([ord(c) for c in s])
        else:
            out += int(v).to_bytes(size, ENDIAN_DATA)
    return out

def _build_frame_serial(cmd_option:str, payload:dict, seq=0) -> bytes:
        """打包串口协议帧 payload为字典形式 seq为包序号"""
        
        _cmd_id, data_len_expect = CMD_OPTIONS[cmd_option]
        # 编码payload 到data_bytes
        data_bytes = _encode_payload(cmd_option, payload)
        # 调整长度
        if len(data_bytes) < data_len_expect:
            data_bytes += [0x00] * (data_len_expect - len(data_bytes))
        if len(data_bytes) > data_len_expect:
            data_bytes = data_bytes[:data_len_expect]

        # 帧其他部分的生成
        sof = SOF.to_bytes(LEN_SOF, ENDIAN)
        data_len_derived = (data_len_expect).to_bytes(LEN_DATA_LENGTH, ENDIAN)
        seq_derived = (seq & 0xFF).to_bytes(LEN_SEQ, ENDIAN)
        # 拼接帧头
        header = sof + data_len_derived + seq_derived
        # 添加帧头CRC8
        header = append_crc8_check_sum(header)
        # 添加cmd_id和payload
        frame = header + _cmd_id.to_bytes(LEN_CMD_ID, ENDIAN) + _encode_payload(cmd_option, payload)
        # 添加crc16
        frame = append_crc16_check_sum(frame)
        return frame


def _build_frame_ota(access, payload:bytes) -> bytes:
    return access.to_bytes(LEN_ACCESS, ENDIAN_OTA) + LEN_OTA_PAYLOAD.to_bytes(LEN_OTA_LENGTH, ENDIAN_OTA) + LEN_OTA_PAYLOAD.to_bytes(LEN_OTA_LENGTH, ENDIAN_OTA) + payload


def _ota_frames_to_bitstream(ota_frames) -> np.ndarray[np.uint8]:
    """
    空口帧转比特流
    输出可以直接给zmq server
    输出格式为np.ndarray[np.uint8] 每byte表示1bit
    """
    buffer = bytes()
    for f in ota_frames:
        buffer += f
    bitstream = np.frombuffer(buffer, dtype=np.uint8)
    # 转比特流
    bitstream = np.unpackbits(bitstream)
    return bitstream


def build_frame_ota_signal(payload_dict, seq=0) -> np.ndarray[np.uint8]:
    """
    构建信息波空口帧
    """
    buffer = None
    for cmd_name in payload_dict:
        if cmd_name == 'jamming': # 不对干扰波秘钥进行构建
            continue
        else:
            frame_serial = _build_frame_serial(cmd_name, payload_dict[cmd_name], seq)
            if buffer is None:
                buffer = frame_serial
            else:
                buffer += frame_serial
    # 开始构建空口帧
    # 补齐buffer为LEN_OTA_PAYLOAD bytes的倍数
    r = len(buffer) % LEN_OTA_PAYLOAD
    len_append = LEN_OTA_PAYLOAD - r
    buffer += random.randbytes(len_append)

    # 将buffer分段为list 每个元素为LEN_OTA_PAYLOAD bytes
    chunks = [buffer[i:i+LEN_OTA_PAYLOAD] for i in range(0, len(buffer), LEN_OTA_PAYLOAD)]
    ota_frames = []
    for c in chunks:
        ota_frames.append(_build_frame_ota(ACCESS_CODE_SIGNAL, c))
    return _ota_frames_to_bitstream(ota_frames)
    
def build_frame_ota_jamming(key:str, num_bytes_fill=200, seq=0) -> np.ndarray[np.uint8]:
    """
    直接从秘钥字符串构建干扰波的空口帧
    Args:
        num_bytes_fill:每次传输秘钥后填充多少字节的随机值
    """
    key_dict = {"key": key}
    frame_serial = _build_frame_serial("jamming", key_dict, seq)
    buffer = frame_serial + random.randbytes(num_bytes_fill)

    # 开始构建空口帧
    # 补齐buffer为LEN_OTA_PAYLOAD bytes的倍数
    r = len(buffer) % LEN_OTA_PAYLOAD
    len_append = LEN_OTA_PAYLOAD - r
    buffer += random.randbytes(len_append)

    # 将buffer分段为list 每个元素为LEN_OTA_PAYLOAD bytes
    chunks = [buffer[i:i+LEN_OTA_PAYLOAD] for i in range(0, len(buffer), LEN_OTA_PAYLOAD)]
    ota_frames = []
    for c in chunks:
        ota_frames.append(_build_frame_ota(ACCESS_CODE_JAMMING, c))
    return _ota_frames_to_bitstream(ota_frames)


# 测试代码
if __name__ == "__main__":
    from util import print_hex_by_byte

    # for f in frames:
    #     print("------------")
    #     print_hex_by_byte(f)
    # payload_dict = _generate_payload_random()
    # buffer = None
    # for cmd_name in payload_dict:
    #     if cmd_name == 'jamming': # 不对干扰波秘钥进行构建
    #         continue
    #     else:
    #         frame_serial = _build_frame_serial(cmd_name, payload_dict[cmd_name])
    #         if buffer is None:
    #             buffer = frame_serial
    #         else:
    #             buffer += frame_serial
    # print(len(buffer))