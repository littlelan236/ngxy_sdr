from typing import Iterable
import logging
from pathlib import Path

def _log(loglevel, strin):
    """进行一次logging.log与一次print"""
    logging.log(loglevel, strin)
    print(strin)

def _makesure_path_exist(filename):
    file_path = Path(filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.touch(exist_ok=True)
    return file_path

def _reverse_string(s): 
    return s[::-1]

def print_hex_by_byte(data: bytes | bytearray | Iterable[int]):
    """测试用函数 以十六进制按字节打印"""
    if data is None:
        print(None)
    def _normalize_data(data: bytes | bytearray | Iterable[int]) -> bytes:
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
            # 处理可迭代对象中的混合类型（int 或 bytes）
            result = bytearray()
            for item in data:
                if isinstance(item, (bytes, bytearray)):
                    result.extend(item)          # 直接扩展字节序列
                elif isinstance(item, int):
                    result.append(item & 0xFF)   # 取低 8 位
                else:
                    raise TypeError(f"Unsupported type in iterable: {type(item)}")
            return bytes(result)
    data = _normalize_data(data)
    for byte in data:
        print('\\'+str(hex(byte)), end="")
    print()