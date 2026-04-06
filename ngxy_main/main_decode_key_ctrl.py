"""
解调干扰波板子的控制逻辑
解调干扰波的gnuradio->python地址为"tcp://127.0.0.1:2234"

实例化了一个内置gnuradio解调干扰波的类
通过传参控制解调干扰波参数
在某一等级尝试一定时间后没有成功解析出秘钥就提升等级 关闭当前gnuradio类 改参数重新初始化
三级仍失败则再从一级开始
"""

import time
from enum import Enum
from frame_decoder import frame_decoder
from final_no_gui import GnuradioClass
from signal_def import *

import logging
from datetime import datetime

DEFAULT_ADDR = "tcp://127.0.0.1:2234" # gnuradio发送解析结果的地址
TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
IQ_FILE_SAVE_PATH =f"./log/raw_{TIME_STR}.iq" # 保存IQ数据的文件路径
LOG_FILE_PATH = f"./log/log_sdr_{TIME_STR}.log"
ERROR_SLEEP_TIME = 5 # 运行gnuradio发生异常时的休眠时间

class InfLevel(Enum):
    INF1 = 0
    INF2 = 1
    INF3 = 2

class DecodeKey:
    def __init__(self, site:TargetSite, polling_interval=1, timeout=5):
        self.target_site = site
        self.inf_level = InfLevel.INF1
        self.last_decode_time = 0 # 标记上次成功解析出秘钥的时间 0表示初始状态
        self.polling_interval = polling_interval # 轮询解析成功状态间隔
        self.timeout = timeout # 解析失败转换等级的时间阈值
        self.decoder = frame_decoder(
            "signal",
            zmq_address=DEFAULT_ADDR,
            on_frame_decoded=self._handle_frame_decoded
        )

    def _update_level(self):
        """转变干扰波等级"""
        self.inf_level = InfLevel((self.inf_level.value + 1) % 3)
        logging.log(logging.INFO, f"[DecodeKey] 提升干扰等级到{self.inf_level.name}")
    
    def _handle_frame_decoded(self, data_dict_list):
        """处理成功解析的帧数据"""
        for data_dict in data_dict_list:
            # 更新上次成功解析的时间
            self.last_decode_time = time.time()
            # 输出解析结果
            logging.log(logging.INFO, f"[DecodeKey] 解析成功: {data_dict}")

    def attempt_decode(self):
        """尝试解析秘钥的主逻辑"""
        while True:
            try:
                # 创建gnuradio实例
                logging.log(logging.INFO, f"[DecodeKey] 创建gnuradio实例 目标队伍颜色: {self.target_site.name}, 干扰等级: {self.inf_level.name}")
                gnuradio = GnuradioClass(
                    fc=[FC_RED_1, FC_RED_2, FC_RED_3][self.inf_level.value] 
                    if self.target_site == TargetSite.RED 
                    else [FC_BLUE_1, FC_BLUE_2, FC_BLUE_3][self.inf_level.value],

                    bw=[BW_1, BW_2, BW_3][self.inf_level.value],

                    gain=[GAIN_1, GAIN_2, GAIN_3][self.inf_level.value],

                    taps_lpf=[TAPS_LPF_1, TAPS_LPF_2, TAPS_LPF_3][self.inf_level.value],

                    taps_lpf_pre=[TAPS_LPF_1_PRE, TAPS_LPF_2_PRE, TAPS_LPF_3_PRE][self.inf_level.value],

                    addr=DEFAULT_ADDR,
                    
                    filesink_path=IQ_FILE_SAVE_PATH
                )
                gnuradio.start()
                # 开始记录上次解析成功时间
                self.last_decode_time = time.time()
                # 等待gnuradio运行一段时间 轮询间隔1s
                while(True):
                    time.sleep(self.polling_interval)
                    if time.time() - self.last_decode_time > self.timeout:
                        # 超过时间阈值 认为当前等级解析失败 提升等级
                        gnuradio.stop()
                        self._update_level()
                        self.last_decode_time = 0 # 重置解析成功时间
                        del gnuradio # 删除当前gnuradio实例
                        break
            except Exception as e:
                logging.log(logging.ERROR, f"[DecodeKey] 运行gnuradio时发生异常: {e}")
                self.last_decode_time = 0 # 重置解析成功时间
                time.sleep(ERROR_SLEEP_TIME) # 休眠一段时间后重试

if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=LOG_FILE_PATH, filemode='w')

    decoder = DecodeKey(TargetSite.RED)
    decoder.attempt_decode()