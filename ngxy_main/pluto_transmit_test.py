if __name__ == "__main__":

    from frame_coder import build_frame_ota_jamming, build_frame_ota_signal, _generate_payload_random
    from zmq_server import  zmq_server_tx
    from frame_decoder import frame_decoder

    server_tx = zmq_server_tx() # port 2235
    decoder = frame_decoder("signal") # port 2236

    # 生成空口帧的比特流
    # frames = build_frame_ota_jamming("RM2026")
    frames = build_frame_ota_signal(_generate_payload_random())

    while True:
        server_tx.send_data(frames)