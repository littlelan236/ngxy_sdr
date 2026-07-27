# pluto.tx

想要连续发送信息：
- 不能销毁sdr对象
- sdr.tx_cyclic_buffer = True 后 sdr.tx()的tx()不是阻塞的 如果后面没有死循环逻辑一样会停止
- 如果不调用tx_destroy_buffer，就算线程/进程退出，仍会继续发送

# 多进程处理

现在的gnuradio封装类使用多进程，调用is_alive可查询进程故障情况。

# 网口通信配置问题

## 国产pluto nano：

ifconfig usb0 无效

vi /etc/network/interfaces 修改配置 无效

有效的方法：

fw_setenv ipaddr 192.168.3.2


如果pluto端修改成功 但是PC Ping不通：

或ERROR: READ LINE: -32

ERROR: No context at 192.168.2.4

Scanning for IIO contexts failed: Not enough space (12)

修改PC端 静态ip：

- 打开“控制面板” → “网络和共享中心” → “更改适配器设置”。
- 找到 USB 网络适配器（可能显示为“以太网”或“RNDIS”），右键 → “属性”。
- 双击“Internet 协议版本 4 (TCP/IPv4)”。
- 如果当前是“自动获得 IP 地址”，则说明 PC 尝试通过 DHCP 获取 IP，但设备侧没有 DHCP 服务器（除非你专门配置了）。这时应该改为“使用下面的 IP 地址”，手动设置：
- IP 地址：192.168.3.100（或同网段的其他地址，不要与设备冲突）
- 子网掩码：255.255.255.0

## 原装plutosdr（有网线版）

设置网线连接静态ip：
```bash
vi /mnt/jffs2/autorun.sh

#!/bin/sh
# 删除可能冲突的 Avahi 备用地址
ifconfig eth0:avahi 0.0.0.0 down
# 配置 eth0 的静态 IP
ifconfig eth0 192.168.1.100 netmask 255.255.255.0 up

chmod +x /mnt/jffs2/autorun.sh
reboot
```

若通过这种方式配置 则不要将usb0的ip也配置到同一子网下！（192.168.3.x视为同意一子网）不然会冲突

不要忘了改PC端的静态ip

报 Unable to create buffer: -16：
看看是不是pluto sink/source用了重复的ip 如两个sink填了重复的ip

#  buffer问题

> UUUfmcomms2_source :warning: Unable to refill buffer: Connection timed out (110)

tx收到zmq传来的信息 但Rx全部是0

成因暂时未知 重启能解决 连续使用时间过长可能会出现

> 出现莫名其妙的crc16 failed 可能是全部failed 可能是几中status正常集中status错误

- 可能是tx buffer设置过小 导致数据包被截断 推荐tx3276800