#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# Author: wangt
# GNU Radio version: 3.10.12.0

import math
import multiprocessing
import threading
import logging
import os
import re
import select
import signal
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
_removed_sys_path_entries: list[str] = []
for _sys_path_entry in list(sys.path):
    try:
        resolved_entry = Path(_sys_path_entry or os.curdir).resolve()
    except Exception:
        continue
    if resolved_entry == WORKSPACE_ROOT:
        sys.path.remove(_sys_path_entry)
        _removed_sys_path_entries.append(_sys_path_entry)

from gnuradio import analog
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio import iio
from gnuradio import zeromq

for _sys_path_entry in reversed(_removed_sys_path_entries):
    sys.path.insert(0, _sys_path_entry)

import grc_hard_decision_block as epy_block_0_0  # embedded python block
from ngxy_main.drivers.util import _log, _makesure_path_exist

class grc_main_block(gr.top_block):
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
                sps,
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
        self.sps = sps

        ##################################################
        # Blocks
        ##################################################

        self.zeromq_pub_sink_0_0 = zeromq.pub_sink(gr.sizeof_char, 1, zmq_addr, 100, False, (-1), '', True, True)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32(pluto_addr if pluto_addr else iio.get_pluto_uri(), [True, True], int(num_samps))
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
            sps,
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
          sps,
    ):
        try:
            self.tb = grc_main_block(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre, filename, num_samps, sps)
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


def _region_games_process_worker(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre, sps, filename, num_samps, stop_event):
    worker_top = top(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre, filename, num_samps, sps)
    if not hasattr(worker_top, "tb"):
        return

    stderr_patterns = (
        re.compile(r"READ LINE: -5"),
        re.compile(r"READ INTEGER: -5"),
        re.compile(r"Unable to refill buffer"),
        re.compile(r"Input/output error \(5\)"),
        re.compile(r"error initializing gnuradio flowgraph"),
        re.compile(r"error starting gnuradio flowgraph"),
    )

    def _stderr_watchdog() -> None:
        try:
            read_fd, write_fd = os.pipe()
            saved_stderr_fd = os.dup(2)
            try:
                os.dup2(write_fd, 2)
            finally:
                os.close(write_fd)
        except Exception as e:
            _log(logging.WARNING, f"[GnuradioClass] failed to install stderr watchdog: {e}")
            return

        try:
            with os.fdopen(read_fd, "rb", closefd=True) as pipe_reader:
                while not stop_event.is_set():
                    ready, _, _ = select.select([pipe_reader], [], [], 0.2)
                    if not ready:
                        continue
                    chunk = pipe_reader.readline()
                    if not chunk:
                        break
                    try:
                        os.write(saved_stderr_fd, chunk)
                    except Exception:
                        pass
                    line = chunk.decode(errors="ignore")
                    if any(pattern.search(line) for pattern in stderr_patterns):
                        _log(logging.ERROR, f"[GnuradioClass] stderr watchdog detected fatal GNU Radio error: {line.strip()}")
                        stop_event.set()
                        try:
                            worker_top.stop()
                        except Exception as e:
                            _log(logging.ERROR, f"[GnuradioClass] error stopping gnuradio flowgraph after stderr failure: {e}")
                        break
        finally:
            try:
                os.dup2(saved_stderr_fd, 2)
            except Exception:
                pass
            try:
                os.close(saved_stderr_fd)
            except Exception:
                pass

    def _stop_when_requested():
        worker_top.tb.flowgraph_started.wait()
        stop_event.wait()
        try:
            worker_top.stop()
        except Exception as e:
            _log(logging.ERROR, f"[GnuradioClass] error stopping gnuradio flowgraph: {e}")

    stop_thread = threading.Thread(target=_stop_when_requested, daemon=True)
    stderr_thread = threading.Thread(target=_stderr_watchdog, daemon=True)
    stop_thread.start()
    stderr_thread.start()
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
          sps,
    ):
        self.zmq_send_addr = zmq_send_addr
        self.pluto_addr = pluto_addr
        self.fc = fc
        self.bandwidth = bandwidth
        self.taps_lpf = taps_lpf
        self.taps_pre = taps_pre
        self.filename = filename
        self.num_samps = num_samps
        self.sps = sps
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
            args=(self.zmq_send_addr, self.pluto_addr, self.fc, self.bandwidth, self.taps_lpf, self.taps_pre, self.sps, self.filename, self.num_samps, self._stop_event),
        )
        self.thread = self.process
        self.process.start()

    def stop(self, timeout=2.0, force_kill=True):
        process = self.process
        stop_event = self._stop_event

        if stop_event is not None:
            stop_event.set()

        if process is not None:
            process.join(timeout=timeout)
            if process.is_alive() and force_kill:
                try:
                    process.terminate()
                    process.join(timeout=timeout)
                except Exception as e:
                    _log(logging.ERROR, f"[GnuradioClass] error terminating gnuradio process: {e}")

        self.process = None
        self.thread = None
        self._stop_event = None
        self.top = None
    
    def is_alive(self):
        return self.process is not None and self.process.is_alive()

if __name__ == '__main__':
    from ngxy_main.defs.def_signal import *
    from ngxy_main.defs.def_taps import *
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