#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# Author: wangt
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import blocks
from gnuradio import digital
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
from gnuradio import zeromq
import threading



class only_tx(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
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

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "only_tx")

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
        self.iio_pluto_sink_0 = iio.fmcomms2_sink_fc32('192.168.3.1' if '192.168.3.1' else iio.get_pluto_uri(), [True, True], 32768, True)
        self.iio_pluto_sink_0.set_len_tag_key('')
        self.iio_pluto_sink_0.set_bandwidth(signal_bandwidth)
        self.iio_pluto_sink_0.set_frequency(fc_1)
        self.iio_pluto_sink_0.set_samplerate(samp_rate)
        self.iio_pluto_sink_0.set_attenuation(0, 47)
        self.iio_pluto_sink_0.set_filter_params('Auto', '', 0, 0)
        self.digital_gfsk_mod_0 = digital.gfsk_mod(
            samples_per_symbol=52,
            sensitivity=sensitivity_signal,
            bt=0.35,
            verbose=False,
            log=False,
            do_unpack=True)
        self.blocks_pack_k_bits_bb_0_0 = blocks.pack_k_bits_bb(8)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_pack_k_bits_bb_0_0, 0), (self.digital_gfsk_mod_0, 0))
        self.connect((self.digital_gfsk_mod_0, 0), (self.iio_pluto_sink_0, 0))
        self.connect((self.zeromq_sub_source_0, 0), (self.blocks_pack_k_bits_bb_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "only_tx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_taps_lpf(firdes.low_pass(1.0, self.samp_rate, 19230, 2000))
        self.set_taps_lpf_pre(firdes.low_pass(1.0, self.samp_rate, 270000, 10000))
        self.iio_pluto_sink_0.set_samplerate(self.samp_rate)

    def get_taps_lpf_pre(self):
        return self.taps_lpf_pre

    def set_taps_lpf_pre(self, taps_lpf_pre):
        self.taps_lpf_pre = taps_lpf_pre

    def get_taps_lpf(self):
        return self.taps_lpf

    def set_taps_lpf(self, taps_lpf):
        self.taps_lpf = taps_lpf

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
        self.iio_pluto_sink_0.set_frequency(self.fc_1)

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc




def main(top_block_cls=only_tx, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
