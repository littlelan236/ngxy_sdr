# pluto.tx
想要连续发送信息：
1,不能销毁sdr对象
2,sdr.tx_cyclic_buffer = True 后 sdr.tx()的tx()不是阻塞的 如果后面没有死循环逻辑一样会停止
3,如果不调用tx_destroy_buffer，就算线程/进程退出，仍会继续发送

# 区域赛版本

现在的gnuradio封装类使用多进程，调用is_alive可查询进程故障情况。