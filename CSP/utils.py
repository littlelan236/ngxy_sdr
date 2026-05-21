import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import fftconvolve

"""使用FSM方法 不是Pysdr上给的代码 改成了可以处理任意alpha的版本"""


def csf_estimator(
    samples1, samples2, alphas, Nw=4096, do_plot=False, report_progress=False
):
    """
    计算CSF
    Args:
        samples: 信号序列
        alphas: 需要在哪些循环频率上计算
        Nw: 窗口大小
    Returns:
        CSF: 行为alpha 列为freq
        freq: 对应的频率值
    """
    N = len(samples1)  # signal length
    assert len(samples1) == len(samples2)
    Nw = min(Nw, N)
    window = np.hanning(Nw)

    CSF = np.zeros((len(alphas), N), dtype=complex)
    for i in range(len(alphas)):
        if report_progress and i % 5 == 0:
            print(f"{i}/{len(alphas)}")
        # 注意 要想获得X(f + a/2)需要的频率偏移是-a/2
        X1 = np.fft.fftshift(np.fft.fft(freq_shift(samples1, -alphas[i] / 2)))
        X2 = np.fft.fftshift(np.fft.fft(freq_shift(samples2, alphas[i] / 2)))
        SCF_slice = X1 * np.conj(X2)
        CSF[i, :] = fftconvolve(SCF_slice, window, mode="same")
    freq = np.fft.fftshift(np.fft.fftfreq(N))
    if do_plot:
        CSF_plot = np.abs(CSF)
        CSF_plot[0,:] = 0
        extent = (-0.5, 0.5, float(np.max(alphas)), float(np.min(alphas)))
        plt.imshow(
            CSF_plot,
            aspect="auto",
            extent=extent,
            vmax=np.max(CSF_plot) / 2,
            interpolation="none",
        )
        plt.xlabel("Frequency [Normalized Hz]")
        plt.ylabel("Cyclic Frequency [Normalized Hz]")
        plt.show()
    return CSF, freq


def csf_conj_estimator(
    samples1, samples2, alphas, Nw=4096, do_plot=False, report_progress=False
):
    """
    计算共轭CSF
    Args:
        samples: 信号序列
        alphas: 需要在哪些循环频率上计算
        Nw: 窗口大小
    Returns:
        CSF: 行为alpha 列为freq
        freq: 对应的频率值
    """
    N = len(samples1)  # signal length
    assert len(samples1) == len(samples2)
    Nw = min(Nw, N)
    window = np.hanning(Nw)

    # 由于下边的操作 这里矩阵长度比非共轭小1
    CSF = np.zeros((len(alphas), N - 1), dtype=complex)
    for i in range(len(alphas)):
        if report_progress and i % 5 == 0:
            print(f"{i}/{len(alphas)}")
        # 这两个都是X(f+a/2)
        X1 = np.fft.fftshift(np.fft.fft(freq_shift(samples1, -alphas[i] / 2)))
        X2 = np.fft.fftshift(np.fft.fft(freq_shift(samples2, -alphas[i] / 2)))
        # 将第二个变为X(a/2-f) 由于使用偶数窗口长度的FFT 所以需要去掉最大的负值f 也即第一个元素
        X2 = X2[1:]
        X2 = np.flip(X2)
        # 相应地也得去掉X1的第一个
        X1 = X1[1:]
        SCF_slice = X1 * X2
        CSF[i, :] = fftconvolve(SCF_slice, window, mode="same")
    freq = np.fft.fftshift(np.fft.fftfreq(N))
    freq = freq[1:]
    if do_plot:
        CSF_plot = np.abs(CSF)
        CSF_plot[0,:] = 0
        extent = (-0.5, 0.5, float(np.max(alphas)), float(np.min(alphas)))
        plt.imshow(
            CSF_plot,
            aspect="auto",
            extent=extent,
            vmax=np.max(CSF_plot) / 2,
            interpolation="none",
        )
        plt.xlabel("Frequency [Normalized Hz]")
        plt.ylabel("Cyclic Frequency [Normalized Hz]")
        plt.show()
    return CSF, freq


def scf_estimator(samples, alphas, Nw=4096, do_plot=False, report_progress=False):
    ret = csf_estimator(
        samples,
        samples,
        alphas,
        Nw=Nw,
        do_plot=do_plot,
        report_progress=report_progress,
    )
    return ret


def scf_conj_estimator(samples, alphas, Nw=4096, do_plot=False, report_progress=False):
    ret = csf_conj_estimator(
        samples,
        samples,
        alphas,
        Nw=Nw,
        do_plot=do_plot,
        report_progress=report_progress,
    )
    return ret


def psd_estimator(samples, Nw=4096):
    alphas = np.array([0])
    N = len(samples)  # signal length
    Nw = min(N, Nw)
    Noverlap = int(2 / 3 * Nw)  # block overlap
    num_windows = int((N - Noverlap) / (Nw - Noverlap))  # Number of windows
    window = np.hanning(Nw)

    SCF = np.zeros((len(alphas), Nw), dtype=complex)
    for ii in range(len(alphas)):  # Loop over cyclic frequencies
        neg = samples * np.exp(-1j * np.pi * alphas[ii] * np.arange(N))
        pos = samples * np.exp(1j * np.pi * alphas[ii] * np.arange(N))
        for i in range(num_windows):
            pos_slice = window * pos[i * (Nw - Noverlap) : i * (Nw - Noverlap) + Nw]
            neg_slice = window * neg[i * (Nw - Noverlap) : i * (Nw - Noverlap) + Nw]
            SCF[ii, :] += np.fft.fft(neg_slice) * np.conj(
                np.fft.fft(pos_slice)
            )  # Cross Cyclic Power Spectrum
    SCF = np.fft.fftshift(SCF, axes=1)
    SCF = SCF.flatten()
    freq = np.fft.fftshift(np.fft.fftfreq(Nw))
    return SCF, freq


def csd_estimator(samples1, samples2, Nw=4096):
    """注意CSF(x,y)!=CSF(y,x)"""
    alphas = np.array([0])
    assert len(samples1) == len(samples2)
    N = len(samples1)  # signal length
    Nw = min(N, Nw)
    Noverlap = int(2 / 3 * Nw)  # block overlap
    num_windows = int((N - Noverlap) / (Nw - Noverlap))  # Number of windows
    window = np.hanning(Nw)

    CSF = np.zeros((len(alphas), Nw), dtype=complex)
    for ii in range(len(alphas)):  # Loop over cyclic frequencies
        neg = samples1 * np.exp(-1j * np.pi * alphas[ii] * np.arange(N))
        pos = samples2 * np.exp(1j * np.pi * alphas[ii] * np.arange(N))
        for i in range(num_windows):
            pos_slice = window * pos[i * (Nw - Noverlap) : i * (Nw - Noverlap) + Nw]
            neg_slice = window * neg[i * (Nw - Noverlap) : i * (Nw - Noverlap) + Nw]
            CSF[ii, :] += np.fft.fft(neg_slice) * np.conj(np.fft.fft(pos_slice))
    CSF = np.fft.fftshift(CSF, axes=1)
    CSF = CSF.flatten()
    freq = np.fft.fftshift(np.fft.fftfreq(Nw))
    return CSF, freq


def freq_shift(sig, f):
    """对信号进行频率偏移"""
    t = np.arange(len(sig))
    sig = sig * np.exp(1j * 2 * np.pi * f * t)
    return sig


def to_spectral(impulse_response):
    """
    冲激响应转频率响应
    输出的结果经过fftshift
    """
    spectual = np.fft.fft(impulse_response)
    freq = np.fft.fftfreq(len(impulse_response))
    spectual = np.fft.fftshift(spectual)
    freq = np.fft.fftshift(freq)
    return spectual, freq


def to_tempral(spectual_response):
    """
    频率响应转冲激响应
    输入值应进行fftshift
    时间间隔为1/fs=1
    """
    spectual_response = np.fft.ifftshift(spectual_response)
    tempral = np.fft.ifft(spectual_response)
    tempral = np.fft.fftshift(tempral)
    return tempral


def get_lms_mumax(x, cutoff, calculate_times=100):
    """
    计算lms中学习率最大值
    Args:
        x: 输入信号
        cutoff: 滤波器抽头数
        calculate_times: 对前多少组迹取平均以得出最终结果
    """
    tr_estimated = 0.0
    for i in range(calculate_times):
        xn = x[:cutoff]
        x = x[cutoff:]
        tr_estimated += np.sum(np.abs(xn) ** 2) / calculate_times
    return 1 / tr_estimated


def apply_fresh_filter(signal, alphas, betas, taps_alphas, taps_betas):
    """
    执行FRESH滤波
    """
    assert (
        len(alphas) == len(taps_alphas) or len(alphas) == 1 and taps_alphas is not None
    )
    assert len(betas) == len(taps_betas) or len(betas) == 1 and taps_betas is not None
    filtered = None
    for i, alpha in enumerate(alphas):
        x_shifted = freq_shift(signal, alpha)
        if filtered is None:
            filtered = fftconvolve(taps_alphas[i], x_shifted)
        else:
            filtered += fftconvolve(taps_alphas[i], x_shifted)
    for i, beta in enumerate(betas):
        x_shifted = freq_shift(np.conj(signal), beta)
        if filtered is None:
            filtered = fftconvolve(taps_betas[i], x_shifted)
        else:
            filtered += fftconvolve(taps_betas[i], x_shifted)
    return filtered


def join_taps(taps_alpha, taps_beta):
    """将不同循环频率的滤波器抽头拼接成一个列向量 用于自适应FRESH滤波器"""
    taps = None
    for t_a in taps_alpha:
        if taps is None:
            taps = np.array(t_a)
        else:
            taps = np.concatenate((taps, t_a))
    for t_b in taps_beta:
        if taps is None:
            taps = np.array(t_b)
        else:
            taps = np.concatenate((taps, t_b))
    return taps


def flip_taps(taps, num_cyc_freqs, cutoff):
    """
    用于将预训练的taps翻转 给lms用
    Args:
        num_sys_freqs: 循环频率个数
        cutoff: 单个FIR的抽头数
    """
    taps = taps.reshape([num_cyc_freqs, cutoff])
    flipt = None
    for t in taps:
        if flipt is None:
            flipt = np.flip(t)
        else:
            flipt = np.vstack([flipt, np.flip(t)])
    return flipt.flatten()


if __name__ == "__main__":  # 测试代码
    # N = 100000 # number of samples to simulate
    # f_offset = 0.2 # Hz normalized
    # sps = 20 # cyclic freq (alpha) will be 1/sps or 0.05 Hz normalized

    # symbols = np.random.randint(0, 2, int(np.ceil(N/sps))) * 2 - 1 # random 1's and -1's
    # bpsk = np.repeat(symbols, sps)  # repeat each symbol sps times to make rectangular BPSK
    # bpsk = bpsk[:N]  # clip off the extra samples
    # bpsk = bpsk * np.exp(2j * np.pi * f_offset * np.arange(N)) # Freq shift up the BPSK, this is also what makes it complex
    # noise = np.random.randn(N) + 1j*np.random.randn(N) # complex white Gaussian noise
    # samples = bpsk + 0.1*noise  # add noise to the signal

    from signal_generator import generate_signal_bpsk, generate_signal_awgn, generate_signal_4rrcfsk
    # samples = generate_signal_bpsk(10, 32768, 0)
    samples, sym = generate_signal_4rrcfsk(10, 32768, 0)
    samples = freq_shift(samples, 0.08)
    print('generated')
    _ = scf_conj_estimator(samples, np.arange(-0.3, 0.3, 1/1000), do_plot=True, report_progress=True)