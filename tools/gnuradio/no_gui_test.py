#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# Author: wangt
# GNU Radio version: 3.10.12.0

from gnuradio import analog
import math
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
from gnuradio import zeromq
import no_gui_test_epy_block_0_0 as epy_block_0_0  # embedded python block
import threading




class no_gui_test(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 1000000
        self.taps_lpf_pre = taps_lpf_pre = firdes.low_pass(1.0, samp_rate, 270000, 10000)
        self.taps_lpf = taps_lpf = firdes.low_pass(1.0, samp_rate, 19230, 2000)
        self.signal_bandwidth = signal_bandwidth = 240600
        self.sensitivity_signal = sensitivity_signal = 1.5756
        self.sensitivity_inf_3 = sensitivity_inf_3 = 0.6466
        self.sensitivity_inf_2 = sensitivity_inf_2 = 2.5809
        self.sensitivity_inf_1 = sensitivity_inf_1 = 2.8323
        self.fc_blue_3 = fc_blue_3 = 434320000
        self.fc_blue_2 = fc_blue_2 = 434620000
        self.fc_blue_1 = fc_blue_1 = 434920000
        self.fc_blue = fc_blue = 433920000
        self.fc_3 = fc_3 = 432800000
        self.fc_2 = fc_2 = 432500000
        self.fc_1 = fc_1 = 432200000
        self.fc = fc = 433200000

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_sub_source_0 = zeromq.sub_source(gr.sizeof_char, 1, 'tcp://127.0.0.1:2235', 100, False, (-1), '', False)
        self.zeromq_pub_sink_0_0 = zeromq.pub_sink(gr.sizeof_char, 1, 'tcp://127.0.0.1:2236', 100, False, (-1), '', True, True)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32('192.168.3.2' if '192.168.3.2' else iio.get_pluto_uri(), [True, True], (32768 * 16))
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency(fc_blue)
        self.iio_pluto_source_0.set_samplerate(samp_rate)
        self.iio_pluto_source_0.set_gain_mode(0, 'slow_attack')
        self.iio_pluto_source_0.set_gain(0, 64)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(True)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
        self.iio_pluto_sink_0 = iio.fmcomms2_sink_fc32('192.168.3.2' if '192.168.3.2' else iio.get_pluto_uri(), [True, True], 32768, True)
        self.iio_pluto_sink_0.set_len_tag_key('')
        self.iio_pluto_sink_0.set_bandwidth(signal_bandwidth)
        self.iio_pluto_sink_0.set_frequency(fc_blue)
        self.iio_pluto_sink_0.set_samplerate(samp_rate)
        self.iio_pluto_sink_0.set_attenuation(0, 0)
        self.iio_pluto_sink_0.set_filter_params('Auto', '', 0, 0)
        self.fft_filter_xxx_1_0_0 = filter.fft_filter_ccc(1, taps_lpf_pre, 1)
        self.fft_filter_xxx_1_0_0.declare_sample_delay(0)
        self.fft_filter_xxx_1_0 = filter.fft_filter_fff(1, taps_lpf, 1)
        self.fft_filter_xxx_1_0.declare_sample_delay(0)
        self.epy_block_0_0 = epy_block_0_0.blk()
        self.digital_symbol_sync_xx_0 = digital.symbol_sync_ff(
            digital.TED_MUELLER_AND_MULLER,
            52,
            0.045,
            1.0,
            1.0,
            1.5,
            1,
            digital.constellation_bpsk().base(),
            digital.IR_MMSE_8TAP,
            128,
            [])
        self.digital_gfsk_mod_0 = digital.gfsk_mod(
            samples_per_symbol=52,
            sensitivity=sensitivity_signal,
            bt=0.35,
            verbose=False,
            log=False,
            do_unpack=True)
        self.blocks_pack_k_bits_bb_0_0_1 = blocks.pack_k_bits_bb(8)
        self.blocks_pack_k_bits_bb_0_0 = blocks.pack_k_bits_bb(8)
        self.blocks_float_to_char_0 = blocks.float_to_char(1, 1)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf((1 / 1.5))


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.fft_filter_xxx_1_0, 0))
        self.connect((self.blocks_float_to_char_0, 0), (self.blocks_pack_k_bits_bb_0_0_1, 0))
        self.connect((self.blocks_pack_k_bits_bb_0_0, 0), (self.digital_gfsk_mod_0, 0))
        self.connect((self.blocks_pack_k_bits_bb_0_0_1, 0), (self.zeromq_pub_sink_0_0, 0))
        self.connect((self.digital_gfsk_mod_0, 0), (self.iio_pluto_sink_0, 0))
        self.connect((self.digital_symbol_sync_xx_0, 0), (self.epy_block_0_0, 0))
        self.connect((self.epy_block_0_0, 0), (self.blocks_float_to_char_0, 0))
        self.connect((self.fft_filter_xxx_1_0, 0), (self.digital_symbol_sync_xx_0, 0))
        self.connect((self.fft_filter_xxx_1_0_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.fft_filter_xxx_1_0_0, 0))
        self.connect((self.zeromq_sub_source_0, 0), (self.blocks_pack_k_bits_bb_0_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_taps_lpf(firdes.low_pass(1.0, self.samp_rate, 19230, 2000))
        self.set_taps_lpf_pre(firdes.low_pass(1.0, self.samp_rate, 270000, 10000))
        self.iio_pluto_sink_0.set_samplerate(self.samp_rate)
        self.iio_pluto_source_0.set_samplerate(self.samp_rate)

    def get_taps_lpf_pre(self):
        return self.taps_lpf_pre

    def set_taps_lpf_pre(self, taps_lpf_pre):
        self.taps_lpf_pre = taps_lpf_pre
        self.fft_filter_xxx_1_0_0.set_taps(self.taps_lpf_pre)

    def get_taps_lpf(self):
        return self.taps_lpf

    def set_taps_lpf(self, taps_lpf):
        self.taps_lpf = taps_lpf
        self.fft_filter_xxx_1_0.set_taps(self.taps_lpf)

    def get_signal_bandwidth(self):
        return self.signal_bandwidth

    def set_signal_bandwidth(self, signal_bandwidth):
        self.signal_bandwidth = signal_bandwidth
        self.iio_pluto_sink_0.set_bandwidth(self.signal_bandwidth)

    def get_sensitivity_signal(self):
        return self.sensitivity_signal

    def set_sensitivity_signal(self, sensitivity_signal):
        self.sensitivity_signal = sensitivity_signal

    def get_sensitivity_inf_3(self):
        return self.sensitivity_inf_3

    def set_sensitivity_inf_3(self, sensitivity_inf_3):
        self.sensitivity_inf_3 = sensitivity_inf_3

    def get_sensitivity_inf_2(self):
        return self.sensitivity_inf_2

    def set_sensitivity_inf_2(self, sensitivity_inf_2):
        self.sensitivity_inf_2 = sensitivity_inf_2

    def get_sensitivity_inf_1(self):
        return self.sensitivity_inf_1

    def set_sensitivity_inf_1(self, sensitivity_inf_1):
        self.sensitivity_inf_1 = sensitivity_inf_1

    def get_fc_blue_3(self):
        return self.fc_blue_3

    def set_fc_blue_3(self, fc_blue_3):
        self.fc_blue_3 = fc_blue_3

    def get_fc_blue_2(self):
        return self.fc_blue_2

    def set_fc_blue_2(self, fc_blue_2):
        self.fc_blue_2 = fc_blue_2

    def get_fc_blue_1(self):
        return self.fc_blue_1

    def set_fc_blue_1(self, fc_blue_1):
        self.fc_blue_1 = fc_blue_1

    def get_fc_blue(self):
        return self.fc_blue

    def set_fc_blue(self, fc_blue):
        self.fc_blue = fc_blue
        self.iio_pluto_sink_0.set_frequency(self.fc_blue)
        self.iio_pluto_source_0.set_frequency(self.fc_blue)

    def get_fc_3(self):
        return self.fc_3

    def set_fc_3(self, fc_3):
        self.fc_3 = fc_3

    def get_fc_2(self):
        return self.fc_2

    def set_fc_2(self, fc_2):
        self.fc_2 = fc_2

    def get_fc_1(self):
        return self.fc_1

    def set_fc_1(self, fc_1):
        self.fc_1 = fc_1

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc



class Gnuradio_main():
    def __init__(self):
        pass

    def main(self, top_block_cls=no_gui_test, options=None):
        self.tb = no_gui_test()

        def sig_handler(sig=None, frame=None):
            self.tb.stop()
            self.tb.wait()

            sys.exit(0)

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        self.tb.start()
        self.tb.flowgraph_started.set()

        try:
            input('Press Enter to quit: ')
        except EOFError:
            pass
        self.tb.stop()
        self.tb.wait()


if __name__ == '__main__':
    gnuradio_main = Gnuradio_main()
    gnuradio_main.main()
