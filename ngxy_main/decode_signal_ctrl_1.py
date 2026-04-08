"""
解调干扰波板子的控制逻辑
解调干扰波的gnuradio->python地址为"tcp://127.0.0.1:2234"

实例化了一个内置gnuradio解调干扰波的类
通过传参控制解调干扰波参数
在某一等级尝试一定时间后没有成功解析出秘钥就提升等级 关闭当前gnuradio类 改参数重新初始化
三级仍失败则再从一级开始
"""

import time
from frame_decoder import frame_decoder
from final_no_gui import GnuradioClass
from signal_def import *
from zmq_server import zmqServerTx
from status_def import *

import logging
from datetime import datetime

ADDR_REPORT = "tcp://127.0.0.1:2238" # 上报地址
ADDR_PLUTO = '192.168.2.2' # pluto地址
ADDR_GNURADIO = "tcp://127.0.0.1:2234" # gnuradio发送解析结果的地址
TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE_PATH = f"log_sdr_1_{TIME_STR}.log"
ERROR_SLEEP_TIME = 5 # 运行gnuradio发生异常时的休眠时间

class DecodeSignal:
    def __init__(self, site:TargetSite):
        self.target_site = site
        self.decoder = frame_decoder(
            "signal",
            zmq_address=ADDR_GNURADIO,
            on_frame_decoded=self._handle_frame_decoded
        )
        self.zmq_tx = zmqServerTx(ADDR_REPORT) # 用于传递最终的信息

    def _handle_frame_decoded(self, data_dict_list):
        """处理成功解析的帧数据"""
        for data_dict in data_dict_list:
            # 更新上次成功解析的时间
            self.last_decode_time = time.time()
            # 输出解析结果
            logging.log(logging.INFO, f"[DecodeSignal] 解析成功: {data_dict}")

            # 提交解析结果
            if data_dict is not None:
                self.zmq_tx.send_data(data_dict)
            

    def attempt_decode(self):
        """尝试解析秘钥的主逻辑"""
        while True:
            try:
                TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                IQ_FILE_SAVE_PATH =f"raw_{self.target_site.name}_{self.inf_level.name}_1_{TIME_STR}.iq" # 保存IQ数据的文件路径 每一轮更新
                # 创建gnuradio实例
                logging.log(logging.INFO, f"[DecodeSignal] 创建gnuradio实例 目标队伍颜色: {self.target_site.name}, 干扰等级: {self.inf_level.name}")
                gnuradio = GnuradioClass(
                    fc= FC_RED 
                    if self.target_site == TargetSite.RED 
                    else FC_BLUE,

                    bw=BW_SIG,

                    gain=GAIN_SIG,

                    taps_lpf=TAPS_LPF_SIG,

                    taps_lpf_pre=TAPS_LPF_SIG_PRE,

                    addr_pluto=ADDR_PLUTO,

                    addr_zmq=ADDR_GNURADIO,
                    
                    filesink_path=IQ_FILE_SAVE_PATH
                )
                gnuradio.start()

            except Exception as e:
                logging.log(logging.ERROR, f"[DecodeSignal] 运行gnuradio时发生异常: {e}")
                self.last_decode_time = 0 # 重置解析成功时间
                time.sleep(ERROR_SLEEP_TIME) # 休眠一段时间后重试

if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=LOG_FILE_PATH, filemode='w')

    decoder = DecodeSignal(TargetSite.RED)
    decoder.attempt_decode()