# 日志/文件保存说明

# 日志

>>zmq_server
- zmq_buffer -> zmq_server_rx_buffer
DEBUG：读取
WARNING：zmq_server_rx_buffer大小超上限 需要加快读取频率
- zmq_server.read_data:
DEBUG:读取

>>frame_decoder
- zmq_server_rx_buffer -> buffer_bits
DEBUG：读取
- read_bytes_from_bits方法
DEBUG:index超过边界
- ota_frame_sync
DEBUG:是否识别OTA帧头 识别的个数 （在buffer_bits中correlate）
INFO:成功读取完整的OTA帧 （没有超idx上限）
DEBUG:若长时间没有读到有效空口帧 丢弃所有buffer_payload中的数据 **这个必须是DEBUG 不然会造成大量io**
DEBUG：循环中播报当前buffer_payload大小
- _frame_sync_serial
INFO:未通过crc校验
INFO:cmd_id无效
- 主循环
DEBUG:串口帧未识别
INFO:串口帧被识别（通过crc8校验）
INFO：识别的串口帧解析失败/成功
WARNING:回调函数报错

>>final_no_gui (GnuradioClass)
ERROR:gnuradio init/start/stop错误

>>decode_key_ctrl
INFO:创建gnuradio实例
ERROR：主循环中发生错误（大概率gnuradio的问题）
INFO:尝试提升干扰等级
INFO:解析成功 输出解析出的dict
WARNING:解析成功 但解析出的dict中没有key
INFO:秘钥验证中/验证成功
INFO:成功解析两种秘钥 退出秘钥解析
# 文件

>>iq文件
只保留原始iq文件
场间调试使用带图像版本的gnuradio读取文件

