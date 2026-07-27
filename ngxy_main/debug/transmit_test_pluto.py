if __name__ == "__main__":
    TEST_MODE = "signal" # signal or key
    INF_LVL = 1 # 1 or 2
    CURRENT_SITE = "RED" # RED or BLUE

    import sys, os, subprocess
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    WORKSPACE_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
    GR_DIR = os.path.join(WORKSPACE_ROOT, "gnuradio")
    SYS_PYTHON = "/usr/bin/python3"

    from ngxy_main.defs.def_signal import FC_RED, FC_BLUE, FC_RED_1, FC_BLUE_1, FC_RED_2, FC_BLUE_2
    from ngxy_main.defs.def_device import *
    from ngxy_main.drivers.extract_usb import get_all_pluto_devices, get_pluto_usb_by_serial
    from ngxy_main.drivers.frame_coder import (build_frame_ota_jamming, build_frame_ota_signal, _generate_payload_random,
        build_frame_ota_from_dataclass, AllFramesData, EnemyPosData, EnemyHpData, EnemyAmmoData,
        BuffStateData, GainsData, JammingData)

    ALL_DATA = AllFramesData(
        enemy_pos=EnemyPosData(hero_x=100, hero_y=200, engineer_x=50, engineer_y=60,
                               infantry_3_x=10, infantry_3_y=20, infantry_4_x=30, infantry_4_y=40,
                               aerial_x=1, aerial_y=2, sentry_x=3, sentry_y=4),
        enemy_hp=EnemyHpData(hero_hp=500, engineer_hp=300, infantry_3_hp=200,
                            infantry_4_hp=200, reserved=0, sentry_hp=1000),
        enemy_ammo=EnemyAmmoData(hero_ammo=50, infantry_3_ammo=100,
                                infantry_4_ammo=100, aerial_ammo=80, sentry_ammo=200),
        buff_state=BuffStateData(remaining_gold=2000, total_gold=5000, macro_bits=0xFF),
        gains=GainsData(hero_major=1, engineer_major=2, infantry_3_major=1, infantry_4_major=0, sentry_major=3),
        jamming=JammingData(key="SYUJON"),
    )
    from ngxy_main.drivers.zmq_server import  zmqServerTx
    from ngxy_main.drivers.frame_decoder_zmq import frame_decoder_zmq
    import logging
    from datetime import datetime
    from ngxy_main.defs.def_status import *

    PLUTO_DEVICE = SERIAL_PLUTO_SDR
    TIME_STR = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    LOG_FILE_PATH = f"./log_sdr_{TIME_STR}.log"

    logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.DEBUG, filename=LOG_FILE_PATH, filemode='w')

    def on_frame_decoded(data_dict_list):
        for data_dict in data_dict_list:
            status = dict_to_dataclass(data_dict)
            print(status)

    def get_device_uri(serial):
        devices = get_all_pluto_devices()
        usb = get_pluto_usb_by_serial(devices, serial)
        if usb:
            print(f"Found device {serial} at {usb}")
            return usb
        print(f"Device {serial} not found, using fallback IP")
        return None

    if CURRENT_SITE == "RED":
        if TEST_MODE == "signal":
            target_fc = FC_RED
        elif TEST_MODE == "key" and INF_LVL == 1:
            target_fc = FC_RED_1
        elif TEST_MODE == "key" and INF_LVL == 2:
            target_fc = FC_RED_2
    elif CURRENT_SITE == "BLUE":
        if TEST_MODE == "signal":
            target_fc = FC_BLUE
        elif TEST_MODE == "key" and INF_LVL == 1:
            target_fc = FC_BLUE_1
        elif TEST_MODE == "key" and INF_LVL == 2:
            target_fc = FC_BLUE_2

    if TEST_MODE == "signal":
        gr_script = os.path.join(GR_DIR, "no_interfere.py")
        device_uri = get_device_uri(PLUTO_DEVICE)
        frames = build_frame_ota_from_dataclass(ALL_DATA, mode="signal")
        decoder = frame_decoder_zmq("signal", on_frame_decoded=on_frame_decoded, zmq_address="tcp://127.0.0.1:2246", crc16_enabled=False)
    elif TEST_MODE == "key":
        gr_script = os.path.join(GR_DIR, f"pure_inf{INF_LVL}.py")
        device_uri = get_device_uri(PLUTO_DEVICE)
        frames = build_frame_ota_from_dataclass(ALL_DATA, mode="jamming")
        decoder = frame_decoder_zmq("key", on_frame_decoded=on_frame_decoded, zmq_address="tcp://127.0.0.1:2246")
                          
    server_tx = zmqServerTx(address="tcp://127.0.0.1:2244")

    gr_args = [SYS_PYTHON, gr_script]
    if device_uri:
        gr_args.append(device_uri)
    gr_args.append(str(int(target_fc)))
    gr_proc = subprocess.Popen(gr_args)
    print(f"Launched GNU Radio: {' '.join(gr_args)}")

    try:
        while True:
            server_tx.send_data(frames)
    except KeyboardInterrupt:
        gr_proc.terminate()
        gr_proc.wait()