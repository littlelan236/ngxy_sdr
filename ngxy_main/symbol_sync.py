from dataclasses import dataclass
from typing import Iterable

import numpy as np


def _sign_bpsk(value: complex | float) -> float:
    """Return the BPSK decision for a scalar sample."""

    return 1.0 if float(np.real(value)) >= 0.0 else -1.0


def _as_1d_array(samples: Iterable[complex | float] | np.ndarray) -> np.ndarray:
    """Normalize input to a one-dimensional NumPy array."""

    array = np.asarray(samples)
    if array.ndim == 0:
        return array.reshape(1)
    if array.ndim != 1:
        return array.reshape(-1)
    return array


@dataclass
class MMSymbolSyncConfig:
    """Configuration for the M&M timing loop."""

    omega: float = 4.0
    mu: float = 0.5
    gain_mu: float = 0.175
    gain_omega: float | None = None
    omega_relative_limit: float = 0.05


class MMSymbolSynchronizer:
    """Decision-directed Mueller and Muller symbol synchronizer for BPSK."""

    _BUFFER_HISTORY = 2

    def __init__(self, config: MMSymbolSyncConfig | None = None):
        self.config = config or MMSymbolSyncConfig()
        if self.config.gain_omega is None:
            self.config.gain_omega = (self.config.gain_mu ** 2) / 4.0

        self.omega_nominal = float(self.config.omega)
        self.omega_min = self.omega_nominal * (1.0 - abs(self.config.omega_relative_limit))
        self.omega_max = self.omega_nominal * (1.0 + abs(self.config.omega_relative_limit))
        self.reset()

    def reset(self) -> None:
        """Reset the internal loop state."""

        self.omega = float(self.config.omega)
        self.mu = float(self.config.mu)
        if self.mu <= 1.0:
            self.mu *= self.omega
        self._buffer = np.array([], dtype=np.complex128)
        self._last_symbol = None
        self._last_decision = None

    @staticmethod
    def _interpolate(samples: np.ndarray, position: float) -> complex | float | None:
        """Linearly interpolate a sample at a fractional position."""

        if position < 0.0:
            return None
        left = int(np.floor(position))
        right = left + 1
        if right >= len(samples):
            return None
        frac = position - left
        return samples[left] * (1.0 - frac) + samples[right] * frac

    def _update_omega_limits(self) -> None:
        self.omega = min(max(self.omega, self.omega_min), self.omega_max)

    def _trim_consumed_buffer(self) -> None:
        """Drop samples that are no longer needed for interpolation."""

        if self._buffer.size <= self._BUFFER_HISTORY:
            return

        consumed = int(self.mu) - self._BUFFER_HISTORY
        if consumed <= 0:
            return

        if consumed >= self._buffer.size:
            consumed = self._buffer.size - self._BUFFER_HISTORY
        if consumed > 0:
            self._buffer = self._buffer[consumed:]
            self.mu -= consumed

    def process(self, samples: Iterable[complex | float] | np.ndarray) -> np.ndarray:
        """Process a chunk of matched-filter samples and return synchronized symbols.

        The input can be real or complex. For BPSK, the timing detector makes
        decisions on the real part of the interpolated samples.
        """

        new_samples = _as_1d_array(samples)
        if new_samples.size == 0:
            return np.array([], dtype=self._buffer.dtype if self._buffer.size else np.complex128)

        if self._buffer.size == 0:
            self._buffer = new_samples.astype(np.complex128 if np.iscomplexobj(new_samples) else np.float64, copy=False)
        else:
            if np.iscomplexobj(self._buffer) or np.iscomplexobj(new_samples):
                self._buffer = self._buffer.astype(np.complex128, copy=False)
                new_samples = new_samples.astype(np.complex128, copy=False)
            else:
                self._buffer = self._buffer.astype(np.float64, copy=False)
                new_samples = new_samples.astype(np.float64, copy=False)
            self._buffer = np.concatenate([self._buffer, new_samples])

        outputs: list[complex | float] = []

        while True:
            current = self._interpolate(self._buffer, self.mu)
            if current is None:
                break

            decision = _sign_bpsk(current)
            outputs.append(current)

            if self._last_symbol is not None and self._last_decision is not None:
                error = self._last_decision * float(np.real(current)) - decision * float(np.real(self._last_symbol))
                self.omega += self.config.gain_omega * error
                self._update_omega_limits()
                self.mu += self.omega + self.config.gain_mu * error
            else:
                self.mu += self.omega

            self._last_symbol = current
            self._last_decision = decision

            self._trim_consumed_buffer()

        self._trim_consumed_buffer()

        if not outputs:
            return np.array([], dtype=self._buffer.dtype if self._buffer.size else np.complex128)
        return np.asarray(outputs, dtype=self._buffer.dtype)

    def synchronize(
        self,
        samples: Iterable[complex | float] | np.ndarray,
        *,
        reset: bool = False,
    ) -> np.ndarray:
        """Process a buffer and keep loop state by default.

        Use ``reset=True`` when starting a new, unrelated signal. The default
        behavior is streaming-friendly so consecutive calls can cover different
        parts of the same long signal.
        """

        if reset:
            self.reset()
        return self.process(samples)

    def decisions(self, samples: Iterable[complex | float] | np.ndarray) -> np.ndarray:
        """Return hard BPSK decisions for synchronized samples."""

        synced = self.synchronize(samples)
        if synced.size == 0:
            return np.array([], dtype=np.int8)
        return np.where(np.real(synced) >= 0.0, 1, -1).astype(np.int8)


def bpsk_bits_from_symbols(symbols: Iterable[complex | float] | np.ndarray) -> np.ndarray:
    """Convert BPSK symbols to bit values 0/1."""

    array = _as_1d_array(symbols)
    if array.size == 0:
        return np.array([], dtype=np.uint8)
    return np.where(np.real(array) >= 0.0, 1, 0).astype(int)


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(7)
    bits = rng.integers(0, 2, size=200)
    symbols = 1.0 - 2.0 * bits

    sps = 4
    tx = np.repeat(symbols, sps).astype(np.float64)
    fractional_delay = 2.35
    delayed = np.interp(
        np.arange(len(tx)) + fractional_delay,
        np.arange(len(tx)),
        tx,
        left=tx[0],
        right=tx[-1],
    )
    noisy = delayed + rng.normal(0.0, 0.15, size=delayed.size)

    sync = MMSymbolSynchronizer(MMSymbolSyncConfig(omega=float(sps)))
    first_half = sync.synchronize(noisy[: len(noisy) // 2], reset=True)
    second_half = sync.synchronize(noisy[len(noisy) // 2 :])
    synced = np.concatenate([first_half, second_half])
    recovered_bits = bpsk_bits_from_symbols(synced)
    
    plt.plot(tx)
    plt.plot(noisy, alpha=0.5)
    recovered_bits = np.repeat(recovered_bits, sps)
    synced = np.repeat(synced, sps)
    # plt.plot(synced)
    plt.plot(recovered_bits.astype(float) * 2.0 - 1.0, alpha=0.7)
    plt.show()

    print(f"input samples: {len(noisy)}")
    print(f"synced symbols: {len(synced)}")
    print(f"recovered bits preview: {recovered_bits[:32].tolist()}")
