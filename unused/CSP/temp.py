from plotter import nmse_calculator, psd_plotter, plot_dB
# from FRESH import fresh_filter_taps_design
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
import numpy as np
from signal_generator import generate_signal_4rrcfsk, generate_signal_bpsk
if __name__ == "__main__":
    N = 10000 # number of samples to simulate
    f_offset = 0.2 # Hz normalized
    sps = 20 # cyclic freq (alpha) will be 1/sps or 0.05 Hz normalized

    symbols = np.random.randint(0, 2, int(np.ceil(N/sps))) * 2 - 1 # random 1's and -1's
    bpsk = np.repeat(symbols, sps)  # repeat each symbol sps times to make rectangular BPSK
    bpsk = bpsk[:N]  # clip off the extra samples
    bpsk = bpsk * np.exp(2j * np.pi * f_offset * np.arange(N)) # Freq shift up the BPSK, this is also what makes it complex
    noise = np.random.randn(N) + 1j*np.random.randn(N) # complex white Gaussian noise
    samples = bpsk + 0.1*noise  # add noise to the signal
    signal = samples
    alphas = np.arange(0, 0.3, 1/1000)
    scf = scf_estimator(signal, alphas, do_plot=True)