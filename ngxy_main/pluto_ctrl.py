import os
import sys
import ctypes
import numpy as np
import adi

if sys.platform == "linux":
	# Ensure the system librtlsdr links against system libusb, not /opt/MVS.
	for lib_path in (
		"/lib/x86_64-linux-gnu/libusb-1.0.so.0",
		"/lib/x86_64-linux-gnu/librtlsdr.so.2",
	):
		try:
			ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
		except OSError:
			pass

from rtlsdr import RtlSdr

class pluto_ctrl_rx:
	def __init__(self, ip_addr='ip:192.168.2.4', sample_rate=1e6, center_freq=433e6,
				 num_samps=32767, rx_hardwaregain_chan0=70.0, agc_mode='slow_attack'):
		"""agc_mode: 'manual' or 'fast_attack' or 'slow_attack'"""
		self.sample_rate = int(sample_rate)
		self.center_freq = int(center_freq)
		self.num_samps = int(num_samps)

		self.sdr = adi.Pluto(ip_addr)
		self.sdr.gain_control_mode_chan0 = agc_mode
		if agc_mode == 'manual':
			self.sdr.rx_hardwaregain_chan0 = rx_hardwaregain_chan0
		self.sdr.rx_lo = self.center_freq
		self.sdr.sample_rate = self.sample_rate
		self.sdr.rx_rf_bandwidth = self.sample_rate
		self.sdr.rx_buffer_size = self.num_samps

	def rx(self):
		ret = self.sdr.rx()
		return ret

	def close(self) -> None:
		try:
			if self.sdr is not None:
				self.sdr.rx_destroy_buffer()
		except Exception:
			pass
		try:
			if self.sdr is not None:
				self.sdr = None
		except Exception:
			pass


class pluto_ctrl_tx:
	def __init__(self, ip_addr='ip:192.168.2.4', sample_rate=1e6, center_freq=433e6,
			   tx_hardwaregain_chan0=-50, tx_cyclic_buffer=True):
		self.sample_rate = int(sample_rate)
		self.center_freq = int(center_freq)

		self.sdr = adi.Pluto(ip_addr)
		self.sdr.sample_rate = self.sample_rate
		self.sdr.tx_rf_bandwidth = self.sample_rate
		self.sdr.tx_lo = self.center_freq
		self.sdr.tx_hardwaregain_chan0 = tx_hardwaregain_chan0
		self.sdr.tx_cyclic_buffer = tx_cyclic_buffer

	def tx(self, samples):
		self.sdr.tx(samples)

	def close(self) -> None:
		try:
			if self.sdr is not None:
				self.sdr.tx_destroy_buffer()
		except Exception:
			pass
		try:
			if self.sdr is not None:
				self.sdr = None
		except Exception:
			pass


class rtl_sdr_ctrl:
	def __init__(self, sample_rate=1e6, center_freq=433.2e6, num_samps=32767, rx_gain='auto'):
		self.sample_rate = int(sample_rate)
		self.center_freq = int(center_freq)
		self.num_samps = int(num_samps)
		self.rx_gain = rx_gain
		self._async_chunk = min(max(4096, self.num_samps), 16384)

		self.sdr = RtlSdr()
		self.sdr.sample_rate = self.sample_rate # Hz
		self.sdr.center_freq = self.center_freq   # Hz
		self.sdr.freq_correction = 60  # PPM
		self.sdr.gain = self.rx_gain
		try:
			self.sdr.reset_buffer()
		except Exception:
			pass

	def close(self) -> None:
		try:
			if self.sdr is not None:
				self.sdr.cancel_read_async()
		except Exception:
			pass
		try:
			if self.sdr is not None:
				self.sdr.close()
		except Exception:
			pass
		self.sdr = None

	def _read_async_samples(self) -> np.ndarray:
		collected_chunks: list[np.ndarray] = []
		collected_samples = 0

		def _on_samples(samples, _context) -> None:
			nonlocal collected_samples
			chunk = np.array(samples, copy=True)
			collected_chunks.append(chunk)
			collected_samples += chunk.size
			if collected_samples >= self.num_samps:
				try:
					self.sdr.cancel_read_async()
				except Exception:
					pass

		self.sdr.read_samples_async(_on_samples, num_samples=self._async_chunk)
		if not collected_chunks:
			return np.array([], dtype=np.complex128)

		samples = np.concatenate(collected_chunks)
		if samples.size > self.num_samps:
			samples = samples[:self.num_samps]
		return samples

	def rx(self):
		try:
			return self._read_async_samples()
		except Exception as exc:
			# Preserve a narrow fallback path if async read is unavailable or fails.
			try:
				self.sdr.close()
			except Exception:
				pass
			self.sdr = RtlSdr()
			self.sdr.sample_rate = self.sample_rate # Hz
			self.sdr.center_freq = self.center_freq   # Hz
			self.sdr.freq_correction = 60  # PPM
			self.sdr.gain = self.rx_gain
			try:
				self.sdr.reset_buffer()
			except Exception:
				pass
			return self.sdr.read_samples(min(self.num_samps, 4096))


if __name__ == '__main__':
	# rx_ctrl = pluto_ctrl_rx(ip_addr="ip:192.168.2.4")
	# samples = rx_ctrl.rx()
	# print(samples[0:10])
	import time

	rx_ctrl = rtl_sdr_ctrl()
	while True:
		samples = rx_ctrl.rx()
		print(samples[0:10])
		time.sleep(0.1)