import subprocess
import re

# Available contexts:
        # 0: 0456:b673 (Analog Devices Inc. PlutoSDR (ADALM-PLUTO)), serial=104473023196000bf5ff1a00aae12c3ca8 [usb:1.25.5]

def get_new_pluto_usb():
    """获取新插入的 PlutoSDR 设备的 USB 地址"""
    try:
        # 执行 iio_info -s
        result = subprocess.run(['iio_info', '-s'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        
        # 查找所有 PlutoSDR 设备
        devices = re.findall(r'\d+:\s+0456:b673.*?\[(usb:[\d\.]+)\]', result.stdout)
        
        if len(devices) >= 2:
            # 返回第二个设备（新设备）
            return devices[1]
        elif len(devices) == 1:
            return devices[0]
        else:
            return None
            
    except Exception as e:
        print(f"错误: {e}")
        return None

# 使用
usb_addr = get_new_pluto_usb()
if usb_addr:
    print(f"新设备 USB 地址: {usb_addr}")
    # 提取纯数字部分
    numbers = usb_addr.split(':')[1].split('.')
    print(f"总线: {numbers[0]}, 设备: {numbers[1]}")