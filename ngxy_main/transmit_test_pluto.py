if __name__ == "__main__":

    from frame_coder import build_frame_ota_jamming, build_frame_ota_signal, _generate_payload_random
    from zmq_server import  zmqServerTx
    from frame_decoder import frame_decoder
    import logging
    from datetime import datetime
    from status_def import *

    TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    LOG_FILE_PATH = f"./log/log_sdr_{TIME_STR}.log"

    logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO, filename=LOG_FILE_PATH, filemode='w')

    def on_frame_decoded(data_dict_list):
        logging.log(logging.INFO, f"解析成功: {data_dict_list}")
        for data_dict in data_dict_list:
            status = dict_to_dataclass(data_dict)
            logging.log(logging.INFO, f"解析结果: {status}")


    server_tx = zmqServerTx() # port 2235
    decoder = frame_decoder("signal", on_frame_decoded=on_frame_decoded) # port 2236

    # 生成空口帧的比特流
    # frames = build_frame_ota_jamming("RM2026")
    frames = build_frame_ota_signal(_generate_payload_random())

    while True:
        server_tx.send_data(frames)
    