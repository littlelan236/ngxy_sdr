import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import warnings

warnings.filterwarnings("ignore")


def plot_dB(x):
    plt.plot(10 * np.log10(np.abs(x)))


def psd_plotter(
    signals,
    labels=None,
    ylim=None,
):
    """
    绘制多个信号的功率谱密度(PSD)图

    Args:
        signals: 信号列表 [signal1, signal2, ...]
        labels: 对应的标签列表
        ylim: 绘制图表时y的范围(dB) (min,max)
    """
    if len(signals) != len(labels):
        raise ValueError("signals和labels长度必须相同")

    # 设置颜色循环
    colors = plt.cm.tab10(np.linspace(0, 1, len(signals)))

    fig, ax = plt.subplots(1, 1, figsize=(12, 8))

    # 为每个信号计算并绘制PSD
    for idx, (sig, label, color) in enumerate(zip(signals, labels, colors)):
        nfft = min(1024, len(sig))

        # 使用Welch方法计算PSD
        f, Pxx = signal.welch(
            sig,
            fs=1,
            window="hann",
            nperseg=nfft,
            noverlap=int(nfft * 0.5),
            return_onesided=False,  # 返回双边谱
            scaling="density",
        )

        # 进行fftshift将零频移到中心
        Pxx_shifted = np.fft.fftshift(Pxx)
        f_shifted = np.fft.fftshift(f)

        # 转换为dB
        Pxx_dB = 10 * np.log10(Pxx_shifted)

        if ylim is not None:
            ax.set_ylim(ylim[0], ylim[1])
        # 绘制PSD - 使用shift后的频率和功率谱
        ax.plot(
            f_shifted,
            Pxx_dB,
            label=label,
            color=color,
            alpha=0.8,
            linewidth=0.5,
        )

    plt.legend()
    plt.show()


def amplitude_scale(d, y):
    """
    对复数滤波器输出进行最小二乘实数幅度缩放，使其与期望信号的幅度匹配。

    Parameters:
    -----------
    desired : array_like, complex
        期望信号（复数），形状为 (N,) 或 (N, 1)
    output : array_like, complex
        滤波器输出信号（复数），形状为 (N,) 或 (N, 1)

    Returns:
    --------
    scaled_output : ndarray, complex
        缩放后的滤波器输出，形状与 output 相同
    scale_factor : float
        实数缩放因子
    """

    # 检查长度一致
    if len(d) != len(y):
        raise ValueError("期望信号与输出信号长度必须一致")

    # 计算最优实数缩放因子: gamma = Re(sum(d * conj(y))) / sum(|y|^2)
    numerator = np.real(np.dot(d.conj(), y))  # 等价于 Re(sum(d * conj(y)))
    denominator = np.dot(y.conj(), y).real  # 等价于 sum(|y|^2)，确保为实数
    scale_factor = numerator / denominator if denominator != 0 else 1.0

    # 应用缩放
    scaled_output = scale_factor * y

    return scaled_output, scale_factor


def nmse_calculator(desired, output, autoscale=False):
    """
    计算归一化均方误差（NMSE）的分贝值，基于文献一的方法。

    步骤：
    1. 对输出信号进行幅度缩放（使用amplitude_scale_complex_signal）
    2. 计算缩放后输出与期望信号的均方误差（MSE）
    3. 计算期望信号的功率
    4. 计算NMSE = MSE / 期望信号功率
    5. 转换为分贝值：NMSE_dB = 10 * log10(NMSE)

    Parameters:
    -----------
    desired : array_like, complex
        期望信号（复数），形状为 (N,) 或 (N, 1)
    output : array_like, complex
        滤波器输出信号（复数），形状为 (N,) 或 (N, 1)，已与期望信号时间同步
    autoscale: 是否进行自适应幅值缩放

    Returns:
    --------
    nmse_dB : float
        归一化均方误差的分贝值（负值表示误差功率小于信号功率）
    scale_factor : float
        应用的最优实数缩放因子
    scaled_output : ndarray, complex
        缩放后的滤波器输出信号
    """

    # 检验 防止输入中有nan时输出为-inf
    if np.any(np.isnan(output)) or np.any(np.isnan(desired)):
        raise ("[nmse_calculator] 输入不合法:nan")
    if np.any(np.isinf(output)) or np.any(np.isinf(desired)):
        raise ("[nmse_calculator] 输入不合法:inf")

    # 1. 幅度缩放
    if autoscale:
        scaled_output, scale_factor = amplitude_scale(desired, output)
    else:
        scaled_output = output
        scale_factor = 1.0

    # 2. 计算均方误差（MSE）
    error = desired - scaled_output
    mse = np.mean(np.abs(error) ** 2)

    # 3. 计算期望信号的功率
    desired_power = np.mean(np.abs(desired) ** 2)

    # 4. 计算NMSE（归一化均方误差）
    nmse = mse / desired_power if desired_power != 0 else float("inf")

    # 5. 转换为分贝值
    nmse_dB = 10 * np.log10(nmse) if nmse > 0 else -float("inf")

    return nmse_dB, scale_factor, scaled_output


# if __name__ == "__main__":  # 测试代码
#     sig = generate_signal_bpsk(7, 20000, 10)
#     sig_scaled = sig * 0.5
#     sig_with_noise = sig_scaled + generate_signal_awgn(len(sig_scaled), -10)
#     nmse, _, scaled_output = nmse_calculator(sig, sig_with_noise)
#     psd_plotter([sig, scaled_output], ["BPSK", "actual"], (-50, 10))
#     print(nmse)
