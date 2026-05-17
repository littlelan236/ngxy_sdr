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
from pathlib import Path
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
from gnuradio import zeromq
import region_games_epy_block_0_0 as epy_block_0_0  # embedded python block
import multiprocessing
import threading
import logging
from util import _log, _makesure_path_exist

class region_games(gr.top_block):
    """内置gnuradio控制线程 将比特流zmq发送至端口
    filename=None则关闭录制"""

    def __init__(self,
                zmq_addr,
                pluto_addr,
                fc,
                bandwidth,
                taps_lpf,
                taps_pre,
                filename,
                num_samps,
                ):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=False)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 1000000
        self.taps_lpf_pre = taps_lpf_pre = taps_pre
        self.taps_lpf = taps_lpf
        self.signal_bandwidth = signal_bandwidth = bandwidth
        self.fc = fc
        self.zmq_addr = zmq_addr
        self.pluto_addr = pluto_addr

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_pub_sink_0_0 = zeromq.pub_sink(gr.sizeof_char, 1, zmq_addr, 100, False, (-1), '', True, True)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32(pluto_addr if pluto_addr else iio.get_pluto_uri(), [True, True], num_samps)
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency(fc)
        self.iio_pluto_source_0.set_samplerate(samp_rate)
        self.iio_pluto_source_0.set_gain_mode(0, 'slow_attack')
        self.iio_pluto_source_0.set_gain(0, 64)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(True)
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
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf((1 / 1.5))
        if filename is not None:
            filepath = _makesure_path_exist(filename)
            self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_gr_complex*1, str(filepath), False)
            self.blocks_file_sink_0.set_unbuffered(False)


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
        self.connect((self.iio_pluto_source_0, 0), (self.fft_filter_xxx_1_0_0, 0))

        if filename is not None:
            self.connect((self.iio_pluto_source_0, 0), (self.blocks_file_sink_0, 0))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        # self.set_taps_lpf(firdes.low_pass(1.0, self.samp_rate, 19230, 2000))
        # self.set_taps_lpf_pre(firdes.low_pass(1.0, self.samp_rate, 270000, 10000))
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

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.iio_pluto_source_0.set_frequency(self.fc)


class top():
    def __init__(
          self,
          zmq_send_addr,
          pluto_addr,
          fc,
          bandwidth,
          taps_lpf,
          taps_pre,
          filename,
          num_samps,
    ):
        try:
            self.tb = region_games(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre, filename, num_samps)
            def sig_handler(sig=None, frame=None):
                self.tb.stop()
                self.tb.wait()
                sys.exit(0)
            signal.signal(signal.SIGINT, sig_handler)
            signal.signal(signal.SIGTERM, sig_handler)
        except Exception as e:
            _log(logging.ERROR, f"[GnuradioClass] error initializing gnuradio flowgraph: {e}")

    def start(self):
        try:
            self.tb.flowgraph_started.set()
            self.tb.run()
        except Exception as e:
            _log(logging.ERROR, f"[GnuradioClass] error starting gnuradio flowgraph: {e}")

    def stop(self):
        try:
            self.tb.stop()
            self.tb.wait()
        except Exception as e:
            _log(logging.ERROR, f"[GnuradioClass] error stopping gnuradio flowgraph: {e}")


def _region_games_process_worker(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre, filename, num_samps, stop_event):
    worker_top = top(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre, filename, num_samps)
    if not hasattr(worker_top, "tb"):
        return

    def _stop_when_requested():
        worker_top.tb.flowgraph_started.wait()
        stop_event.wait()
        try:
            worker_top.stop()
        except Exception as e:
            _log(logging.ERROR, f"[GnuradioClass] error stopping gnuradio flowgraph: {e}")

    stop_thread = threading.Thread(target=_stop_when_requested, daemon=True)
    stop_thread.start()
    try:
        worker_top.start()
    finally:
        stop_event.set()

class top_thread_wrapper():
    def __init__(
          self,
          zmq_send_addr,
          pluto_addr,
          fc,
          bandwidth,
          taps_lpf,
          taps_pre,
          filename,
          num_samps,
    ):
        self.zmq_send_addr = zmq_send_addr
        self.pluto_addr = pluto_addr
        self.fc = fc
        self.bandwidth = bandwidth
        self.taps_lpf = taps_lpf
        self.taps_pre = taps_pre
        self.filename = filename
        self.num_samps = num_samps
        self.thread = None
        self.process = None
        self.top = None
        self._stop_event = None

    def start(self):
        if self.process is not None and self.process.is_alive():
            raise RuntimeError("process already started")

        self._stop_event = multiprocessing.Event()
        self.process = multiprocessing.Process(
            target=_region_games_process_worker,
            args=(self.zmq_send_addr, self.pluto_addr, self.fc, self.bandwidth, self.taps_lpf, self.taps_pre, self.filename, self.num_samps, self._stop_event),
        )
        self.thread = self.process
        self.process.start()

    def stop(self):
        if self._stop_event is not None:
            self._stop_event.set()
        if self.process is not None:
            self.process.join()
        self.process = None
        self.thread = None
        self._stop_event = None
        self.top = None
    
    def is_alive(self):
        return self.process is not None and self.process.is_alive()

if __name__ == '__main__':
    from def_signal import *
    from def_taps import *
    from time import sleep, time

    filename = f"rec/{time()}test_rec"

    t = top_thread_wrapper(
        "tcp://127.0.0.1:2236",
        "192.168.2.3",
        FC_RED,
        BW_SIG,
        TAPS_LPF,
        TAPS_LPF_PRE,
        filename,
        32767,
    )
    t.start()
    cnt = 0 
    while(1):
        cnt += 1
        sleep(1)
        print(f"running... {cnt}s")
        print(f"process alive: {t.is_alive()}")
        if cnt == 10:
            t.stop()
            break
    t.start()
    while(1):
        cnt += 1
        sleep(1)
        print(f"running... {cnt}s")
        print(f"process alive: {t.is_alive()}")
        if cnt == 10:
            t.stop()
            break