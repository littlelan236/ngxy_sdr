from dataclasses import dataclass
from typing import Iterable

import numpy as np


def _as_1d_array(samples: Iterable[complex | float] | np.ndarray) -> np.ndarray:
	"""Normalize input to a one-dimensional NumPy array."""

	array = np.asarray(samples)
	if array.ndim == 0:
		return array.reshape(1)
	if array.ndim != 1:
		return array.reshape(-1)
	return array


@dataclass
class QuadratureDiscriminatorConfig:
	"""Configuration for the quadrature discriminator."""

	gain: float = 1.0
	clip_output: bool = False
	output_limit: float | None = None


class QuadratureDiscriminator:
	"""Stateful quadrature discriminator for streaming complex baseband input."""

	def __init__(self, config: QuadratureDiscriminatorConfig | None = None):
		self.config = config or QuadratureDiscriminatorConfig()
		self.reset()

	def reset(self) -> None:
		"""Reset the internal history sample."""

		self._prev_sample: complex | None = None

	def _discriminate_pair(self, current: complex) -> float:
		"""Convert two adjacent complex samples into an instantaneous phase delta."""

		if self._prev_sample is None:
			self._prev_sample = current
			return 0.0

		value = np.angle(current * np.conjugate(self._prev_sample)) * self.config.gain
		self._prev_sample = current

		if self.config.clip_output and self.config.output_limit is not None:
			value = float(np.clip(value, -abs(self.config.output_limit), abs(self.config.output_limit)))
		return float(value)

	def process(self, samples: Iterable[complex | float] | np.ndarray) -> np.ndarray:
		"""Process a chunk of samples and return the discriminator output.

		The first sample of the very first chunk has no previous reference, so it
		yields no output. After that, each new input sample produces one output
		value, and the last sample is preserved for the next call.
		"""

		array = _as_1d_array(samples)
		if array.size == 0:
			return np.array([], dtype=np.float32)

		if not np.iscomplexobj(array):
			array = array.astype(np.complex128, copy=False)
		elif array.dtype != np.complex128:
			array = array.astype(np.complex128, copy=False)

		outputs: list[float] = []
		for sample in array:
			outputs.append(self._discriminate_pair(complex(sample)))

		if self._prev_sample is None:
			return np.array([], dtype=np.float32)
		return np.asarray(outputs, dtype=np.float32)

	def demodulate(self, samples: Iterable[complex | float] | np.ndarray, *, reset: bool = False) -> np.ndarray:
		"""Convenience wrapper for processing a chunk.

		Use ``reset=True`` when starting a new, unrelated signal. The default
		behavior keeps the previous sample so multiple calls can process different
		parts of the same long stream.
		"""

		if reset:
			self.reset()
		return self.process(samples)


def quadrature_discriminator(
	samples: Iterable[complex | float] | np.ndarray,
	gain: float = 1.0,
	*,
	reset: bool = True,
) -> np.ndarray:
	"""Stateless helper for one-shot use.

	This helper creates a temporary discriminator instance, which is convenient
	for offline processing of a single buffer.
	"""

	discriminator = QuadratureDiscriminator(QuadratureDiscriminatorConfig(gain=gain))
	return discriminator.demodulate(samples, reset=reset)


if __name__ == "__main__":
	rng = np.random.default_rng(7)
	fs = 1_000_000
	freq_dev = 50_000
	samples = 2000
	phase = 2.0 * np.pi * freq_dev / fs * np.arange(samples)
	carrier = np.exp(1j * phase)
	noise = 0.05 * (rng.normal(size=samples) + 1j * rng.normal(size=samples))
	stream = carrier + noise

	qd = QuadratureDiscriminator(QuadratureDiscriminatorConfig(gain=fs / (2.0 * np.pi * freq_dev)))
	first = qd.demodulate(stream[:1000], reset=True)
	second = qd.demodulate(stream[1000:])
	out = np.concatenate([first, second])

	print(f"input samples: {len(stream)}")
	print(f"output samples: {len(out)}")
	print(f"preview: {out[:10].tolist()}")
