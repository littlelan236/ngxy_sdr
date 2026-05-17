#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# Author: wangt
# GNU Radio version: 3.10.12.0

VISUALIZE_ON = True

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
import region_games_epy_block_0_0 as epy_block_0_0  # embedded python block
import threading
import logging
from PyQt5 import Qt
from gnuradio import qtgui
import sip

class region_games(gr.top_block, Qt.QWidget):

    def __init__(self,
                zmq_addr,
                pluto_addr,
                fc,
                bandwidth,
                taps_lpf,
                taps_pre,
                ):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        if VISUALIZE_ON:
            Qt.QWidget.__init__(self)
            self.setWindowTitle("Not titled yet")
            qtgui.util.check_set_qss()
            try:
                self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
            except BaseException as exc:
                print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
            self.top_scroll_layout = Qt.QVBoxLayout()
            self.setLayout(self.top_scroll_layout)
            self.top_scroll = Qt.QScrollArea()
            self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
            self.top_scroll_layout.addWidget(self.top_scroll)
            self.top_scroll.setWidgetResizable(True)
            self.top_widget = Qt.QWidget()
            self.top_scroll.setWidget(self.top_widget)
            self.top_layout = Qt.QVBoxLayout(self.top_widget)
            self.top_grid_layout = Qt.QGridLayout()
            self.top_layout.addLayout(self.top_grid_layout)

            self.settings = Qt.QSettings("gnuradio/flowgraphs", "region_games_with_gui")

            try:
                geometry = self.settings.value("geometry")
                if geometry:
                    self.restoreGeometry(geometry)
            except BaseException as exc:
                print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
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
        if VISUALIZE_ON:
            self.qtgui_time_sink_x_0_0_0_1_0 = qtgui.time_sink_f(
                1024, #size
                samp_rate, #samp_rate
                'raw', #name
                2, #number of inputs
                None # parent
            )
            self.qtgui_time_sink_x_0_0_0_1_0.set_update_time(0.10)
            self.qtgui_time_sink_x_0_0_0_1_0.set_y_axis(-1, 1)

            self.qtgui_time_sink_x_0_0_0_1_0.set_y_label('Amplitude', "")

            self.qtgui_time_sink_x_0_0_0_1_0.enable_tags(True)
            self.qtgui_time_sink_x_0_0_0_1_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
            self.qtgui_time_sink_x_0_0_0_1_0.enable_autoscale(True)
            self.qtgui_time_sink_x_0_0_0_1_0.enable_grid(False)
            self.qtgui_time_sink_x_0_0_0_1_0.enable_axis_labels(True)
            self.qtgui_time_sink_x_0_0_0_1_0.enable_control_panel(True)
            self.qtgui_time_sink_x_0_0_0_1_0.enable_stem_plot(False)


            labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
                'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
            widths = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            colors = ['blue', 'red', 'green', 'black', 'cyan',
                'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
            alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                1.0, 1.0, 1.0, 1.0, 1.0]
            styles = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            markers = [-1, -1, -1, -1, -1,
                -1, -1, -1, -1, -1]


            for i in range(2):
                if len(labels[i]) == 0:
                    self.qtgui_time_sink_x_0_0_0_1_0.set_line_label(i, "Data {0}".format(i))
                else:
                    self.qtgui_time_sink_x_0_0_0_1_0.set_line_label(i, labels[i])
                self.qtgui_time_sink_x_0_0_0_1_0.set_line_width(i, widths[i])
                self.qtgui_time_sink_x_0_0_0_1_0.set_line_color(i, colors[i])
                self.qtgui_time_sink_x_0_0_0_1_0.set_line_style(i, styles[i])
                self.qtgui_time_sink_x_0_0_0_1_0.set_line_marker(i, markers[i])
                self.qtgui_time_sink_x_0_0_0_1_0.set_line_alpha(i, alphas[i])

            self._qtgui_time_sink_x_0_0_0_1_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0_0_0_1_0.qwidget(), Qt.QWidget)
            self.top_layout.addWidget(self._qtgui_time_sink_x_0_0_0_1_0_win)
            self.qtgui_time_sink_x_0_0_0_0 = qtgui.time_sink_f(
                1024, #size
                samp_rate, #samp_rate
                'filtered', #name
                1, #number of inputs
                None # parent
            )
            self.qtgui_time_sink_x_0_0_0_0.set_update_time(0.10)
            self.qtgui_time_sink_x_0_0_0_0.set_y_axis(-1, 1)

            self.qtgui_time_sink_x_0_0_0_0.set_y_label('Amplitude', "")

            self.qtgui_time_sink_x_0_0_0_0.enable_tags(True)
            self.qtgui_time_sink_x_0_0_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
            self.qtgui_time_sink_x_0_0_0_0.enable_autoscale(True)
            self.qtgui_time_sink_x_0_0_0_0.enable_grid(False)
            self.qtgui_time_sink_x_0_0_0_0.enable_axis_labels(True)
            self.qtgui_time_sink_x_0_0_0_0.enable_control_panel(True)
            self.qtgui_time_sink_x_0_0_0_0.enable_stem_plot(False)


            labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
                'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
            widths = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            colors = ['blue', 'red', 'green', 'black', 'cyan',
                'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
            alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                1.0, 1.0, 1.0, 1.0, 1.0]
            styles = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            markers = [-1, -1, -1, -1, -1,
                -1, -1, -1, -1, -1]


            for i in range(1):
                if len(labels[i]) == 0:
                    self.qtgui_time_sink_x_0_0_0_0.set_line_label(i, "Data {0}".format(i))
                else:
                    self.qtgui_time_sink_x_0_0_0_0.set_line_label(i, labels[i])
                self.qtgui_time_sink_x_0_0_0_0.set_line_width(i, widths[i])
                self.qtgui_time_sink_x_0_0_0_0.set_line_color(i, colors[i])
                self.qtgui_time_sink_x_0_0_0_0.set_line_style(i, styles[i])
                self.qtgui_time_sink_x_0_0_0_0.set_line_marker(i, markers[i])
                self.qtgui_time_sink_x_0_0_0_0.set_line_alpha(i, alphas[i])

            self._qtgui_time_sink_x_0_0_0_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0_0_0_0.qwidget(), Qt.QWidget)
            self.top_layout.addWidget(self._qtgui_time_sink_x_0_0_0_0_win)
            self.qtgui_time_sink_x_0 = qtgui.time_sink_f(
                1024, #size
                samp_rate, #samp_rate
                'rx', #name
                2, #number of inputs
                None # parent
            )
            self.qtgui_time_sink_x_0.set_update_time(0.10)
            self.qtgui_time_sink_x_0.set_y_axis(-1, 1)

            self.qtgui_time_sink_x_0.set_y_label('Amplitude', "")

            self.qtgui_time_sink_x_0.enable_tags(True)
            self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
            self.qtgui_time_sink_x_0.enable_autoscale(True)
            self.qtgui_time_sink_x_0.enable_grid(False)
            self.qtgui_time_sink_x_0.enable_axis_labels(True)
            self.qtgui_time_sink_x_0.enable_control_panel(True)
            self.qtgui_time_sink_x_0.enable_stem_plot(False)


            labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
                'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
            widths = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            colors = ['blue', 'red', 'green', 'black', 'cyan',
                'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
            alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                1.0, 1.0, 1.0, 1.0, 1.0]
            styles = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            markers = [-1, -1, -1, -1, -1,
                -1, -1, -1, -1, -1]


            for i in range(2):
                if len(labels[i]) == 0:
                    self.qtgui_time_sink_x_0.set_line_label(i, "Data {0}".format(i))
                else:
                    self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
                self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
                self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
                self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
                self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
                self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

            self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.qwidget(), Qt.QWidget)
            self.top_layout.addWidget(self._qtgui_time_sink_x_0_win)
            self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
                1024, #size
                window.WIN_BLACKMAN_hARRIS, #wintype
                0, #fc
                samp_rate, #bw
                "", #name
                2,
                None # parent
            )
            self.qtgui_freq_sink_x_0.set_update_time(0.10)
            self.qtgui_freq_sink_x_0.set_y_axis((-100), (-30))
            self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
            self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
            self.qtgui_freq_sink_x_0.enable_autoscale(False)
            self.qtgui_freq_sink_x_0.enable_grid(False)
            self.qtgui_freq_sink_x_0.set_fft_average(1.0)
            self.qtgui_freq_sink_x_0.enable_axis_labels(True)
            self.qtgui_freq_sink_x_0.enable_control_panel(False)
            self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)



            labels = ['', '', '', '', '',
                '', '', '', '', '']
            widths = [1, 1, 1, 1, 1,
                1, 1, 1, 1, 1]
            colors = ["blue", "red", "green", "black", "cyan",
                "magenta", "yellow", "dark red", "dark green", "dark blue"]
            alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                1.0, 1.0, 1.0, 1.0, 1.0]

            for i in range(2):
                if len(labels[i]) == 0:
                    self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
                else:
                    self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
                self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
                self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
                self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

            self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
            self.top_layout.addWidget(self._qtgui_freq_sink_x_0_win)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32(pluto_addr if pluto_addr else iio.get_pluto_uri(), [True, True], 32768)
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
        if VISUALIZE_ON:
            self.analog_quadrature_demod_cf_0_0 = analog.quadrature_demod_cf((1 / 1.5))


        ##################################################
        # Connections
        ##################################################
        if VISUALIZE_ON:
            self.connect((self.analog_quadrature_demod_cf_0, 0), (self.fft_filter_xxx_1_0, 0))
            self.connect((self.analog_quadrature_demod_cf_0, 0), (self.qtgui_time_sink_x_0_0_0_1_0, 1))
            self.connect((self.analog_quadrature_demod_cf_0_0, 0), (self.qtgui_time_sink_x_0_0_0_1_0, 0))
            self.connect((self.blocks_float_to_char_0, 0), (self.blocks_pack_k_bits_bb_0_0_1, 0))
            self.connect((self.blocks_pack_k_bits_bb_0_0_1, 0), (self.zeromq_pub_sink_0_0, 0))
            self.connect((self.digital_symbol_sync_xx_0, 0), (self.epy_block_0_0, 0))
            self.connect((self.digital_symbol_sync_xx_0, 0), (self.qtgui_time_sink_x_0, 0))
            self.connect((self.epy_block_0_0, 0), (self.blocks_float_to_char_0, 0))
            self.connect((self.epy_block_0_0, 0), (self.qtgui_time_sink_x_0, 1))
            self.connect((self.fft_filter_xxx_1_0, 0), (self.digital_symbol_sync_xx_0, 0))
            self.connect((self.fft_filter_xxx_1_0, 0), (self.qtgui_time_sink_x_0_0_0_0, 0))
            self.connect((self.fft_filter_xxx_1_0_0, 0), (self.analog_quadrature_demod_cf_0, 0))
            self.connect((self.fft_filter_xxx_1_0_0, 0), (self.qtgui_freq_sink_x_0, 1))
            self.connect((self.iio_pluto_source_0, 0), (self.analog_quadrature_demod_cf_0_0, 0))
            self.connect((self.iio_pluto_source_0, 0), (self.fft_filter_xxx_1_0_0, 0))
            self.connect((self.iio_pluto_source_0, 0), (self.qtgui_freq_sink_x_0, 0))
        else:
            self.connect((self.analog_quadrature_demod_cf_0, 0), (self.fft_filter_xxx_1_0, 0))
            self.connect((self.blocks_float_to_char_0, 0), (self.blocks_pack_k_bits_bb_0_0_1, 0))
            self.connect((self.blocks_pack_k_bits_bb_0_0_1, 0), (self.zeromq_pub_sink_0_0, 0))
            self.connect((self.digital_symbol_sync_xx_0, 0), (self.epy_block_0_0, 0))
            self.connect((self.epy_block_0_0, 0), (self.blocks_float_to_char_0, 0))
            self.connect((self.fft_filter_xxx_1_0, 0), (self.digital_symbol_sync_xx_0, 0))
            self.connect((self.fft_filter_xxx_1_0_0, 0), (self.analog_quadrature_demod_cf_0, 0))
            self.connect((self.iio_pluto_source_0, 0), (self.fft_filter_xxx_1_0_0, 0))

    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "region_games_with_gui")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        # self.set_taps_lpf(firdes.low_pass(1.0, self.samp_rate, 19230, 2000))
        # self.set_taps_lpf_pre(firdes.low_pass(1.0, self.samp_rate, 270000, 10000))
        self.iio_pluto_source_0.set_samplerate(self.samp_rate)
        if VISUALIZE_ON:
            self.qtgui_freq_sink_x_0.set_frequency_range(0, self.samp_rate)
            self.qtgui_time_sink_x_0.set_samp_rate(self.samp_rate)
            self.qtgui_time_sink_x_0_0_0_0.set_samp_rate(self.samp_rate)
            self.qtgui_time_sink_x_0_0_0_1_0.set_samp_rate(self.samp_rate)

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
    ):
        try:
            if VISUALIZE_ON:
                self.qapp = Qt.QApplication.instance() or Qt.QApplication(sys.argv)
            self.tb = region_games(zmq_send_addr, pluto_addr, fc, bandwidth, taps_lpf, taps_pre)
            def sig_handler(sig=None, frame=None):
                self.tb.stop()
                self.tb.wait()
                if VISUALIZE_ON:
                    Qt.QApplication.quit()
                sys.exit(0)
            signal.signal(signal.SIGINT, sig_handler)
            signal.signal(signal.SIGTERM, sig_handler)
        except Exception as e:
            logging.log(logging.ERROR, f"[GnuradioClass] error initializing gnuradio flowgraph: {e}")

    def start(self):
        try:
            self.tb.start()
            self.tb.flowgraph_started.set()
            if VISUALIZE_ON:
                self.tb.show()
                self._timer = Qt.QTimer(self.tb)
                self._timer.timeout.connect(lambda: None)
                self._timer.start(500)
                self.qapp.exec_()
        except Exception as e:
            logging.log(logging.ERROR, f"[GnuradioClass] error starting gnuradio flowgraph: {e}")

    def stop(self):
        try:
            self.tb.stop()
            self.tb.wait()
        except Exception as e:
            logging.log(logging.ERROR, f"[GnuradioClass] error stopping gnuradio flowgraph: {e}")


if __name__ == '__main__':
    from def_signal import *
    from def_taps import *
    from time import sleep
    t = top(
        "tcp://127.0.0.1:2236",
        "192.168.2.1",
        FC_RED,
        BW_SIG,
        TAPS_LPF,
        TAPS_LPF_PRE
    )
    t.start()
    cnt = 0
    while(True):
        sleep(1)
        cnt += 1
        print(f"running...{cnt}")
        if cnt == 15:
            break
    t.stop()

    t.start()
    cnt = 0
    while(True):
        sleep(1)
        cnt += 1
        print(f"running...{cnt}")
        if cnt == 15:
            break
    t.stop()

