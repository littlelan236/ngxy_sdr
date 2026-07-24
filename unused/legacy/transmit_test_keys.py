"""测试轮换秘钥 实时性和控制逻辑 附带日志输出"""

if __name__ == "__main__":

    from frame_coder import build_frame_ota_jamming, build_frame_ota_signal, _generate_payload_random
    from zmq_server import  zmqServerTx
    from frame_decoder import frame_decoder
    import time
    import logging
    from datetime import datetime

    # 初始化日志
    TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    LOG_FILE_PATH = f"./log/log_transmit_test_keys_{TIME_STR}.log"
    logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=LOG_FILE_PATH, filemode='w')


    server_tx = zmqServerTx() # port 2235
    decoder = frame_decoder("signal") # port 2236

    while True:
        # 生成空口帧的比特流
        # frames = build_frame_ota_jamming("RM2022")
        frames = build_frame_ota_signal(_generate_payload_random())
        logging.log(logging.INFO, f"发送信息帧")
        server_tx.send_data(frames)
        
        time.sleep(0.5)