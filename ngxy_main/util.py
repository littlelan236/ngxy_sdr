# 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

import logging
from typing import Iterable

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