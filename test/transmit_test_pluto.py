if __name__ == "__main__":

    from frame_coder import build_frame_ota_jamming, build_frame_ota_signal, _generate_payload_random
    from zmq_server import  zmqServerTx
    from frame_decoder import frame_decoder
    import logging
    from datetime import datetime
    from def_status import *

    TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    LOG_FILE_PATH = f"./log_sdr_{TIME_STR}.log"

    logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.DEBUG, filename=LOG_FILE_PATH, filemode='w')

    def on_frame_decoded(data_dict_list):
        # logging.log(logging.INFO, f"解析成功: {data_dict_list}")
        print(data_dict_list)
        for data_dict in data_dict_list:
            status = dict_to_dataclass(data_dict)
            # logging.log(logging.INFO, f"解析结果: {status}")
            print(status)


    server_tx = zmqServerTx(address="tcp://127.0.0.1:2235") # port 2234
    decoder = frame_decoder("signal", on_frame_decoded=on_frame_decoded, zmq_address="tcp://127.0.0.1:2236", crc16_enabled=False) # port 2236
    # decoder = frame_decoder("key", on_frame_decoded=on_frame_decoded, zmq_address="tcp://127.0.0.1:2234") # port 2236


    # 生成空口帧的比特流
    # frames = build_frame_ota_jamming("RM2025")
    frames = build_frame_ota_signal(_generate_payload_random())

    while True:
        server_tx.send_data(frames)
    