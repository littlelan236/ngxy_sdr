from scipy.signal import fftconvolve
import numpy as np

def apply_fft_filter(samples: np.ndarray, filter_coefficients: np.ndarray) -> np.ndarray:
    # Ensure inputs are 1D arrays
    samples = np.asarray(samples).flatten()
    filter_coefficients = np.asarray(filter_coefficients).flatten()

    # Perform FFT convolution using scipy's optimized function
    filtered = fftconvolve(samples, filter_coefficients, mode='same')

    return filtered