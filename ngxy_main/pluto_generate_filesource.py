"""生成干扰波比特流文件"""

if __name__ == "__main__":

    from frame_coder import build_frame_ota_jamming, build_frame_ota_signal
    from zmq_server import  zmq_server_tx
    import numpy as np

    server_tx = zmq_server_tx() # port 2235

    # 生成空口帧的比特流
    frames = build_frame_ota_jamming("RM2026")
    print(frames)
    print(frames.dtype)
    # 文件名
    filename = "interfere_1"
    frames = np.tile(frames, 1000).flatten().tofile(filename) # 重复信息防止信息过短导致射频信号质量低