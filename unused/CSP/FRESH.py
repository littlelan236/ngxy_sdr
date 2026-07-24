import numpy as np
import matplotlib.pyplot as plt
from signal_generator import generate_signal_bpsk, generate_signal_awgn, generate_signal_4rrcfsk
from plotter import nmse_calculator, psd_plotter, plot_dB
from utils import (
    freq_shift,
    scf_estimator,
    scf_conj_estimator,
    csf_estimator,
    csf_conj_estimator,
    to_tempral,
    to_spectral,
    apply_fresh_filter,
)
from scipy.signal import fftconvolve


def fresh_filter_taps_design(
    sig, desired, alphas, betas, cutoff=129, Nw=4096, decimation=64
):
    """
    设计FRESH滤波器抽头
    Args:
        sig:输入信号
        desired:参考信号
        cut_off:滤波器抽头个数
        Nw:FSM窗口大小
        decimation:FSM抽样周期
    Returns:
        fresh_tempral_alphas, fresh_tempral_betas: 两个list list中套的小list是实际的taps 按给的循环频率的顺序排序
    """

    def get_scf_alphas(alphas, betas):
        """计算出S矩阵中Sx部分所有需要的循环频率值"""
        scf_alphas = []
        for alpha_y in alphas:
            for alpha_x in alphas:
                scf_alphas.append(alpha_y - alpha_x)
        for beta_y in betas:
            for beta_x in betas:
                scf_alphas.append(beta_y - beta_x)
        return np.array(scf_alphas)

    def get_conj_scf_alphas(alphas, betas):
        """计算出S矩阵中S*x部分所有需要的循环频率值"""
        scf_alphas = []
        for beta_y in betas:
            for alpha_x in alphas:
                scf_alphas.append(beta_y - alpha_x)
        for alpha_y in alphas:
            for beta_x in betas:
                scf_alphas.append(beta_x - alpha_y)
        return np.array(scf_alphas)

    def get_scf_fs(f, alphas, betas):
        """计算出S矩阵中Sx部分所有需要的频率值 由于SCF计算出的f由FFT窗口决定 不正好是所需的值 故需要插值"""
        scf_fs = []
        for alpha_y in alphas:
            for alpha_x in alphas:
                scf_fs.append(f - (alpha_y + alpha_x) / 2)
        for beta_y in betas:
            for beta_x in betas:
                scf_fs.append(-f + (beta_y + beta_x) / 2)
        scf_fs = np.array(scf_fs)
        return scf_fs

    def get_conj_scf_fs(f, alphas, betas):
        """计算出S矩阵中S*x部分所有需要的频率值 由于SCF计算出的f由FFT窗口决定 不正好是所需的值 故需要插值"""
        scf_fs = []
        for beta_y in betas:
            for alpha_x in alphas:
                scf_fs.append(f - (beta_y + alpha_x) / 2)
        for alpha_y in alphas:
            for beta_x in betas:
                scf_fs.append(f - (beta_x + alpha_y) / 2)
        scf_fs = np.array(scf_fs)
        return scf_fs

    def get_csf_alphas(alphas):
        """计算出B矩阵所有非共轭部分需要的循环频率值"""
        csf_alphas = []
        for alpha in alphas:
            csf_alphas.append(alpha)
        return np.array(csf_alphas)

    def get_conj_csf_alphas(betas):
        """计算出B矩阵所有共轭部分需要的循环频率值"""
        csf_alphas = []
        for beta in betas:
            csf_alphas.append(beta)
        return np.array(csf_alphas)

    def get_csf_fs(f, alphas):
        """计算出B矩阵所有非共轭部分需要的频率值"""
        csf_fs = []
        for alpha in alphas:
            csf_fs.append(f - alpha / 2)
        csf_fs = np.array(csf_fs)
        return csf_fs

    def get_conj_csf_fs(f, betas):
        """计算出B矩阵所有共轭部分需要的频率值"""
        csf_fs = []
        for beta in betas:
            csf_fs.append(f - beta / 2)
        csf_fs = np.array(csf_fs)
        return csf_fs

    def f_interp(slice, f, freqs):
        """进行f插值处理"""
        # 利用SCF/CSF的循环性 对f进行折叠处理
        assert len(slice) == len(freqs)
        f_folded = f - np.round(f)
        if f_folded > 0.5:
            f_folded -= 1.0
        elif f_folded < -0.5:
            f_folded += 1.0

        # 查找f_folded在freqs中的位置
        if f_folded <= freqs[0]:
            return slice[0]
        elif f_folded >= freqs[-1]:
            return slice[-1]
        else:
            result = np.interp(f_folded, freqs, slice)
            return result.item()

    def get_b_matrix(f, alphas, betas, csf, csf_conj, freq_csf, freq_conj_csf):
        """计算B矩阵"""
        b_matrix = []
        csf_fs = get_csf_fs(f, alphas)
        conj_csf_fs = get_conj_csf_fs(f, betas)
        for csf_slice, f in zip(csf, csf_fs):
            b_matrix.append(f_interp(csf_slice, f, freq_csf))
        for csf_conj_slice, f in zip(csf_conj, conj_csf_fs):
            b_matrix.append(f_interp(csf_conj_slice, f, freq_conj_csf))
        return np.array(b_matrix).T

    def get_s_matrix(f, alphas, betas, scf, scf_conj, freq_scf, freq_conj_scf):
        """计算S矩阵"""
        m = len(alphas)
        n = len(betas)
        s_matrix_1 = []  # 左上右下序列
        s_matrix_2 = []  # 左下右上序列
        scf_fs = get_scf_fs(f, alphas, betas)
        conj_scf_fs = get_conj_scf_fs(f, alphas, betas)
        # 计算矩阵左上与右下部分
        for scf_slice, f in zip(scf, scf_fs):
            s_matrix_1.append(f_interp(scf_slice, f, freq_scf))
        for scf_conj_slice, f in zip(scf_conj, conj_scf_fs):
            s_matrix_2.append(f_interp(scf_conj_slice, f, freq_conj_scf))
        # 重组矩阵
        s_mat_11 = np.array(s_matrix_1[: m * m])  # 左上
        s_mat_12 = np.array(s_matrix_1[m * m :])  # 右下
        assert len(s_mat_12) == n * n
        s_mat_21 = np.array(s_matrix_2[: m * n])  # 左下
        s_mat_22 = np.array(s_matrix_2[m * n :])  # 右上
        assert len(s_mat_22) == m * n
        s_mat_11 = s_mat_11.reshape((m, m))
        s_mat_12 = s_mat_12.reshape((n, n))
        s_mat_21 = s_mat_21.reshape((n, m))
        s_mat_22 = s_mat_22.reshape((m, n))
        s_upper = np.hstack((s_mat_11, s_mat_22))  # 上
        s_lower = np.hstack((s_mat_21, s_mat_12))  # 下
        s_matrix = np.vstack((s_upper, s_lower))
        return s_matrix

    # 频域响应矩阵 行-f 列 alpha/beta
    fresh_spectual_alphas = None
    fresh_spectual_betas = None
    m = len(alphas)
    n = len(betas)

    # print(get_scf_alphas(alphas, betas))
    # print(get_conj_scf_alphas(alphas, betas))
    # print(get_csf_alphas(alphas))
    # print(get_conj_csf_alphas(betas))
    # 先计算所有SCF/CSF矩阵并存储
    print("calculating_scf...")
    scf, freq_scf = scf_estimator(
        sig,
        get_scf_alphas(alphas, betas),
        report_progress=True,
        Nw=Nw,
    )
    print("calculating_conj_scf...")
    scf_conj, freq_conj_scf = scf_conj_estimator(
        sig,
        get_conj_scf_alphas(alphas, betas),
        report_progress=True,
        Nw=Nw,
    )
    print("calculating_csf...")
    csf, freq_csf = csf_estimator(
        desired,
        sig,
        get_csf_alphas(alphas),
        report_progress=True,
        Nw=Nw,
    )
    print("calculating_conj_csf...")
    csf_conj, freq_conj_csf = csf_conj_estimator(
        desired,
        sig,
        get_conj_csf_alphas(betas),
        report_progress=True,
        Nw=Nw,
    )
    # plt.imshow(np.abs(scf), aspect="auto", interpolation="none")
    # plt.colorbar()
    # plt.show()
    # plt.imshow(
    #     np.abs(scf_conj),
    #     aspect="auto",
    #     vmax=np.max(np.abs(scf_conj)) / 2,
    #     interpolation="none",
    # )
    # plt.colorbar()
    # plt.show()
    # plt.imshow(
    #     np.abs(csf), aspect="auto", vmax=np.max(np.abs(csf)) / 2, interpolation="none"
    # )
    # plt.colorbar()
    # plt.show()
    # plt.imshow(
    #     np.abs(csf_conj),
    #     aspect="auto",
    #     vmax=np.max(np.abs(csf_conj)) / 2,
    #     interpolation="none",
    # )
    # plt.colorbar()
    # plt.show()

    print("calculating matrixes...")
    assert len(freq_conj_csf) == len(freq_conj_scf)
    assert len(freq_csf) == len(freq_scf)
    fs = freq_scf[::decimation]
    cnt = 0
    cntmax = len(fs)
    for i, f in enumerate(fs):
        cnt += 1
        if cnt % 1000 == 0:
            print(f"{cnt}/{cntmax}")  # 打印进度
        b_matrix = get_b_matrix(
            f, alphas, betas, csf, csf_conj, freq_csf, freq_conj_csf
        )
        s_matrix = get_s_matrix(
            f, alphas, betas, scf, scf_conj, freq_scf, freq_conj_scf
        )
        h_matrix = np.linalg.inv(s_matrix) @ b_matrix
        h_list = h_matrix.T
        assert len(h_list) == m + n
        # 进行矩阵拼接
        if fresh_spectual_alphas is None:
            fresh_spectual_alphas = h_list[:m]
            assert fresh_spectual_betas is None
            fresh_spectual_betas = h_list[m:]
        else:
            fresh_spectual_alphas = np.vstack((fresh_spectual_alphas, h_list[:m]))
            fresh_spectual_betas = np.vstack((fresh_spectual_betas, h_list[m:]))
    fresh_spectual_alphas = fresh_spectual_alphas.T
    fresh_spectual_betas = fresh_spectual_betas.T
    # 计算实际抽头并取中间
    fresh_tempral_alphas = []
    fresh_tempral_betas = []
    for spectual in fresh_spectual_alphas:
        tempral = to_tempral(spectual)
        tempral = tempral[
            len(tempral) // 2 - cutoff // 2 : len(tempral) // 2 - cutoff // 2 + cutoff
        ]
        fresh_tempral_alphas.append(tempral)
    for spectual in fresh_spectual_betas:
        tempral = to_tempral(spectual)
        tempral = tempral[
            len(tempral) // 2 - cutoff // 2 : len(tempral) // 2 - cutoff // 2 + cutoff
        ]
        fresh_tempral_betas.append(tempral)
    return fresh_tempral_alphas, fresh_tempral_betas


def fresh_filter(sig, desired, alphas, betas, cutoff=129, Nw=4096, decimation=32):
    """
    进行维纳滤波
    """
    taps_alphas, taps_betas = fresh_filter_taps_design(
        sig, desired, alphas, betas, cutoff, Nw, decimation
    )
    for taps in taps_alphas:
        spec, _ = to_spectral(taps)
        plot_dB(spec)
    for taps in taps_alphas:
        spec, _ = to_spectral(taps)
        plot_dB(spec)
    plt.show()

    filtered = apply_fresh_filter(sig, alphas, betas, taps_alphas, taps_betas)
    return filtered


if __name__ == "__main__":  # 测试代码
    """ "注意信号长度必须要为2的次幂 否则会导致FFT效率低下 且长度不是偶数会导致conj_scf的freqs少一个的处理出问题"""
    SYMBOL_NUM = 32768  # 生成的所有信号中 取最短的
    decimation = 32 * 2
    cutoff = 256 + 1

    # sig = generate_signal_bpsk(8, SYMBOL_NUM, 0)
    # sig = freq_shift(sig, -0.01)
    # inf1 = generate_signal_bpsk(10, SYMBOL_NUM, 0)
    # inf1 = freq_shift(inf1, 0.13)
    sig, _ = generate_signal_4rrcfsk(sps=8, symbol_num=SYMBOL_NUM, power_dB=0)
    sig = freq_shift(sig, 0.02)
    inf1, _ = generate_signal_4rrcfsk(sps=10, symbol_num=SYMBOL_NUM, power_dB=0)
    inf1 = freq_shift(inf1, 0.02)
    num_sample = min(len(sig), len(inf1))
    noise = generate_signal_awgn(num_sample, -20)
    x = sig[:num_sample] + inf1[:num_sample] + noise
    sig = sig[:num_sample]

    alphas = [0, 1/8, 1/10]
    betas = [0.04]
    y = fresh_filter(x, sig, alphas, betas, decimation=decimation, cutoff=cutoff)
    y = y[(cutoff - 1) // 2 : -(cutoff - 1) // 2]
    nmse, _, _ = nmse_calculator(sig, x)
    print(nmse)
    nmse, scale, auto_scaled = nmse_calculator(sig, y, autoscale=True)
    print(nmse)
    print(scale)
    psd_plotter(
        [sig, inf1, x, auto_scaled], ["sig", "inf1", "x", "y"], (-40, 30)
    )
    auto_scaled = freq_shift(auto_scaled, 0.01)
    sig = freq_shift(sig, 0.01)
    plt.plot(np.imag(auto_scaled)[:5000])
    plt.plot(auto_scaled[:5000])
    plt.plot(sig[:5000])
    plt.plot(sig[:5000] - auto_scaled[:5000])
    plt.show()
