import numpy as np
from rrc import srrc_design
from scipy import signal


_FSK_MAPPING = np.array([-4.0, -3.0, 3.0, 4.0], dtype=np.float64)
_SRRC_CACHE = {}


def _get_srrc_taps(sps: int) -> np.ndarray:
    taps = _SRRC_CACHE.get(sps)
    if taps is None:
        taps = srrc_design(sps, True)
        _SRRC_CACHE[sps] = taps
    return taps

def generate_signal_4rrcfsk(sps, symbol_num, power_dB=0):
    """
    生成经过一个rrc的FSK信号 使用归一化频率
    返回值除了信号数组外还返回符号数组 以便后续分析
    """
    assert sps == 4 or sps == 7 or sps == 8 or sps == 10
    correction = -20  # 换算到绝对功率
    srrc = _get_srrc_taps(sps)
    sym = np.random.randint(0, 4, symbol_num)
    fsk = _FSK_MAPPING[sym].copy()
    amplitude = np.sqrt(10 ** (0.1 * (power_dB + correction)))
    fsk *= amplitude
    sym_upsampled = np.zeros(symbol_num * sps, dtype=np.float64)
    sym_upsampled[::sps] = fsk[: len(sym_upsampled[::sps])]
    shaped = signal.fftconvolve(srrc, sym_upsampled)

    # print(sym)
    # srrc = srrc_design(sps, False)
    # shaped = signal.fftconvolve(shaped, srrc, mode="same")
    # import matplotlib.pyplot as plt
    # plt.plot(sym_upsampled)
    # plt.plot(shaped[(len(srrc) - 1) // 2:])
    # plt.show()

    return shaped, sym

def generate_signal_bpsk(sps, symbol_num, power_dB=0):
    """
    生成经过脉冲成型的BPSK信号 使用归一化频率
    """
    assert sps == 5 or sps == 6 or sps == 7 or sps == 8 or sps == 10
    correction = -7  # 换算到绝对功率
    srrc = srrc_design(sps)
    sym = np.random.randint(0, 2, symbol_num)
    bpsk = sym * 2 - 1
    amplitude = np.sqrt(np.pow(10, 0.1 * (power_dB + correction)))
    bpsk = amplitude * np.astype(bpsk, np.float64)
    sym_upsampled = np.zeros(symbol_num * sps)
    sym_upsampled[::sps] = bpsk[: len(sym_upsampled[::sps])]
    shaped = signal.fftconvolve(srrc, sym_upsampled)
    shaped = signal.fftconvolve(srrc, shaped)
    # shaped = shaped[2 * 10 * sps :]
    # plt.plot(sym_upsampled)
    # plt.plot(shaped)
    # plt.show()
    return shaped

def generate_signal_awgn(num_samples, power_dB=0):
    """
    生成噪声
    """
    amplitude = np.sqrt(10 ** (0.1 * power_dB))
    return np.random.normal(loc=0.0, scale=amplitude, size=num_samples)


def generate_signal_complex_exp(num_samples, freq, amplitude):
    """生成标准复指数信号"""
    t = np.arange(num_samples)
    sig = amplitude * np.exp(1j * 2 * np.pi * freq * t)
    return sig

if __name__ == "__main__":  # 测试代码
    generated_signal = generate_signal_4rrcfsk(sps=8, symbol_num=1000, power_dB=0)