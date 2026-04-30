import subprocess
import re

# Available contexts:
        # 0: 0456:b673 (Analog Devices Inc. PlutoSDR (ADALM-PLUTO)), serial=104473023196000bf5ff1a00aae12c3ca8 [usb:1.25.5]

def get_all_pluto_devices():
    """获取所有 PlutoSDR 设备及其信息（包括序列号和 USB 地址）"""
    try:
        # 执行 iio_info -s
        result = subprocess.run(['iio_info', '-s'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        
        # 提取所有 PlutoSDR 设备的完整信息
        device_pattern = r'\d+:\s+0456:b673.*?serial=([a-f0-9]+)\s+\[(usb:[\d\.]+)\]'
        devices = re.findall(device_pattern, result.stdout)
        
        return devices  # 返回 [(serial, usb_addr), ...]
            
    except Exception as e:
        print(f"错误: {e}")
        return []

def get_pluto_usb_by_serial(target_serial):
    """根据设备序列号获取对应的 USB 地址"""
    devices = get_all_pluto_devices()
    for serial, usb_addr in devices:
        if serial.upper() == target_serial.upper():
            return usb_addr
    return None

def get_pluto_by_index(index=0):
    """按索引获取 PlutoSDR 设备的序列号和 USB 地址"""
    devices = get_all_pluto_devices()
    if index < len(devices):
        return devices[index]
    return None

# 使用示例
if __name__ == '__main__':
    # 获取所有设备
    all_devices = get_all_pluto_devices()
    print("所有 PlutoSDR 设备：")
    for i, (serial, usb_addr) in enumerate(all_devices):
        print(f"  [{i}] 序列号: {serial}, USB地址: {usb_addr}")
    
    # 根据序列号获取 USB 地址
    if all_devices:
        serial = all_devices[0][0]
        usb_addr = get_pluto_usb_by_serial(serial)
        print(f"\n序列号 {serial} 的 USB 地址: {usb_addr}")