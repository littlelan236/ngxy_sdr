from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QToolTip
from PyQt5.QtChart import QChart, QChartView, QLineSeries
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt
from collections import deque
import numpy as np

class ChartItem(QWidget):
    """支持多条曲线的折线图组件。

    参数
    ----------
    data_list : list of lists
        多条曲线的初始数据，例：[[1,2,3], [4,5,6]] 表示2条曲线
        如果为单个列表 [1,2,3]，则作为一条曲线处理
    buffer_size : int or None
        每条曲线的缓冲区长度，缺省使用初始数据的最大长度
    width, height : int or None
        控件尺寸
    y_range : tuple or None
        纵轴范围 (min, max)
    hline_values : list or None
        水平参考线的 y 值列表
    title : str or None
        图表标题
    """

    # 默认颜色列表（用于不同曲线）
    DEFAULT_COLORS = [
        QColor('#6FA8DC'),  # 柔和蓝
        QColor('#F4A261'),  # 柔和橙
        QColor('#90BE6D'),  # 柔和绿
        QColor('#F6C177'),  # 淡黄
        QColor('#B39CD0'),  # 淡紫
        QColor('#9AD1D4'),  # 淡青
    ]

    def __init__(
        self,
        data_list=None,
        buffer_size=None,
        width=None,
        height=None,
        y_range=None,
        autoscale=False,
        hline_values=None,
        title=None,
        parent=None,
    ):
        super().__init__(parent)

        # 规范化 data_list：确保是 list of lists
        if data_list is None:
            data_list = [[]]
        elif not isinstance(data_list, list):
            data_list = [data_list]
        elif len(data_list) > 0 and not isinstance(data_list[0], (list, tuple)):
            # 单个列表，转换为 list of lists
            data_list = [data_list]

        self.num_series = len(data_list)

        # 初始化多个缓冲区
        if buffer_size is None:
            buffer_size = max(len(d) for d in data_list) if data_list and any(data_list) else 10
        self.buffer_size = buffer_size
        self.fill_zeros = False  # 禁用前面填充0的功能
        self.autoscale = bool(autoscale)

        self.buffer_list = []
        for data in data_list:
            initial = list(data) if data else []
            buf = deque(initial, maxlen=self.buffer_size)
            self.buffer_list.append(buf)

        # 创建多个折线系列，每个对应一条曲线
        self.series_list = []
        self.chart = QChart()

        for i in range(self.num_series):
            series = QLineSeries()
            self.series_list.append(series)
            self.chart.addSeries(series)

            # 设置颜色
            color_idx = i % len(self.DEFAULT_COLORS)
            pen = series.pen()
            pen.setColor(self.DEFAULT_COLORS[color_idx])
            pen.setWidth(1)  # 更细的线条
            series.setPen(pen)

        self.chart.createDefaultAxes()

        # 统一提前拿到坐标轴，避免分支里变量未定义
        x_axis = self.chart.axisX()
        y_axis = self.chart.axisY()

        # 调整 y 轴范围
        if y_range is not None:
            try:
                ymin, ymax = y_range
            except Exception:
                ymin, ymax = None, None
            else:
                if y_axis is not None and ymin is not None and ymax is not None:
                    y_axis.setRange(ymin, ymax)

        # 设置 X 轴范围为 0 到 buffer_size-1，防止坐标轴自动调整导致显示混乱
        if x_axis is not None:
            x_axis.setRange(0, max(1, self.buffer_size - 1))
            # 使用 Consolas 字体的较小字号用于坐标刻度
            try:
                x_axis.setLabelsFont(QFont('Consolas', 9))
            except Exception:
                pass
        if y_axis is not None:
            try:
                y_axis.setLabelsFont(QFont('Consolas', 9))
            except Exception:
                pass

        # 绘制水平虚线并关闭背景网格
        if hline_values:
            x_axis = self.chart.axisX()
            y_axis = self.chart.axisY()
            if x_axis is not None:
                try:
                    x_axis.setGridLineVisible(False)
                except Exception:
                    pass
            if y_axis is not None:
                try:
                    y_axis.setGridLineVisible(False)
                except Exception:
                    pass

            # 计算横线跨度
            x_len = self.buffer_size - 1 if self.buffer_size and self.buffer_size > 0 else 0
            for yval in hline_values:
                line = QLineSeries()
                line.append(0, yval)
                line.append(x_len, yval)
                pen = line.pen()
                pen.setStyle(Qt.DashLine)
                pen.setWidth(1)
                pen.setColor(QColor('#BDBDBD'))
                line.setPen(pen)
                self.chart.addSeries(line)
                if x_axis is not None:
                    line.attachAxis(x_axis)
                if y_axis is not None:
                    line.attachAxis(y_axis)

        self.chart.legend().hide()
        if title is not None:
            self.chart.setTitle(title)
        else:
            self.chart.setTitle("Line Chart")

        # 设定图表整体和绘图区的柔和背景色
        try:
            self.chart.setBackgroundBrush(QColor('#F5F7FA'))
            self.chart.setPlotAreaBackgroundBrush(QColor('#FFFFFF'))
        except Exception:
            pass

        # 设置字体为 Consolas（如果可用）用于标题和视图
        try:
            self.chart.setTitleFont(QFont('Consolas', 11))
        except Exception:
            pass

        # 使用自定义视图以获取鼠标坐标
        class CoordinateChartView(QChartView):
            def __init__(self, chart, parent=None):
                super().__init__(chart, parent)
                self.setMouseTracking(True)

            def mouseMoveEvent(self, event):
                # 将鼠标位置转换到图表坐标系
                pt = self.chart().mapToValue(event.pos())
                text = f"({pt.x():.2f}, {pt.y():.2f})"
                QToolTip.showText(event.globalPos(), text, self)
                super().mouseMoveEvent(event)

        view = CoordinateChartView(self.chart)
        view.setRenderHint(QPainter.Antialiasing)
        # 让图表视图在水平方向上可扩展，垂直方向与控件高度一致
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # 确保 QChartView 的高度与指定高度一致，否则其 sizeHint 可能很小
        if height is not None:
            view.setFixedHeight(height)
        else:
            view.setFixedHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        # 应用尺寸参数：固定高度，水平方向跟随父窗口伸缩
        if height is not None:
            self.setFixedHeight(height)
        else:
            self.setFixedHeight(150)
        # 宽度允许扩展以适配父容器（如可调整大小的主窗口或滚动区）
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 初始刷新
        self._refresh_all_series()

        # 标志指示是否在追加数据时刷新图表
        self._silent = False

    def _refresh_all_series(self):
        """刷新所有系列。"""
        for i, series in enumerate(self.series_list):
            self._refresh_single_series(i)
        if self.autoscale:
            self._update_y_axis_autoscale()

    def _update_y_axis_autoscale(self):
        y_axis = self.chart.axisY()
        if y_axis is None:
            return

        values = []
        for buf in self.buffer_list:
            for v in buf:
                try:
                    if np.iscomplexobj(v):
                        values.append(float(np.real(v)))
                    else:
                        values.append(float(v))
                except Exception:
                    continue

        if not values:
            return

        ymin = min(values)
        ymax = max(values)
        if ymax <= ymin:
            ymax = ymin + 1.0
        margin = 0.05 * (ymax - ymin)
        y_axis.setRange(ymin - margin, ymax + margin)

    def _refresh_single_series(self, series_idx):
        """刷新单条系列。"""
        if series_idx < 0 or series_idx >= len(self.series_list):
            return

        series = self.series_list[series_idx]
        buf = self.buffer_list[series_idx]

        series.clear()

        if self.fill_zeros and len(buf) < self.buffer_size:
            # 前面用 0 填充
            pad = [0] * (self.buffer_size - len(buf))
            data_iter = pad + list(buf)
        else:
            data_iter = list(buf)

        for idx, value in enumerate(data_iter):
            series.append(idx, value)

    def add_values(self, values_list):
        """向每条曲线追加一个新数据点。

        参数
        ----------
        values_list : list
            与曲线数量相同长度的列表，每个元素是对应曲线的新数据点
        """
        for i, val in enumerate(values_list):
            if i < len(self.buffer_list):
                buf = self.buffer_list[i]
                buf.append(val)
                # deque with maxlen auto-discards oldest; ensure property holds
                if self.buffer_size is not None and len(buf) > self.buffer_size:
                    # convert to new deque in case maxlen not set
                    self.buffer_list[i] = deque(list(buf)[-self.buffer_size:], maxlen=self.buffer_size)
        if not getattr(self, '_silent', False):
            self._refresh_all_series()

    def add_value(self, value, series_idx=0):
        """向指定曲线追加单个数据点（向后兼容）。"""
        if series_idx < len(self.buffer_list):
            buf = self.buffer_list[series_idx]
            buf.append(value)
            if self.buffer_size is not None and len(buf) > self.buffer_size:
                self.buffer_list[series_idx] = deque(list(buf)[-self.buffer_size:], maxlen=self.buffer_size)
            if not getattr(self, '_silent', False):
                self._refresh_single_series(series_idx)

    def update_data(self, data_list):
        """用新数据替换所有缓冲区。"""
        if not isinstance(data_list, list) or (len(data_list) > 0 and not isinstance(data_list[0], (list, tuple))):
            data_list = [data_list]

        for i, data in enumerate(data_list):
            if i < len(self.buffer_list):
                data_list_full = list(data)
                if len(data_list_full) > self.buffer_size:
                    data_list_full = data_list_full[-self.buffer_size :]
                self.buffer_list[i] = deque(data_list_full, maxlen=self.buffer_size)

    def set_silent(self, silent: bool):
        """如果设置为 True，则新增数据不会立即绘制，直到恢复。"""
        self._silent = silent
        if not silent:
            self._refresh_all_series()


class FftChartItem(QWidget):
    """按需绘制的 FFT 频域图组件。

    该组件只维护数据缓冲区；调用 refresh_fft() 时才会把当前缓冲区
    转换为频谱并绘制到图表上。
    """

    DEFAULT_COLORS = ChartItem.DEFAULT_COLORS

    def __init__(
        self,
        data_list=None,
        buffer_size=None,
        width=None,
        height=None,
        y_range=None,
        autoscale=False,
        hline_values=None,
        title=None,
        sample_rate=None,
        fft_size=None,
        fft_shift=True,
        fft_db=True,
        fft_max_refresh_hz=20.0,
        parent=None,
    ):
        super().__init__(parent)

        if data_list is None:
            data_list = [[]]
        elif not isinstance(data_list, list):
            data_list = [data_list]
        elif len(data_list) > 0 and not isinstance(data_list[0], (list, tuple)):
            data_list = [data_list]

        self.num_series = len(data_list)
        if buffer_size is None:
            buffer_size = max(len(d) for d in data_list) if data_list and any(data_list) else 10
        self.buffer_size = buffer_size
        self.autoscale = bool(autoscale)
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.fft_shift = bool(fft_shift)
        self.fft_db = bool(fft_db)
        self.fft_max_refresh_hz = fft_max_refresh_hz
        self._silent = False

        self.buffer_list = []
        for data in data_list:
            initial = list(data) if data else []
            buf = deque(initial, maxlen=self.buffer_size)
            self.buffer_list.append(buf)

        self.series_list = []
        self.chart = QChart()
        for i in range(self.num_series):
            series = QLineSeries()
            self.series_list.append(series)
            self.chart.addSeries(series)
            color_idx = i % len(self.DEFAULT_COLORS)
            pen = series.pen()
            pen.setColor(self.DEFAULT_COLORS[color_idx])
            pen.setWidth(1)
            series.setPen(pen)

        self.chart.createDefaultAxes()
        x_axis = self.chart.axisX()
        y_axis = self.chart.axisY()

        if x_axis is not None:
            try:
                x_axis.setLabelsFont(QFont('Consolas', 9))
            except Exception:
                pass
        if y_axis is not None:
            try:
                y_axis.setLabelsFont(QFont('Consolas', 9))
            except Exception:
                pass

        if y_range is not None:
            try:
                ymin, ymax = y_range
            except Exception:
                ymin, ymax = None, None
            else:
                if y_axis is not None and ymin is not None and ymax is not None:
                    y_axis.setRange(ymin, ymax)
        elif y_axis is not None:
            if self.fft_db:
                y_axis.setRange(-120.0, 0.0)
            else:
                y_axis.setRange(0.0, 1.0)

        if hline_values:
            x_len = max(1, self.buffer_size - 1)
            for yval in hline_values:
                line = QLineSeries()
                line.append(0, yval)
                line.append(x_len, yval)
                pen = line.pen()
                pen.setStyle(Qt.DashLine)
                pen.setWidth(1)
                pen.setColor(QColor('#BDBDBD'))
                line.setPen(pen)
                self.chart.addSeries(line)
                if x_axis is not None:
                    line.attachAxis(x_axis)
                if y_axis is not None:
                    line.attachAxis(y_axis)

        self.chart.legend().hide()
        if title is not None:
            self.chart.setTitle(title)
        else:
            self.chart.setTitle("FFT Chart")

        try:
            self.chart.setBackgroundBrush(QColor('#F5F7FA'))
            self.chart.setPlotAreaBackgroundBrush(QColor('#FFFFFF'))
        except Exception:
            pass

        try:
            self.chart.setTitleFont(QFont('Consolas', 11))
        except Exception:
            pass

        class CoordinateChartView(QChartView):
            def __init__(self, chart, parent=None):
                super().__init__(chart, parent)
                self.setMouseTracking(True)

            def mouseMoveEvent(self, event):
                pt = self.chart().mapToValue(event.pos())
                text = f"({pt.x():.2f}, {pt.y():.2f})"
                QToolTip.showText(event.globalPos(), text, self)
                super().mouseMoveEvent(event)

        view = CoordinateChartView(self.chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if height is not None:
            view.setFixedHeight(height)
        else:
            view.setFixedHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        if height is not None:
            self.setFixedHeight(height)
        else:
            self.setFixedHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _prepare_fft_series(self, buf):
        samples = np.asarray(list(buf), dtype=np.complex128)
        if samples.size == 0:
            return np.array([]), np.array([])

        nfft = int(self.fft_size) if self.fft_size else int(samples.size)
        if nfft <= 0:
            nfft = int(samples.size)
        if nfft <= 0:
            return np.array([]), np.array([])

        if samples.size < nfft:
            padded = np.zeros(nfft, dtype=np.complex128)
            padded[-samples.size:] = samples
            samples = padded
        elif samples.size > nfft:
            samples = samples[-nfft:]

        if self.sample_rate:
            freq_step = 1.0 / float(self.sample_rate)
        else:
            freq_step = 1.0

        spectrum = np.fft.fft(samples, n=nfft)
        freqs = np.fft.fftfreq(nfft, d=freq_step)

        if self.fft_shift:
            spectrum = np.fft.fftshift(spectrum)
            freqs = np.fft.fftshift(freqs)
        else:
            order = np.argsort(freqs)
            freqs = freqs[order]
            spectrum = spectrum[order]

        magnitude = np.abs(spectrum) / max(1, nfft)
        if self.fft_db:
            magnitude = 20.0 * np.log10(np.maximum(magnitude, 1e-12))

        return freqs, magnitude

    def _refresh_single_series(self, series_idx):
        if series_idx < 0 or series_idx >= len(self.series_list):
            return

        series = self.series_list[series_idx]
        buf = self.buffer_list[series_idx]
        freqs, magnitude = self._prepare_fft_series(buf)

        series.clear()
        for xval, yval in zip(freqs, magnitude):
            series.append(float(xval), float(yval))

    def refresh_fft(self):
        """按当前缓冲区内容绘制一次频域图。"""
        for idx in range(len(self.series_list)):
            self._refresh_single_series(idx)

        x_axis = self.chart.axisX()
        y_axis = self.chart.axisY()

        all_freqs = []
        all_values = []
        for buf in self.buffer_list:
            freqs, magnitude = self._prepare_fft_series(buf)
            if freqs.size > 0:
                all_freqs.extend([float(v) for v in freqs])
            if magnitude.size > 0:
                all_values.extend([float(v) for v in magnitude])

        if x_axis is not None and all_freqs:
            xmin = min(all_freqs)
            xmax = max(all_freqs)
            if xmin == xmax:
                xmax = xmin + 1.0
            x_axis.setRange(xmin, xmax)

            try:
                if self.sample_rate:
                    x_axis.setTitleText('Frequency (Hz)')
                else:
                    x_axis.setTitleText('Frequency')
            except Exception:
                pass

        if y_axis is not None and all_values:
            ymin = min(all_values)
            ymax = max(all_values)
            if ymin == ymax:
                ymax = ymin + 1.0
            margin = 0.05 * max(1.0, ymax - ymin)
            y_axis.setRange(ymin - margin, ymax + margin)

            try:
                y_axis.setTitleText('Magnitude (dB)' if self.fft_db else 'Magnitude')
            except Exception:
                pass

    def add_values(self, values_list):
        for i, val in enumerate(values_list):
            if i < len(self.buffer_list):
                self.buffer_list[i].append(val)

    def add_value(self, value, series_idx=0):
        if series_idx < len(self.buffer_list):
            self.buffer_list[series_idx].append(value)

    def update_data(self, data_list):
        if not isinstance(data_list, list) or (len(data_list) > 0 and not isinstance(data_list[0], (list, tuple))):
            data_list = [data_list]

        for i, data in enumerate(data_list):
            if i < len(self.buffer_list):
                data_list_full = list(data)
                if len(data_list_full) > self.buffer_size:
                    data_list_full = data_list_full[-self.buffer_size :]
                self.buffer_list[i] = deque(data_list_full, maxlen=self.buffer_size)

    def set_silent(self, silent: bool):
        self._silent = silent
