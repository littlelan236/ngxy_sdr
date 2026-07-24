项目架构总览
这是一个 RoboMaster 2026 赛季的无线通信子系统，用于通过 SDR 硬件（PlutoSDR / RTL-SDR）进行空口信号的收发和解析，最终通过 ROS2 将敌方机器人信息广播出去。
目录结构
ngxy_sdr/
├── ngxy_main/                    # 主项目代码
│   ├── main_gnuradio.py          # 主控入口（生产环境）
│   ├── grc_main.py               # GNU Radio 流图封装（多进程）
│   ├── grc_hard_decision_block.py # GNU Radio 硬判决嵌入式模块
│   ├── defs/                     # 定义层
│   │   ├── def_frame.py          # 帧协议定义（SOF, access code, 字段长度, CRC）
│   │   ├── def_signal.py         # 射频参数（载频, 带宽, 滤波器增益）
│   │   ├── def_taps.py           # FIR 滤波器系数
│   │   └── def_status.py         # 状态 dataclass（位置/血量/弹药/Buff/密码等）
│   ├── drivers/                  # 驱动层
│   │   ├── frame_coder.py        # 发射端：协议帧编码 → 空口帧 → 比特流
│   │   ├── frame_decoder_zmq.py  # 接收端：ZMQ比特流 → 帧同步 → 协议解码
│   │   ├── zmq_server.py         # ZMQ PUB/SUB 封装（Tx 和 Rx）
│   │   ├── crc.py                # CRC8/CRC16 校验
│   │   ├── extract_usb.py        # 通过 iio_info 发现 PlutoSDR USB 地址
│   │   ├── pluto_ctrl.py         # PlutoSDR/RTL-SDR 硬件控制（adi/rtlsdr 库）
│   │   ├── wireless_ros2_adaptor.py # ROS2 适配器（实际代码在远程 Ubuntu 机器）
│   │   └── util.py               # 工具函数
│   ├── debug/                    # 调试脚本
│   │   └── transmit_test_pluto.py # 发射测试脚本
│   └── bringup/                  # 部署启动脚本（bash）
├── tools/                        # 工具与 GRC 工程
│   ├── gnuradio/                 # GRC 工程文件（.grc + 生成的 .py）
│   ├── generate_filesource.py    # 生成干扰波比特流文件
│   ├── max_ros2_publish_gap.py   # 日志分析工具
│   └── slice_gr_complex_head.py  # IQ文件切片工具
└── rec/                          # IQ 录制文件存储
数据流架构
                        【接收链路】
PlutoSDR → GRC流图(IIO Source → 预滤波 → FM解调 → 低通滤波 → 符号同步 → 硬判决 → pack_bits)
    → ZMQ PUB (tcp://127.0.0.1:2236/2235)
        → frame_decoder_zmq (SUB, 比特流缓存 → access code相关检测 → OTA帧提取 → 串口帧同步 → CRC校验 → payload解码)
            → 回调函数 on_frame_decoded(data_dict_list)
                → main_gnuradio 主循环 (ros_publish_queue)
                    → ROS2 publish_wireless_result(json)

                        【发射链路】
main_gnuradio / transmit_test_pluto.py
    → frame_coder (payload dict → 串口帧编码 → 空口帧封装 → 比特流)
        → zmq_server.zmqServerTx (PUB)
            → (外部 GNURadio TX 流图 SUB 接收并发射)
核心设计
1. 多进程隔离：每个 SDR 板子（信号接收 rx_sig、干扰接收 rx_inf、备用 backup）各跑一个独立的 multiprocessing.Process，内含完整 GRC 流图，通过 ZMQ 与主进程通信，避免 GRC 的阻塞式 run() 影响主控。
2. 双通路通信：
- 信息波（signal）：载频 433.2/433.92 MHz，传输敌方位置、血量、弹药、Buff 等结构化数据
- 干扰波（jamming）：传输密码/密钥（6字节 key），用于干扰对方通信
3. 帧协议：两层结构 —— 空口帧（8字节 access code + 长度 + payload）内嵌串口帧（SOF + CRC8帧头 + cmd_id + data + CRC16）。
4. 阵营识别：先从 ROS 获取己方红/蓝阵营，失败则通过分别在红蓝频率上短暂接收解码来探测。
5. 干扰等级自动切换：3 级干扰对应不同载频和带宽，ROS 可实时下发切换指令，也支持超时自动升级。
6. 设备容灾：3 块 PlutoSDR（sig/inf/backup），主设备故障自动切换到备用板，记录错误次数。