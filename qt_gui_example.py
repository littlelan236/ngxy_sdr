import sys
import time
from pathlib import Path

import numpy as np

# Ensure workspace root is importable when running this file directly.
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from pyqt_scroll_charts import ChartConfig, ScrollChartsApp
except ImportError:
    from pyqt_scroll_charts import ChartConfig, ScrollChartsApp


SAMPLE_RATE = 200.0
DT = 1.0 / SAMPLE_RATE

configs = [
    # 时域图：实时更新
    ChartConfig(
        num_series=1,
        buffer_size=256,
        y_range=(-2.0, 2.0),
        hline_values=[0.0],
        title='Time Domain Signal',
        plot_mode='time',
    ),
    # 频域图：buffer 持续更新，但仅在点击“绘制频域”时刷新一次
    ChartConfig(
        num_series=1,
        buffer_size=256,
        y_range=(-100.0, 10.0),
        hline_values=[-20.0],
        title='FFT Spectrum (Manual Draw)',
        plot_mode='fft',
        sample_rate=SAMPLE_RATE,
        fft_size=256,
        fft_shift=True,
        fft_db=True,
    ),
]

app = ScrollChartsApp(configs, uniform_height=320)
app.show()

print('Demo started: 图1为时域实时更新，图2为 FFT。')
print('请点击窗口顶部的“绘制频域”按钮来刷新 FFT 图。')

# Simulate an external non-blocking data source loop.
t = 0.0
while True:
    # 组合两种频率分量，便于在 FFT 上观察谱峰
    s1 = np.sin(2 * np.pi * 12.0 * t)
    s2 = 0.5 * np.sin(2 * np.pi * 30.0 * t)
    noise = 0.05 * np.random.randn()
    sample = s1 + s2 + noise

    # chart 0: time-domain (实时绘制)
    app.add_values(0, [sample])
    # chart 1: fft buffer only (不实时绘制，等待按钮触发)
    app.add_values(1, [sample])

    app.process_events()
    time.sleep(DT)
    t += DT
