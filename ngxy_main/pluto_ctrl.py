import numpy as np
import adi

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
		return self.sdr.rx()


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


if __name__ == '__main__':
	rx_ctrl = pluto_ctrl_rx()
	samples = rx_ctrl.rx()
	print(samples[0:10])