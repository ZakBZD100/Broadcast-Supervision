import os
import sys
import ctypes
from PyQt5.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QWidget, QTextEdit, QHBoxLayout, QMessageBox, QPushButton, QSizePolicy, QSpacerItem, QFrame, QSlider, QStackedLayout, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QComboBox, QDateEdit, QGridLayout, QGroupBox
)
from PyQt5.QtGui import QPixmap, QIcon, QFont, QPalette, QColor, QLinearGradient, QBrush, QPainter, QPen, QPaintEvent, QFontDatabase, QPainterPath
from PyQt5.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QRect, QEasingCurve, QThread, pyqtSignal, QDate
from PyQt5.QtMultimedia import QSound
from stream_monitor import StreamMonitor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd
from PyQt5.QtChart import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis, QPieSeries, QLineSeries, QCategoryAxis
from PyQt5.QtGui import QLinearGradient, QColor, QBrush, QFont
from PyQt5.QtWidgets import QGraphicsSimpleTextItem
import collections
import datetime
import csv

# helper PyInstaller for resource access

def resource_path(relative_path):
    """Retourne le chemin absolu vers une ressource, compatible PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)

# force loading of VLC 64-bit DLL only on Windows
if sys.platform == "win32":
    vlc_dll_path = resource_path('libvlc.dll')
    ctypes.CDLL(vlc_dll_path)
import vlc

# utility to load SVG as QPixmap
from PyQt5.QtSvg import QSvgWidget

if getattr(sys, 'frozen', False):
    # we are in a PyInstaller executable
    os.environ['PATH'] = sys._MEIPASS + os.path.sep + os.environ['PATH']

def svg_icon(path, size=32):
    w = QSvgWidget(path)
    w.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
    image = QPixmap(size, size)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    w.renderer().render(painter)
    painter.end()
    return image

class GlassmorphismFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            GlassmorphismFrame {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 20px;
            }
        """)

class NeonButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(38)
        self.setStyleSheet("""
            NeonButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 rgba(255, 0, 60, 0.8), 
                    stop:1 rgba(255, 0, 60, 0.6));
                color: white;
                border: 2px solid rgba(255, 0, 60, 0.8);
                border-radius: 12px;
                font-size: 15px;
                font-weight: 700;
                padding: 8px 24px 6px 24px;
            }
            NeonButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 rgba(255, 0, 60, 1), 
                    stop:1 rgba(255, 0, 60, 0.8));
                box-shadow: 0 0 15px rgba(255, 0, 60, 0.6);
            }
            NeonButton:pressed {
                background: rgba(35, 41, 70, 0.9);
                box-shadow: 0 0 10px rgba(255, 0, 60, 0.4);
            }
        """)

class StatusIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            StatusIndicator {
                border-radius: 10px;
                background: #4CAF50;
                border: 2px solid #4CAF50;
            }
        """)
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(1000)
        self.animation.setLoopCount(-1)
        
    def set_status(self, status):
        if status == "NONE":
            if self.animation.state() == QPropertyAnimation.Running:
                self.animation.stop()
            self.setStyleSheet(f"""
            StatusIndicator {{
                border-radius: 10px;
                background: #607D8B;
                border: 2px solid #607D8B;
            }}
            """)
            return

        color_map = {
            "OK": "#4CAF50",
            "LAG": "#FFC107", 
            "BLACK SCREEN": "#F44336",
            "ERROR": "#9C27B0"
        }
        color = color_map.get(status, "#607D8B")
        self.setStyleSheet(f"""
            StatusIndicator {{
                border-radius: 10px;
                background: {color};
                border: 2px solid {color};
                box-shadow: 0 0 10px {color};
            }}
        """)
        
        # pulse animation
        rect = self.geometry()
        if self.animation.state() == QPropertyAnimation.Running:
            self.animation.stop()
        self.animation.setStartValue(rect)
        self.animation.setEndValue(rect.adjusted(2, 2, -2, -2))
        self.animation.start()

class IncidentTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Timestamp", "Type", "Durée", "Actions"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setStyleSheet("""
            QTableWidget {
                background: #111;
                border: 1px solid #ff003c;
                border-radius: 15px;
                gridline-color: #222;
                color: white;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #222;
            }
            QTableWidget::item:selected {
                background: #ff003c;
                color: #fff;
            }
            QHeaderView::section {
                background: #ff003c;
                color: white;
                padding: 10px;
                border: none;
                font-weight: 700;
                font-size: 15px;
            }
        """)

class VideoWidget16_9(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def heightForWidth(self, width):
        return int(width * 9 / 16)

    def sizeHint(self):
        w = 1280
        return QSize(w, self.heightForWidth(w))

    def hasHeightForWidth(self):
        return True

class AspectRatioVideoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.bottom_padding = 120  # space in pixels to leave at bottom (increased)

    def resizeEvent(self, event):
        parent_w = self.parent().width() if self.parent() else self.width()
        parent_h = self.parent().height() if self.parent() else self.height()
        # 16:9 ratio
        target_w = parent_w
        target_h = int(target_w * 9 / 16)
        if target_h + self.bottom_padding > parent_h:
            target_h = parent_h - self.bottom_padding
            target_w = int(target_h * 16 / 9)
        # center widget in parent, with space at bottom
        x = (parent_w - target_w) // 2
        y = (parent_h - self.bottom_padding - target_h) // 2
        self.setGeometry(x, y, target_w, target_h)
        super().resizeEvent(event)

class MainWindow(QMainWindow):
    def __init__(self, channels):
        super().__init__()
        self.all_channels = channels
        self.monitors = {} # dictionary to store monitors for each channel
        self.active_monitor = None # currently active monitor
        
        self.setWindowTitle("Supervision")
        self.setMinimumSize(640, 480)  # default size larger
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0a0a0a,
                    stop:0.3 #1a1a2e,
                    stop:0.7 #2d1b3d,
                    stop:1 #0f0f0f);
            }
        """)
        
        # application icon
        favicon_path = resource_path(os.path.join("assets", "Favicone", "favicon.ico"))
        if os.path.exists(favicon_path):
            self.setWindowIcon(QIcon(favicon_path))
            
        self.init_ui()
        self.setup_channels()
        if self.all_channels:
            self.on_channel_selected(0)

    def init_ui(self):
        # single video widget and single player
        self.vlc_video_widget = QWidget()
        self.vlc_video_widget.setStyleSheet("background: #000; border-radius: 10px; border: 2px solid #c2185b;")
        self.vlc_video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # placeholder layouts for each tab
        self.live_video_layout = None
        self.vlc_video_widget_mini_placeholder = QVBoxLayout()
        self.vlc_video_widget_logs_placeholder = QVBoxLayout()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # futuristic header
        header_frame = GlassmorphismFrame()
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        # dynamic logo and title
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.logo_label)
        
        self.title_label = QLabel("SUPERVISION")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            font-size: 38px;
            font-weight: 900;
            color: #fff;
            letter-spacing: 2.5px;
        """)
        header_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("Système de Détection - Temps Réel")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            font-size: 18px;
            color: #e0e0e0;
            font-weight: 400;
            letter-spacing: 1.2px;
        """)
        header_layout.addWidget(self.subtitle_label)
        
        main_layout.addWidget(header_frame, alignment=Qt.AlignHCenter)
        
        # channel selector
        channel_selector_frame = GlassmorphismFrame()
        channel_selector_layout = QHBoxLayout(channel_selector_frame)
        channel_selector_layout.setContentsMargins(24, 8, 24, 8)
        channel_selector_layout.setSpacing(15)

        channel_label = QLabel("CHAÎNE:")
        channel_label.setStyleSheet("""
            color: #e0e0e0;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 1px;
            padding-right: 5px;
        """)
        channel_selector_layout.addWidget(channel_label)
        
        self.channel_combo = QComboBox()
        self.channel_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d1b3d;
                color: white;
                border: 2px solid #c2185b;
                border-radius: 15px;
                padding: 10px 30px; /* Increased horizontal padding */
                font-size: 16px;
                font-weight: 700;
                letter-spacing: 1px;
                min-width: 200px; /* Added minimum width */
            }
            QComboBox:hover {
                background-color: #3c2a4d;
                border: 2px solid #ff003c;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left-width: 2px;
                border-left-color: #c2185b;
                border-left-style: solid;
                border-top-right-radius: 15px;
                border-bottom-right-radius: 15px;
            }
            QComboBox::down-arrow {
                width: 16px; /* Increased size */
                height: 16px; /* Increased size */
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a2e;
                color: white;
                selection-background-color: #c2185b;
                border: 2px solid #c2185b;
                border-radius: 10px;
                padding: 8px;
                font-size: 16px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 35px;
            }
        """)
        self.channel_combo.currentIndexChanged.connect(self.on_channel_selected)
        channel_selector_layout.addWidget(self.channel_combo)
        
        add_channel_button = NeonButton("Ajouter Chaîne")
        add_channel_button.clicked.connect(self.add_channel)
        channel_selector_layout.addWidget(add_channel_button)
        
        delete_channel_button = NeonButton("Supprimer Chaîne")
        delete_channel_button.clicked.connect(self.delete_channel)
        channel_selector_layout.addWidget(delete_channel_button)
        
        main_layout.addWidget(channel_selector_frame, alignment=Qt.AlignHCenter)
        
        # status controls
        status_frame = GlassmorphismFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(24, 8, 24, 8)
        status_layout.setSpacing(18)
        
        # status indicator
        self.status_indicator = StatusIndicator()
        status_layout.addWidget(self.status_indicator)
        
        # status label
        self.status_label = QLabel("Statut: Initialisation...")
        self.status_label.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #fff;
            padding: 6px 18px;
            letter-spacing: 1px;
        """)
        status_layout.addWidget(self.status_label)
        
        # restart button
        self.restart_button = NeonButton("Relancer le Flux")
        self.restart_button.setMinimumHeight(38)
        self.restart_button.setMaximumWidth(260)
        self.restart_button.clicked.connect(self.restart_stream)
        status_layout.addWidget(self.restart_button)

        # export button
        self.export_button = NeonButton("Exporter CSV")
        self.export_button.setMinimumHeight(38)
        self.export_button.setMaximumWidth(260)
        self.export_button.clicked.connect(self.export_incidents)
        status_layout.addWidget(self.export_button)

        # incident simulation button
        self.simulate_incident_button = NeonButton("Simuler Incident")
        self.simulate_incident_button.setMinimumHeight(38)
        self.simulate_incident_button.setMaximumWidth(260)
        self.simulate_incident_button.clicked.connect(self.simulate_incident)
        status_layout.addWidget(self.simulate_incident_button)
        
        main_layout.addWidget(status_frame, alignment=Qt.AlignHCenter)
        
        # content area with tabs
        content_frame = GlassmorphismFrame()
        content_layout = QVBoxLayout(content_frame)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: #1a1a2e;
                color: #fff;
                padding: 10px 40px 8px 40px;
                margin-right: 8px;
                border-radius: 10px;
                font-weight: 700;
                min-width: 180px;
                font-size: 15px;
                letter-spacing: 1px;
                border: 2px solid #2d1b3d;
            }
            QTabBar::tab:selected {
                background: #c2185b;
                color: #fff;
                border: 2px solid #c2185b;
            }
            QTabBar::tab:hover {
                background: #2d1b3d;
                color: #fff;
            }
        """)
        
        # live tab
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        
        # video frame
        video_frame = GlassmorphismFrame()
        video_layout = QVBoxLayout(video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)
        self.live_video_layout = video_layout

        video_layout.addWidget(self.vlc_video_widget)
        live_layout.addWidget(video_frame, stretch=1)
        self.tab_widget.addTab(live_tab, "Live")
        
        # incidents tab with mini video
        incidents_tab = QWidget()
        incidents_layout = QVBoxLayout(incidents_tab)
        
        # horizontal layout for incidents + mini video
        incidents_horizontal = QHBoxLayout()
        
        # incidents section (left)
        incidents_left = QVBoxLayout()
        
        # incidents table
        self.incidents_table = IncidentTable()
        incidents_left.addWidget(self.incidents_table)

        # search filters
        filter_layout = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDisplayFormat('yyyy-MM-dd')
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.setStyleSheet('color: white; background: #222; border-radius: 8px; padding: 4px 12px;')
        date_label = QLabel('Date :')
        date_label.setStyleSheet('color: white; font-weight: 600;')
        filter_layout.addWidget(date_label)
        filter_layout.addWidget(self.date_filter)
        self.type_filter = QComboBox()
        self.type_filter.addItem('Tous')
        self.type_filter.addItems(['BLACK SCREEN', 'LAG', 'ERROR', 'SILENCE AUDIO'])
        self.type_filter.setStyleSheet('color: white; background: #222; border-radius: 8px; padding: 4px 12px;')
        type_label = QLabel('Type :')
        type_label.setStyleSheet('color: white; font-weight: 600;')
        filter_layout.addWidget(type_label)
        filter_layout.addWidget(self.type_filter)
        filter_btn = NeonButton('Filtrer')
        filter_btn.clicked.connect(self.apply_filters)
        filter_layout.addWidget(filter_btn)
        export_filtered_btn = NeonButton('Exporter Filtré')
        export_filtered_btn.clicked.connect(self.export_filtered_incidents)
        filter_layout.addWidget(export_filtered_btn)
        # remove 'Diagnose' button in incident filters
        # (on ne l'ajoute plus)
        filter_layout.addStretch()
        incidents_left.addLayout(filter_layout)
        
        # action buttons
        actions_layout = QHBoxLayout()
        
        refresh_btn = NeonButton("Actualiser")
        refresh_btn.clicked.connect(self.refresh_incidents)
        actions_layout.addWidget(refresh_btn)
        
        clear_btn = NeonButton("Effacer")
        clear_btn.clicked.connect(self.clear_incidents)
        actions_layout.addWidget(clear_btn)
        
        delete_btn = NeonButton("Supprimer l'incident sélectionné")
        delete_btn.clicked.connect(self.delete_selected_incident)
        actions_layout.addWidget(delete_btn)
        actions_layout.addStretch()
        incidents_left.addLayout(actions_layout)
        
        incidents_horizontal.addLayout(incidents_left, stretch=7)
        
        # mini video (right)
        video_mini_frame = GlassmorphismFrame()
        video_mini_frame.setFixedSize(300, 200)
        video_mini_layout = QVBoxLayout(video_mini_frame)
        
        mini_title = QLabel("Live Mini")
        mini_title.setAlignment(Qt.AlignCenter)
        mini_title.setStyleSheet("color: white; font-weight: 600; font-size: 14px; margin-bottom: 5px;")
        video_mini_layout.addWidget(mini_title)
        
        # add shared video widget (will be moved dynamically)
        video_mini_layout.addLayout(self.vlc_video_widget_mini_placeholder)
        
        incidents_horizontal.addWidget(video_mini_frame, stretch=3)
        incidents_layout.addLayout(incidents_horizontal)
        
        self.tab_widget.addTab(incidents_tab, "Incidents")
        
        # logs tab with mini video
        logs_tab = QWidget()
        logs_layout = QVBoxLayout(logs_tab)
        
        # horizontal layout for logs + mini video
        logs_horizontal = QHBoxLayout()
        
        # logs section (left)
        logs_left = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 15px;
                color: white;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                padding: 15px;
            }
        """)
        logs_left.addWidget(self.log_text)
        
        logs_horizontal.addLayout(logs_left, stretch=7)
        
        # mini video (right) - same as for incidents
        logs_video_mini_frame = GlassmorphismFrame()
        logs_video_mini_frame.setFixedSize(300, 200)
        logs_video_mini_layout = QVBoxLayout(logs_video_mini_frame)
        
        logs_mini_title = QLabel("Live Mini")
        logs_mini_title.setAlignment(Qt.AlignCenter)
        logs_mini_title.setStyleSheet("color: white; font-weight: 600; font-size: 14px; margin-bottom: 5px;")
        logs_video_mini_layout.addWidget(logs_mini_title)
        
        # Ajout du widget vidéo partagé (sera déplacé dynamiquement)
        logs_video_mini_layout.addLayout(self.vlc_video_widget_logs_placeholder)
        
        logs_horizontal.addWidget(logs_video_mini_frame, stretch=3)
        logs_layout.addLayout(logs_horizontal)
        
        self.tab_widget.addTab(logs_tab, "Logs Temps Réel")
        
        # add futuristic statistics tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        # prepare QChartView for statistics tab
        self.stats_chartview1 = QChartView()
        self.stats_chartview3 = QChartView()
        self.stats_chartview4 = QChartView()
        for cv in [self.stats_chartview1, self.stats_chartview3, self.stats_chartview4]:
            cv.setRenderHint(QPainter.Antialiasing)
            cv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # styled GroupBox for each graph
        self.stats_box1 = QGroupBox("Incidents par type")
        self.stats_box3 = QGroupBox("Disponibilité du flux")
        self.stats_box4 = QGroupBox("Incidents par heure (dernière journée)")
        for box, chartview in zip([self.stats_box1, self.stats_box3, self.stats_box4], [self.stats_chartview1, self.stats_chartview3, self.stats_chartview4]):
            box.setStyleSheet("""
                QGroupBox {
                    background: #181824;
                    border: 2px solid #ff003c;
                    border-radius: 18px;
                    margin-top: 18px;
                    font-size: 18px;
                    font-weight: bold;
                    color: #ff003c;
                    padding: 12px;
                }
                QGroupBox:title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 8px;
                }
            """)
            # initialize each QChartView with a default QChart
            chart = QChart()
            chart.setBackgroundBrush(QBrush(QColor(24, 24, 36)))
            chart.setTitle("Aucune donnée d'incident")
            chart.setTitleBrush(QBrush(QColor(255, 0, 60)))
            chartview.setChart(chart)
        l1 = QVBoxLayout(); l1.addWidget(self.stats_chartview1)
        l3 = QVBoxLayout(); l3.addWidget(self.stats_chartview3)
        l4 = QVBoxLayout(); l4.addWidget(self.stats_chartview4)
        self.stats_box1.setLayout(l1)
        self.stats_box3.setLayout(l3)
        self.stats_box4.setLayout(l4)
        # remove AI summary in statistics
        # grid layout for graphs
        stats_tab = QWidget()
        stats_grid = QGridLayout(stats_tab)
        stats_grid.setSpacing(24)
        stats_grid.setContentsMargins(24, 24, 24, 24)
        stats_grid.addWidget(self.stats_box1, 0, 0)
        stats_grid.addWidget(self.stats_box3, 0, 1)
        stats_grid.addWidget(self.stats_box4, 1, 0, 1, 2)
        self.tab_widget.addTab(stats_tab, "Statistiques")
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        content_layout.addWidget(self.tab_widget)
        main_layout.addWidget(content_frame)
        
        # fixed video controls under tabs (always visible)
        controls_frame = GlassmorphismFrame()
        controls_layout = QHBoxLayout(controls_frame)
        self.play_pause_btn = QPushButton("⏸")
        self.play_pause_btn.setFixedSize(40, 40)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 0, 60, 0.8);
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 0, 60, 1);
                box-shadow: 0 0 15px rgba(255, 0, 60, 0.6);
            }
        """)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_pause_btn)
        self.vol_label = QLabel("🔊")
        self.vol_label.setStyleSheet("color: white; font-size: 16px;")
        controls_layout.addWidget(self.vol_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(255, 0, 60, 1);
                border: none;
                width: 16px;
                height: 16px;
                border-radius: 8px;
                margin: -5px 0;
            }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addStretch()
        main_layout.addWidget(controls_frame)
        
        # connect tab change
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # VLC initialization
        self.init_vlc_player()

    def setup_channels(self):
        from stream_monitor import StreamMonitor # import here to avoid circular dependency
        self.channel_combo.blockSignals(True) # block signals during population
        self.channel_combo.clear()
        
        # sort channels alphabetically
        self.all_channels.sort(key=lambda x: x["name"].lower())

        for i, channel in enumerate(self.all_channels):
            self.channel_combo.addItem(channel["name"])
            # create a new StreamMonitor for each channel
            self.monitors[channel["name"]] = StreamMonitor(channel["url"], channel["db_name"], channel["name"])
        
        if self.all_channels:
                        self.channel_combo.setCurrentIndex(0) # set index after population
        self.channel_combo.blockSignals(False) # unblock signals

    def on_channel_selected(self, index):
        try:
            if index < 0 or index >= len(self.all_channels):
                return

            # stop previous channel's monitor and VLC player
            if self.active_monitor:
                try:
                    self.active_monitor.status_signal.disconnect(self.update_status)
                    self.active_monitor.log_signal.disconnect(self.append_log)
                except TypeError:
                    pass # signal was not connected
                self.active_monitor.stop()

            if hasattr(self, 'player') and self.player:
                self.player.stop()

            self.current_channel_index = index
            selected_channel_name = self.channel_combo.itemText(index)
            if not selected_channel_name:
                return

            # safe monitor retrieval
            self.active_monitor = self.monitors.get(selected_channel_name)
            if not self.active_monitor:
                self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur: Moniteur non trouvé pour {selected_channel_name}</span>")
                return
            
            # update interface display
            self.update_channel_display(selected_channel_name)
            
            # connect signals and start new monitor
            self.active_monitor.status_signal.connect(self.update_status)
            self.active_monitor.log_signal.connect(self.append_log)
            self.active_monitor.start()
            
            # start VLC player for new channel
            if hasattr(self, 'player') and self.player:
                media = self.instance.media_new(self.active_monitor.stream_url)
                self.player.set_media(media)
                self.player.play()
            
            # load incidents and update statistics for new channel
            self.load_incidents()
            self.update_stats_tab()
            self.log_text.clear() # clear previous logs
            self.append_log(f"<span style='color:#4ecdc4'>Supervision démarrée pour : {selected_channel_name}</span>")
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur critique lors de la sélection de la chaîne : {e}</span>")
            import traceback
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())

    def update_channel_display(self, channel_name):
        self.setWindowTitle(f"Supervision {channel_name}")
        self.title_label.setText(f"SUPERVISION {channel_name.upper()}")

        self.tab_widget.setTabText(0, f"Live {channel_name}")

    def clear_ui_for_no_channel(self):
        self.setWindowTitle("Supervision")
        self.title_label.setText("SUPERVISION")
        self.logo_label.clear()
        self.status_indicator.set_status("NONE")
        self.status_label.setText("Statut: Aucune chaîne")
        self.log_text.clear()
        self.incidents_table.setRowCount(0)
        self.update_stats_tab() # will display empty graphs
        if hasattr(self, 'player') and self.player:
            self.player.stop()
        self.active_monitor = None

    def add_channel(self):
        from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter une nouvelle chaîne")
        
        layout = QFormLayout(dialog)
        
        name_input = QLineEdit(dialog)
        name_input.setPlaceholderText("Nom de la chaîne (ex: Ma Chaîne TV)")
        layout.addRow("Nom de la chaîne:", name_input)
        
        url_input = QLineEdit(dialog)
        url_input.setPlaceholderText("M3U8 stream URL (ex: http://example.com/stream.m3u8)")
        layout.addRow("Stream URL:", url_input)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            channel_name = name_input.text().strip()
            channel_url = url_input.text().strip()
            
            if not channel_name or not channel_url:
                QMessageBox.warning(self, "Error", "Channel name and URL cannot be empty.")
                return
            
            # check if channel already exists
            for channel in self.all_channels:
                if channel["name"].lower() == channel_name.lower():
                    QMessageBox.warning(self, "Error", f"Channel '{channel_name}' already exists.")
                    return
            
            # generate unique database filename
            db_name = f"incidents_{channel_name.lower().replace(' ', '_')}.db"
            
            new_channel = {
                "name": channel_name,
                "url": channel_url,
                "db_name": db_name
            }
            
            self.all_channels.append(new_channel)
            
            # save updated channels
            from main import save_channels # import here to avoid circular dependency
            save_channels(self.all_channels)
            
            # update ComboBox and monitors
            self.setup_channels()
            self.channel_combo.setCurrentText(channel_name) # select new channel
            
            self.append_log(f"<span style='color:#4CAF50'>Channel '{channel_name}' added successfully.</span>")

    def delete_channel(self):
        from main import save_channels # Import here to avoid circular dependency
        
        current_channel_name = self.channel_combo.currentText()
        
        if not current_channel_name:
            QMessageBox.warning(self, "Warning", "No channel selected.")
            return

        reply = QMessageBox.question(self, "Delete Confirmation", 
                                     f"Do you really want to delete channel '{current_channel_name}' and all its data (incidents, logs)?\nThis action is irreversible.",
                                     QMessageBox.Yes | QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            channel_to_delete = None
            for channel in self.all_channels:
                if channel["name"] == current_channel_name:
                    channel_to_delete = channel
                    break
            
            if channel_to_delete:
                # delete database files
                data_dir = os.path.join(os.getcwd(), "data")
                db_path = os.path.join(data_dir, channel_to_delete["db_name"])
                csv_path = os.path.join(data_dir, channel_to_delete["db_name"].replace(".db", ".csv"))
                
                if os.path.exists(db_path):
                    os.remove(db_path)
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                
                # delete associated monitor
                if current_channel_name in self.monitors:
                    self.monitors[current_channel_name].stop()
                    del self.monitors[current_channel_name]
                
                # remove channel from list
                self.all_channels.remove(channel_to_delete)
                
                # save updated channels
                save_channels(self.all_channels)
                
                # update ComboBox and UI
                self.setup_channels()
                
                # if no channels remain, reset UI
                if not self.all_channels:
                    self.clear_ui_for_no_channel()
                
                self.append_log(f"<span style='color:#ff003c'>Channel '{current_channel_name}' and its data deleted.</span>")
            else:
                QMessageBox.warning(self, "Error", "Selected channel not found.")

    def init_vlc_player(self):
        try:
            vlc_plugins_path = resource_path('plugins')
            with open('vlc_debug.log', 'w', encoding='utf-8') as f:
                f.write(f'vlc_plugins_path={vlc_plugins_path}\n')
                f.write(f'PATH={os.environ["PATH"]}\n')
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            if sys.platform.startswith('linux'):
                self.player.set_xwindow(int(self.vlc_video_widget.winId()))
            elif sys.platform == "win32":
                self.player.set_hwnd(int(self.vlc_video_widget.winId()))
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.vlc_video_widget.winId()))
            self.player.play()
            self.player.audio_set_volume(self.volume_slider.value())
            import time
            time.sleep(1)
        except Exception as e:
            import traceback
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            self.log_text.append(f"<span style='color:#ff6b6b'>Erreur VLC/vidéo : {e}</span>")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Erreur VLC/vidéo")
            msg.setText(f"Impossible d'initialiser la vidéo : {e}")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.show()
            self.vlc_video_widget.setVisible(False)

    def toggle_play_pause(self):
        try:
            if hasattr(self, 'player') and self.player is not None:
                if not hasattr(self, 'is_paused'):
                    self.is_paused = False
            if self.is_paused:
                self.player.play()
                self.play_pause_btn.setText("⏸")
                self.is_paused = False
            else:
                self.player.pause()
                self.play_pause_btn.setText("▶️")
                self.is_paused = True
        except Exception as e:
            import traceback
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur pause/lecture : {e}</span>")

    def set_volume(self, value):
        try:
            if hasattr(self, 'player') and self.player is not None:
                self.player.audio_set_volume(value)
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur volume : {e}</span>")

    def update_status(self, status):
        try:
            self.status_indicator.set_status(status)
            self.status_label.setText(f"Statut: {status}")
            
            if status != "OK":
                self.add_incident(status)
                
            if status in ("LAG", "BLACK SCREEN", "ERROR") and not self.alert_shown:
                self.alert_shown = True
                self.show_alert(status)
            elif status == "OK":
                self.alert_shown = False
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur mise à jour statut : {e}</span>")

    def append_log(self, message):
        try:
            timestamp = QTimer().remainingTime()
            self.log_text.append(f"<span style='color:#4ecdc4'>[{timestamp}]</span> {message}")
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        except Exception as e:
            print(f"Log error: {e}")

    def add_incident(self, incident_type):
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            row = self.incidents_table.rowCount()
            self.incidents_table.insertRow(row)
            
            self.incidents_table.setItem(row, 0, QTableWidgetItem(timestamp))
            self.incidents_table.setItem(row, 1, QTableWidgetItem(incident_type))
            self.incidents_table.setItem(row, 2, QTableWidgetItem("En cours..."))
            self.incidents_table.setItem(row, 3, QTableWidgetItem("🔍 Surveillé"))
            
            # save incident via active monitor
            if self.active_monitor:
                self.active_monitor.add_incident(incident_type, f"Incident detected on stream {self.active_monitor.channel_name}.")
            
            self.update_stats_tab()
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur ajout incident : {e}</span>")

    def load_incidents(self):
        try:
            self.incidents_table.setRowCount(0) # clear table before reloading
            data_dir = os.path.join(os.getcwd(), "data")
            db_path = os.path.join(data_dir, self.active_monitor.db_name)
            
            if not os.path.exists(db_path):
                with open(db_path, 'w', encoding='utf-8') as f:
                    pass # create the file

            if os.path.exists(db_path):
                with open(db_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            parts = line.strip().split("|", 2)
                            if len(parts) == 3:
                                timestamp, incident_type, message = [p.strip() for p in parts]
                                
                                row = self.incidents_table.rowCount()
                                self.incidents_table.insertRow(row)
                                
                                self.incidents_table.setItem(row, 0, QTableWidgetItem(timestamp))
                                self.incidents_table.setItem(row, 1, QTableWidgetItem(incident_type))
                                self.incidents_table.setItem(row, 2, QTableWidgetItem("Terminé"))
                                self.incidents_table.setItem(row, 3, QTableWidgetItem("✅ Résolu"))
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Erreur chargement incidents : {e}</span>")

    def refresh_incidents(self):
        try:
            self.load_incidents()
            self.update_stats_tab()
            self.append_log("🔄 Incidents updated")
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Update error: {e}</span>")

    def clear_incidents(self):
        try:
            reply = QMessageBox.question(self, "Confirmation", 
                                       "Do you really want to clear all incidents for this channel?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.incidents_table.setRowCount(0)
                
                # clear active channel files
                data_dir = os.path.join(os.getcwd(), "data")
                db_path = os.path.join(data_dir, self.active_monitor.db_name)
                csv_path = os.path.join(data_dir, self.active_monitor.db_name.replace(".db", ".csv"))
                
                if os.path.exists(db_path):
                    os.remove(db_path)
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                
                self.append_log(f"🗑️ All incidents for {self.active_monitor.channel_name} have been cleared")
                self.update_stats_tab() # update stats after clearing
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Clear error: {e}</span>")

    def export_incidents(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Incidents", 
                f"incidents_{self.active_monitor.channel_name.lower().replace(' ', '_')}.csv", 
                "CSV Files (*.csv)"
            )
            
            if filename:
                data_dir = os.path.join(os.getcwd(), "data")
                csv_path = os.path.join(data_dir, self.active_monitor.db_name.replace(".db", ".csv"))
                
                if os.path.exists(csv_path):
                    import shutil
                    shutil.copy2(csv_path, filename)
                    self.append_log(f"📊 Export successful: {filename}")
                else:
                    self.append_log("<span style='color:#ff6b6b'>❌ No incidents to export for this channel</span>")
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Export error: {e}</span>")

    def restart_stream(self):
        try:
            import time
            if hasattr(self, 'player') and self.player is not None:
                try:
                    self.player.stop()
                    time.sleep(0.5)
                except Exception:
                    pass
                media = self.instance.media_new(self.active_monitor.stream_url)
                self.player.set_media(media)
                self.player.play()
                self.player.audio_set_volume(self.volume_slider.value())
            self.append_log(f"🔄 Stream restarted for {self.active_monitor.channel_name}")
        except Exception as e:
            import traceback
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            self.append_log(f"<span style='color:#ff6b6b'>❌ Stream restart error: {e}</span>")

    def show_alert(self, status):
        try:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("⚠️ Supervision Alert")
            msg.setText(f"Incident detected: {status}")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.show()
            
            # alert sound
            alert_path = os.path.join("assets", "alert.wav")
            if os.path.exists(alert_path):
                QSound.play(alert_path)
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>❌ Alert error: {e}</span>")

    def simulate_incident(self):
        """adds a fake incident for UI/logic testing."""
        self.add_incident("SIMULATION")
        self.append_log("<span style='color:#ffb300'>⚡ Simulated incident added</span>")

    def apply_filters(self):
        date_str = self.date_filter.date().toString('yyyy-MM-dd')
        type_str = self.type_filter.currentText()
        self.incidents_table.setRowCount(0)
        data_dir = os.path.join(os.getcwd(), 'data')
        db_path = os.path.join(data_dir, self.active_monitor.db_name)
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        parts = line.strip().split('|', 2)
                        if len(parts) == 3:
                            timestamp, incident_type, message = [p.strip() for p in parts]
                            if (date_str in timestamp) and (type_str == 'Tous' or type_str in incident_type):
                                row = self.incidents_table.rowCount()
                                self.incidents_table.insertRow(row)
                                self.incidents_table.setItem(row, 0, QTableWidgetItem(timestamp))
                                self.incidents_table.setItem(row, 1, QTableWidgetItem(incident_type))
                                self.incidents_table.setItem(row, 2, QTableWidgetItem('Terminé'))
                                self.incidents_table.setItem(row, 3, QTableWidgetItem('✅ Résolu'))

    def export_filtered_incidents(self):
        from PyQt5.QtWidgets import QFileDialog
        date_str = self.date_filter.date().toString('yyyy-MM-dd')
        type_str = self.type_filter.currentText()
        filename, _ = QFileDialog.getSaveFileName(self, 'Exporter incidents filtrés', f'incidents_filtres_{self.active_monitor.channel_name.lower().replace(" ", "_")}_{date_str}.csv', 'CSV Files (*.csv)')
        if filename:
            data_dir = os.path.join(os.getcwd(), 'data')
            db_path = os.path.join(data_dir, self.active_monitor.db_name)
            if os.path.exists(db_path):
                with open(db_path, 'r', encoding='utf-8') as f, open(filename, 'w', encoding='utf-8', newline='') as fout:
                    writer = csv.writer(fout)
                    writer.writerow(['Timestamp', 'Type', 'Message'])
                    for line in f:
                        if line.strip():
                            parts = line.strip().split('|', 2)
                            if len(parts) == 3:
                                timestamp, incident_type, message = [p.strip() for p in parts]
                                if (date_str in timestamp) and (type_str == 'Tous' or type_str in incident_type):
                                    writer.writerow([timestamp, incident_type, message])



    def closeEvent(self, event):
        try:
            # clean shutdown of all supervision threads
            for channel_name, monitor_instance in self.monitors.items():
                if monitor_instance:
                    try:
                        monitor_instance.stop()
                    except Exception as e:
                        self.append_log(f"<span style='color:#ff6b6b'>Error stopping monitor {channel_name}: {e}</span>")
            
            # clean shutdown of VLC player
            if hasattr(self, 'player') and self.player is not None:
                try:
                    self.player.stop()
                    self.player.release()
                except Exception as e:
                    self.append_log(f"<span style='color:#ff6b6b'>Error stopping VLC player: {e}</span>")
            event.accept()
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>General error during shutdown: {e}</span>")
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event) 

    def on_tab_changed(self, index):
        try:
            # dynamically move video widget to current tab layout
            parent = self.vlc_video_widget.parentWidget()
            if parent:
                layout = parent.layout()
                if layout:
                    layout.removeWidget(self.vlc_video_widget)
            if index == 0:  # live
                self.live_video_layout.addWidget(self.vlc_video_widget)
            elif index == 1:
                self.vlc_video_widget_mini_placeholder.addWidget(self.vlc_video_widget)
            elif index == 2:
                self.vlc_video_widget_logs_placeholder.addWidget(self.vlc_video_widget)
            # do nothing for statistics
            self.vlc_video_widget.update()
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>Tab change error (video widget move): {e}</span>") 

    def update_stats_tab(self):
        for chartview in [self.stats_chartview1, self.stats_chartview3, self.stats_chartview4]:
            chart = QChart()
            chart.setBackgroundBrush(QBrush(QColor(24, 24, 36)))
            chart.setTitle("No incident data")
            chart.setTitleBrush(QBrush(QColor(255, 0, 60)))
            chart.legend().setVisible(False)
            chartview.setChart(chart)

        if not self.active_monitor:
            return

        data_dir = os.path.join(os.getcwd(), 'data')
        db_path = os.path.join(data_dir, self.active_monitor.db_name)

        if not os.path.exists(db_path):
            return

        rows = []
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        parts = line.strip().split('|', 2)
                        if len(parts) == 3:
                            timestamp, incident_type, _ = [p.strip() for p in parts]
                            date, heure = timestamp.split(' ')
                            rows.append({'date': date, 'heure': heure, 'type': incident_type})
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>DB read error: {e}</span>")
            return

        if not rows:
            return

        # --- Chart 1: Incidents by Type (Bar Chart) ---
        chart1 = QChart()
        chart1.setAnimationOptions(QChart.SeriesAnimations)
        chart1.setBackgroundBrush(QBrush(QColor(24, 24, 36)))
        type_counts = collections.Counter([r['type'] for r in rows])
        bar_set = QBarSet("Incidents")
        bar_set.setColor(QColor(255, 0, 60))
        for t in type_counts:
            bar_set << type_counts[t]
        bar_series = QBarSeries()
        bar_series.append(bar_set)
        chart1.addSeries(bar_series)
        categories = list(type_counts.keys())
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsBrush(QBrush(QColor(255, 255, 255)))
        chart1.setAxisX(axis_x, bar_series)
        axis_y = QValueAxis()
        axis_y.setLabelsBrush(QBrush(QColor(255, 255, 255)))
        axis_y.setLabelFormat("%d")
        chart1.setAxisY(axis_y, bar_series)
        chart1.legend().setVisible(False)
        self.stats_chartview1.setChart(chart1)

        # --- Chart 3: Availability (Pie Chart) ---
        chart3 = QChart()
        chart3.setAnimationOptions(QChart.SeriesAnimations)
        chart3.setBackgroundBrush(QBrush(QColor(24, 24, 36)))
        chart3.setTitle("Availability (24h Approximation)")
        chart3.setTitleBrush(QBrush(QColor(255, 255, 255)))

        total_minutes = 24 * 60
        incident_minutes = len(rows) # approximation: 1 incident = 1 minute of unavailability
        ok_minutes = max(total_minutes - incident_minutes, 0)

        pie_series = QPieSeries()
        pie_series.setPieSize(0.8) # enlarges circle to 80% of available space
        pie_series.append(f"OK", ok_minutes).setColor(QColor(30, 200, 80))
        pie_series.append(f"Incidents", incident_minutes).setColor(QColor(255, 0, 60))
        
        pie_series.setLabelsVisible(True)
        for sl in pie_series.slices():
            sl.setLabel(f"{sl.label()} - {sl.percentage()*100:.1f}%")
            sl.setLabelBrush(QBrush(QColor(255,255,255)))

        chart3.addSeries(pie_series)
        chart3.legend().setVisible(True)
        chart3.legend().setLabelColor(QColor(255, 255, 255))
        self.stats_chartview3.setChart(chart3)

        # --- Chart 4: Incidents by Hour (Bar Chart) ---
        chart4 = QChart()
        chart4.setAnimationOptions(QChart.SeriesAnimations)
        chart4.setBackgroundBrush(QBrush(QColor(24, 24, 36)))
        last_date = sorted(rows, key=lambda x: x['date'])[-1]['date']
        hour_counts = collections.Counter([r['heure'].split(':')[0] for r in rows if r['date'] == last_date])
        bar_set_heat = QBarSet(f"Hours of {last_date}")
        bar_set_heat.setColor(QColor(255, 0, 60))
        for h in range(24):
            bar_set_heat << hour_counts.get(str(h).zfill(2), 0)
        bar_series_heat = QBarSeries()
        bar_series_heat.append(bar_set_heat)
        chart4.addSeries(bar_series_heat)
        axis_xh = QBarCategoryAxis()
        axis_xh.append([str(h) for h in range(24)])
        axis_xh.setLabelsBrush(QBrush(QColor(255, 255, 255)))
        chart4.setAxisX(axis_xh, bar_series_heat)
        axis_yh = QValueAxis()
        axis_yh.setLabelsBrush(QBrush(QColor(255, 255, 255)))
        axis_yh.setLabelFormat("%d")
        chart4.setAxisY(axis_yh, bar_series_heat)
        chart4.legend().setVisible(False)
        self.stats_chartview4.setChart(chart4) 

    def delete_selected_incident(self):
        row = self.incidents_table.currentRow()
        if row < 0:
            self.append_log("<span style='color:#ffb300'>No incident selected.</span>")
            return
        # get incident (timestamp, type, message)
        timestamp = self.incidents_table.item(row, 0).text()
        incident_type = self.incidents_table.item(row, 1).text()
        # remove from table
        self.incidents_table.removeRow(row)
        # remove from incidents.db file
        data_dir = os.path.join(os.getcwd(), "data")
        db_path = os.path.join(data_dir, self.active_monitor.db_name)
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(db_path, "w", encoding="utf-8") as f:
                for line in lines:
                    if timestamp not in line or incident_type not in line:
                        f.write(line)
        # remove from incidents.csv file
        csv_path = os.path.join(data_dir, self.active_monitor.db_name.replace(".db", ".csv"))
        if os.path.exists(csv_path):
            import csv
            rows = []
            with open(csv_path, "r", encoding="utf-8") as fin:
                reader = csv.reader(fin)
                header = next(reader, None)
                for r in reader:
                    if len(r) < 3 or r[0] != timestamp.split()[0] or r[1] != timestamp.split()[1] or r[2] != incident_type:
                        rows.append(r)
            with open(csv_path, "w", encoding="utf-8", newline='') as fout:
                writer = csv.writer(fout)
                if header:
                    writer.writerow(header)
                writer.writerows(rows)
        self.append_log(f"<span style='color:#ff003c'>Incident deleted: {timestamp} | {incident_type}</span>")
        # refresh statistics graphs
        try:
            self.update_stats_tab()
        except Exception as e:
            self.append_log(f"<span style='color:#ff6b6b'>Statistics update error: {e}</span>") 