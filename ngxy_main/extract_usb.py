import subprocess
import re

SERIAL_PLUTO_NANO_2 = "03df62bf070f233332d76ab70f173b2b2a"
SERIAL_PLUTO_SDR = "104473023196000bf5ff1a00aae12c3ca8"
SERIAL_PLUTO_NANO_1 = None
SERIAL_PLUTO_NANO_0 = None

def get_all_pluto_devices(timeout=15):
    """获取所有 PlutoSDR 设备及其信息（包括序列号和 USB 地址）"""
    # 执行 iio_info -s
    result = subprocess.run(['iio_info', '-s'], 
                            capture_output=True, 
                            text=True, 
                            timeout=timeout)
    
    # 提取所有 PlutoSDR 设备的完整信息
    device_pattern = r'\d+:\s+0456:b673.*?serial=([a-f0-9]+)\s+\[(usb:[\d\.]+)\]'
    devices = re.findall(device_pattern, result.stdout)
    
    return devices  # 返回 [(serial, usb_addr), ...]

def get_pluto_usb_by_serial(devices, target_serial):
    """根据设备序列号获取对应的 USB 地址"""
    for serial, usb_addr in devices:
        if serial.upper() == target_serial.upper():
            return usb_addr
    return None

# 使用示例
if __name__ == '__main__':
    # 获取所有设备
    all_devices = get_all_pluto_devices()
    usb_name = get_pluto_usb_by_serial(all_devices, SERIAL_PLUTO_NANO_2)
    print(usb_name)