"""误码率检测程序 调试用"""

"""
版本历史
v1.1 基础版本
v1.2 更改tcp_server 添加定时清空buffer功能
v1.3 添加加载/保存功能
v1.3.1 添加另一种保存格式
v1.5 添加实际信息帧验证功能
"""

from ngxy_main.gnu_tcp_server_v1_2 import gnu_tcp_server

from frame_generator import (
    generate_looped_examples_stream,
    bytes_to_bits,
)
from ngxy_main.frame_decoder import (
    decode_frames_from_bitstream,
    print_decoded_frames_compact_cn,
)

import numpy as np
import time


ANSI_GREEN = "\033[32m"
ANSI_RESET = "\033[0m"


# cmd_id 名称映射 用于日志输出
CMD_NAMES = {
    0x0A06: "密钥",
    0x0A01: "位置信息",
    0x0A02: "血量",
    0x0A03: "可发弹量",
    0x0A04: "资源状态",
}


def generate_test_symbols(cycle_count, seed=20260312):
    """使用协议帧生成循环数据流并转为4-FSK符号。

    Args:
        cycle_count: 帧循环次数 每次循环生成5种帧
        seed: 随机种子 确保可复现
    Returns:
        symbols: np.ndarray int8 可直接发送的4-FSK符号序列
        expected_frames: set of (cmd_id, data) 用于接收端校验
    """
    # 生成协议字节流
    byte_stream = generate_looped_examples_stream(
        cycle_count=cycle_count,
        start_seq=0,
        seed=seed,
    )

    # bytes → bits → 4-FSK symbols (00→0, 01→1, 10→2, 11→3)
    bits = bytes_to_bits(byte_stream)
    bits_np = np.array(bits, dtype=np.int8)
    symbols = coder(bits_np)

    # 预解码得到期望帧集合 用于接收端比对
    decoded = decode_frames_from_bitstream(bits)
    expected_frames = set()
    for frame in decoded:
        expected_frames.add((frame.cmd_id, frame.data))

    return symbols, expected_frames


def examine_received_data(received_bits, expected_frames):
    """从接收比特流中解码帧并与期望帧比对。

    利用CRC8+CRC16双重校验自动识别有效帧,
    再与发送端的帧数据比对确认内容正确性。

    Args:
        received_bits: 接收到的0/1比特序列
        expected_frames: set of (cmd_id, data) 期望帧集合
    Returns:
        total_cnt, correct_cnt, incorrect_cnt
    """
    decoded = decode_frames_from_bitstream(received_bits)

    correct_cnt = 0
    incorrect_cnt = 0
    correct_frame_kinds = set()
    cmd_correct = {}
    cmd_incorrect = {}

    for frame in decoded:
        key = (frame.cmd_id, frame.data)
        cmd_name = CMD_NAMES.get(frame.cmd_id, f"0x{frame.cmd_id:04X}")
        if key in expected_frames:
            correct_cnt += 1
            correct_frame_kinds.add(key)
            cmd_correct[cmd_name] = cmd_correct.get(cmd_name, 0) + 1
        else:
            incorrect_cnt += 1
            cmd_incorrect[cmd_name] = cmd_incorrect.get(cmd_name, 0) + 1

    total_cnt = correct_cnt + incorrect_cnt

    if total_cnt == 0:
        print(f"[{time.time():.3f}] 未检测到有效帧")
    else:
        total_sent_kinds = len(expected_frames)
        correct_kinds = len(correct_frame_kinds)
        kind_ratio = (
            (correct_kinds / total_sent_kinds * 100) if total_sent_kinds else 0.0
        )
        print(
            f"{ANSI_GREEN}解调正确率: "
            f"{correct_kinds}/{total_sent_kinds} ({kind_ratio:.1f}%){ANSI_RESET}"
        )

        # 输出每个已解码帧的具体字段值(密钥/位置/血量/弹量/资源状态)
        print("  解码详情:")
        print_decoded_frames_compact_cn(decoded)

    return total_cnt, correct_cnt, incorrect_cnt


if __name__ == "__main__":

    THRESHOLDS = [-3.5, 0, 3.5]  # 硬判决界限
    CYCLE_COUNT = 10  # 帧循环次数 每次循环生成5种帧
    SEED = 20260312  # 随机种子

    print("使用协议帧生成器生成测试数据...")
    data_send_symbols, expected_frames = generate_test_symbols(
        cycle_count=CYCLE_COUNT,
        seed=SEED,
    )
    print(
        f"已生成 {len(data_send_symbols)} 个符号 " f"({len(expected_frames)} 种独立帧)"
    )

    # examine_received_data(decoder(data_send_symbols), expected_frames)  # 本地测试用 直接解码发送数据验证生成的正确性
    server = gnu_tcp_server()
    while True:
        server.send_data(data_send_symbols)
        data_recv = server.read_data()
        if data_recv is not None:
            print(f"recv_len={len(data_recv)}")
            data_symbols = hard_decision(data_recv, THRESHOLDS)
            received_bits = decoder(data_symbols)
            examine_received_data(received_bits, expected_frames)
        else:
            time.sleep(0.01)
