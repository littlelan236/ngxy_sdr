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
import final_no_gui_epy_block_0_0 as epy_block_0_0  # embedded python block
import threading

import logging
import util

class final_no_gui(gr.top_block):

    def __init__(self, fc, bw, gain, taps_lpf, taps_lpf_pre, addr='tcp://127.0.0.1:2234', filesink_path='./log/raw_samples.iq'):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = int(1e6)  # Default sample rate
        self.taps_lpf_pre = taps_lpf_pre
        self.taps_lpf = taps_lpf
        self.signal_bandwidth = bw
        self.gain = gain
        self.fc = fc

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_pub_sink_0_0 = zeromq.pub_sink(gr.sizeof_char, 1, addr, 100, False, (-1), '', True, True)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32('192.168.3.2' if '192.168.3.2' else iio.get_pluto_uri(), [True, True], 32768)
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency(fc)
        self.iio_pluto_source_0.set_samplerate(samp_rate)
        self.iio_pluto_source_0.set_gain_mode(0, 'slow_attack')
        self.iio_pluto_source_0.set_gain(0, 64)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(False)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
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
        self.blocks_pack_k_bits_bb_0_0_1 = blocks.pack_k_bits_bb(8)
        self.blocks_float_to_char_0 = blocks.float_to_char(1, 1)
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_gr_complex*1, filesink_path, True)
        self.blocks_file_sink_0.set_unbuffered(False)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(gain)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.fft_filter_xxx_1_0, 0))
        self.connect((self.blocks_float_to_char_0, 0), (self.blocks_pack_k_bits_bb_0_0_1, 0))
        self.connect((self.blocks_pack_k_bits_bb_0_0_1, 0), (self.zeromq_pub_sink_0_0, 0))
        self.connect((self.digital_symbol_sync_xx_0, 0), (self.epy_block_0_0, 0))
        self.connect((self.epy_block_0_0, 0), (self.blocks_float_to_char_0, 0))
        self.connect((self.fft_filter_xxx_1_0, 0), (self.digital_symbol_sync_xx_0, 0))
        self.connect((self.fft_filter_xxx_1_0_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.blocks_file_sink_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.fft_filter_xxx_1_0_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_taps_lpf(firdes.low_pass(1.0, self.samp_rate, 19230, 2000))
        self.set_taps_lpf_pre(firdes.low_pass(1.0, self.samp_rate, 270000, 10000))
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

    def get_gain(self):
        return self.gain

    def set_gain(self, gain):
        self.gain = gain
        self.analog_quadrature_demod_cf_0.set_gain(self.gain)

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.iio_pluto_source_0.set_frequency(self.fc)




def main(top_block_cls=final_no_gui, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


class GnuradioClass():
    def __init__(self, fc, bw, gain, taps_lpf, taps_lpf_pre, addr='tcp://127.0.0.1:2234', filesink_path='./log/raw_samples.iq'):
        try:
            self.tb = final_no_gui(fc, bw, gain, taps_lpf, taps_lpf_pre, addr, filesink_path)
        except Exception as e:
            logging.log(logging.ERROR, f"[GnuradioClass] error initializing gnuradio flowgraph: {e}")

    def start(self):
        try:
            self.tb.start()
            self.tb.flowgraph_started.set()
        except Exception as e:
            logging.log(logging.ERROR, f"[GnuradioClass] error starting gnuradio flowgraph: {e}")

    def stop(self):
        try:
            self.tb.stop()
            self.tb.wait()
        except Exception as e:
            logging.log(logging.ERROR, f"[GnuradioClass] error stopping gnuradio flowgraph: {e}")


if __name__ == '__main__':
    pass