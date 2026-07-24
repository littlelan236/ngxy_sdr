import numpy as np
from PyQt5.QtCore import QTimer

try:
    from pyqt_scroll_charts import ScrollChartsApp, ChartConfig
except ImportError:
    from scroll_charts import ScrollChartsApp, ChartConfig

SAMPLES_PER_CHUNK = int(1e5)
FEED_HZ = 10.0
SAMPLE_RATE = 1e6


def build_configs():
    return [
        ChartConfig(
            num_series=1,
            buffer_size=256,
            autoscale=True,
            y_range=(-2.0, 2.0),
            hline_values=[0.0],
            title="Input",
            plot_mode="time",
        ),
        ChartConfig(
            num_series=1,
            buffer_size=256,
            y_range=(-90.0, 0.0),
            hline_values=[],
            title="FFT",
            plot_mode="fft",
            sample_rate=SAMPLE_RATE,
            fft_size=1024,
            fft_shift=True,
            fft_db=True,
        ),
    ]


def main():
    app = ScrollChartsApp(
        build_configs(),
        uniform_height=260,
        time_max_refresh_hz=20.0,
    )
    app.window.setWindowTitle("Scroll Charts Stress Test")
    app.show()

    def push_chunk():
        real = np.random.randn(SAMPLES_PER_CHUNK)
        imag = np.random.randn(SAMPLES_PER_CHUNK)
        samples = (real + 1j * imag).astype(np.complex64, copy=False)
        app.add_values(0, samples)
        app.add_values(1, samples)

    timer = QTimer()
    timer.setInterval(max(1, int(1000.0 / FEED_HZ)))
    timer.timeout.connect(push_chunk)
    timer.start()

    app._app.exec_()


if __name__ == "__main__":
    main()
