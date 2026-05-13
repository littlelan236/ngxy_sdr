import sys
import time
import itertools
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QScrollArea, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt, QTimer

# 折线图单元模块
try:
    # package mode: from pyqt_scroll_charts.scroll_charts import ...
    from .chart_item import ChartItem, FftChartItem
except ImportError:
    # script mode: python pyqt_scroll_charts/scroll_charts.py
    from chart_item import ChartItem, FftChartItem

@dataclass
class ChartConfig:
    """Typed configuration for one chart panel."""

    num_series: int = 1
    buffer_size: int = 50
    y_range: Optional[Tuple[float, float]] = None
    autoscale: bool = False
    hline_values: Sequence[float] = field(default_factory=list)
    title: Optional[str] = None
    plot_mode: str = 'time'
    sample_rate: Optional[float] = None
    fft_size: Optional[int] = None
    fft_shift: bool = True
    fft_db: bool = True
    fft_max_refresh_hz: Optional[float] = 20.0


def _normalize_chart_config(cfg: Union[ChartConfig, Mapping[str, Any]]) -> ChartConfig:
    """Accept dataclass or dict-like configs and normalize to ChartConfig."""
    if isinstance(cfg, ChartConfig):
        return cfg

    if isinstance(cfg, Mapping):
        return ChartConfig(
            num_series=int(cfg.get('num_series', 1)),
            buffer_size=int(cfg.get('buffer_size', 50)),
            y_range=cfg.get('y_range'),
            autoscale=bool(cfg.get('autoscale', False)),
            hline_values=cfg.get('hline_values', []),
            title=cfg.get('title'),
            plot_mode=str(cfg.get('plot_mode', 'time')).lower(),
            sample_rate=cfg.get('sample_rate'),
            fft_size=cfg.get('fft_size'),
            fft_shift=bool(cfg.get('fft_shift', True)),
            fft_db=bool(cfg.get('fft_db', True)),
            fft_max_refresh_hz=cfg.get('fft_max_refresh_hz', 20.0),
        )

    raise TypeError(
        'Each chart config must be ChartConfig or a dict-like mapping.'
    )


def _to_python_scalar(value: Any) -> Any:
    """Convert numpy scalar types to native Python scalars."""
    if isinstance(value, np.generic):
        return value.item()
    return value


def _normalize_values_list(values: Any) -> list:
    """Normalize incoming sample containers to a Python list for signal transport."""
    if isinstance(values, np.ndarray):
        if values.ndim == 0:
            return [_to_python_scalar(values.item())]
        return [_to_python_scalar(v) for v in values.reshape(-1)]

    if isinstance(values, list):
        return [_to_python_scalar(v) for v in values]

    if isinstance(values, tuple):
        return [_to_python_scalar(v) for v in values]

    if hasattr(values, '__iter__') and not isinstance(values, (str, bytes, bytearray)):
        try:
            return [_to_python_scalar(v) for v in list(values)]
        except Exception:
            pass

    return [_to_python_scalar(values)]


def _trim_samples(values: Any, maxlen: Optional[int]) -> Any:
    if maxlen is None or maxlen <= 0:
        return values

    if isinstance(values, np.ndarray):
        if values.ndim == 0:
            return values
        flat = values.reshape(-1)
        if flat.size <= maxlen:
            return flat
        return flat[-maxlen:]

    if isinstance(values, list):
        if len(values) <= maxlen:
            return values
        return values[-maxlen:]

    if isinstance(values, tuple):
        if len(values) <= maxlen:
            return values
        return values[-maxlen:]

    if isinstance(values, deque):
        if len(values) <= maxlen:
            return values
        start = len(values) - maxlen
        return list(itertools.islice(values, start, None))

    if hasattr(values, '__iter__') and not isinstance(values, (str, bytes, bytearray)):
        tail = deque(values, maxlen=maxlen)
        return list(tail)

    return values


def _take_head(values: Any, count: int) -> list:
    if count <= 0:
        return []

    if isinstance(values, np.ndarray):
        if values.ndim == 0:
            return [_to_python_scalar(values.item())]
        return values.reshape(-1)[:count].tolist()

    if isinstance(values, list):
        return values[:count]

    if isinstance(values, tuple):
        return list(values[:count])

    if isinstance(values, deque):
        return list(itertools.islice(values, count))

    if hasattr(values, '__iter__') and not isinstance(values, (str, bytes, bytearray)):
        return list(itertools.islice(values, count))

    return [_to_python_scalar(values)]


def _pretrim_values(values: Any, num_series: int, buffer_size: Optional[int]) -> Any:
    if num_series <= 1:
        return _trim_samples(values, buffer_size)

    if isinstance(values, np.ndarray) and values.ndim >= 2 and values.shape[0] == num_series:
        return [_trim_samples(values[i], buffer_size) for i in range(num_series)]

    if isinstance(values, (list, tuple)) and len(values) == num_series:
        return [_trim_samples(v, buffer_size) for v in values]

    return _take_head(values, num_series)


class ScrollChartManager(QWidget):
    """可复用的滚动图表管理器。

    Signals defined here allow thread-safe updates from background threads.

        使用方法：在实例化时传入 chart_configs 列表，每个 config 可以是 ChartConfig
        或兼容的 dict（自动转换），字段包括：
      - num_series: int (每个 Chart 的曲线数量)
      - buffer_size: int
      - y_range: tuple
      - hline_values: list
      - title: str

    所有 Chart 的高度通过 `uniform_height` 指定。初始化时每条曲线用 0 填充。
    通过 ``add_values(chart_idx, values_list)`` 或 ``add_value(chart_idx, series_idx, value)``
    在外部推入新数据点以更新图表。
    """
    addValuesSignal = pyqtSignal(int, object)
    addValueSignal = pyqtSignal(int, int, object)
    def __init__(self, chart_configs, chart_height=200, parent=None, time_max_refresh_hz: Optional[float] = 20.0):
        super().__init__(parent)
        # connect signals for thread-safe updates
        self.addValuesSignal.connect(self._handle_add_values)
        self.addValueSignal.connect(self._handle_add_value)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._fft_items = []
        self._time_items = []
        self._time_refresh_timer = None
        self._time_max_refresh_hz = time_max_refresh_hz

        self._refresh_button = QPushButton("绘制一次", self)
        self._refresh_button.clicked.connect(self.refresh_all)
        layout.addWidget(self._refresh_button)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)

        container = QWidget()
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(10)

        self.items = []
        self._chart_configs = []

        for raw_cfg in chart_configs:
            cfg = _normalize_chart_config(raw_cfg)
            self._chart_configs.append(cfg)
            num_series = cfg.num_series
            buffer_size = cfg.buffer_size
            y_range = cfg.y_range
            hline_values = cfg.hline_values
            title = cfg.title
            autoscale = cfg.autoscale
            plot_mode = cfg.plot_mode
            sample_rate = cfg.sample_rate
            fft_size = cfg.fft_size
            fft_shift = cfg.fft_shift
            fft_db = cfg.fft_db
            fft_max_refresh_hz = cfg.fft_max_refresh_hz

            # 初始化为全0的数据缓冲区（每条曲线长度为 buffer_size）
            data_list = [[0] * buffer_size for _ in range(num_series)]

            if plot_mode == 'fft':
                item = FftChartItem(
                    data_list,
                    buffer_size=buffer_size,
                    height=chart_height,
                    y_range=y_range,
                    autoscale=autoscale,
                    hline_values=hline_values,
                    title=title,
                    sample_rate=sample_rate,
                    fft_size=fft_size,
                    fft_shift=fft_shift,
                    fft_db=fft_db,
                    fft_max_refresh_hz=fft_max_refresh_hz,
                )
                self._fft_items.append(item)
            else:
                item = ChartItem(
                    data_list,
                    buffer_size=buffer_size,
                    height=chart_height,
                    y_range=y_range,
                    autoscale=autoscale,
                    hline_values=hline_values,
                    title=title,
                )
                item.set_silent(True)
                self._time_items.append(item)
            self.items.append(item)
            vlayout.addWidget(item)

        self._refresh_button.setEnabled(bool(self.items))

        self._start_time_refresh_timer()

        vlayout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _start_time_refresh_timer(self):
        if not self._time_items:
            return
        if self._time_max_refresh_hz is None:
            return
        try:
            hz = float(self._time_max_refresh_hz)
        except Exception:
            return
        if hz <= 0:
            return
        interval_ms = max(1, int(1000.0 / hz))
        timer = QTimer(self)
        timer.setInterval(interval_ms)
        timer.timeout.connect(self._refresh_time_series)
        timer.start()
        self._time_refresh_timer = timer

    def _refresh_time_series(self):
        for item in self._time_items:
            item.refresh_now()

    def _handle_add_values(self, chart_idx, values_list):
        if 0 <= chart_idx < len(self.items):
            self.items[chart_idx].add_values(values_list)

    def _handle_add_value(self, chart_idx, series_idx, value):
        if 0 <= chart_idx < len(self.items):
            self.items[chart_idx].add_value(value, series_idx)

    def add_values(self, chart_idx, values_list):
        """线程安全版本：无论在哪个线程调用，都会在主线程执行更新。"""
        safe_chart_idx = int(_to_python_scalar(chart_idx))
        if 0 <= safe_chart_idx < len(self._chart_configs):
            cfg = self._chart_configs[safe_chart_idx]
            values_list = _pretrim_values(values_list, cfg.num_series, cfg.buffer_size)
        self.addValuesSignal.emit(safe_chart_idx, values_list)

    def refresh_all(self):
        """手动绘制一次所有图表。"""
        for item in self._time_items:
            item.refresh_now()
        for item in self._fft_items:
            item.refresh_fft()

    def refresh_fft(self):
        """兼容式别名：手动绘制一次所有图表。"""
        self.refresh_all()

    def add_value(self, chart_idx, series_idx, value):
        """线程安全版本：无论在哪个线程调用，都会在主线程执行更新。"""
        safe_chart_idx = int(_to_python_scalar(chart_idx))
        safe_series_idx = int(_to_python_scalar(series_idx))
        safe_value = _to_python_scalar(value)
        self.addValueSignal.emit(safe_chart_idx, safe_series_idx, safe_value)

    def draw_fft(self):
        """兼容式别名：手动绘制一次 FFT 图。"""
        self.refresh_all()


class MainWindow(QWidget):
    """简单演示窗口：展示 ScrollChartManager 并在需要时由上层程序调用数据更新。"""
    def __init__(self, chart_configs, uniform_height=200, time_max_refresh_hz: Optional[float] = 20.0):
        super().__init__()
        self.setWindowTitle("Scroll Charts Demo")
        layout = QVBoxLayout(self)

        self.manager = ScrollChartManager(
            chart_configs,
            chart_height=uniform_height,
            time_max_refresh_hz=time_max_refresh_hz,
        )
        layout.addWidget(self.manager)

        self.setLayout(layout)
        self.resize(1080, 720)


class ScrollChartsApp:
    """封装整体程序，可在其他模块中实例化并调用。
    * 非阻塞：只需调用 ``show()``，然后由外部
      的 QApplication 或循环定期执行 ``process_events()``。
    """
    def __init__(self, chart_configs, uniform_height=200, time_max_refresh_hz: Optional[float] = 20.0):
        # 如果已有 QApplication 实例则复用；否则创建一个。
        self._app = QApplication.instance() or QApplication(sys.argv)
        self.window = MainWindow(
            chart_configs,
            uniform_height=uniform_height,
            time_max_refresh_hz=time_max_refresh_hz,
        )

    def add_values(self, chart_idx, values_list):
        """追加数据点给指定 chart。"""
        self.window.manager.add_values(chart_idx, values_list)

    def add_value(self, chart_idx, series_idx, value):
        """向指定曲线追加单个值。"""
        self.window.manager.add_value(chart_idx, series_idx, value)

    def refresh_fft(self):
        """手动绘制一次所有 FFT 图。"""
        self.window.manager.refresh_all()

    def draw_fft(self):
        """手动绘制一次所有 FFT 图。"""
        self.window.manager.refresh_all()

    def refresh_all(self):
        """手动绘制一次所有图表。"""
        self.window.manager.refresh_all()

    def show(self):
        self.window.show()

    def process_events(self):
        """在外部主循环中调用此方法来处理 Qt 事件。"""
        self._app.processEvents()