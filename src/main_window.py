"""
Coupang Partners Threads Auto - Main Window (PyQt5)
Stitch Blue Design
"""
import re
import html
import time
import threading
import queue
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QPlainTextEdit, QListWidget, QFrame,
    QMessageBox, QSplitter, QStatusBar, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPainter, QLinearGradient

from src.config import config
from src.coupang_uploader import CoupangPartnersPipeline
from src.theme import Colors, Typography, Radius, global_stylesheet


# ─── Helpers ─────────────────────────────────────────────────

def _format_interval(seconds):
    """Format seconds into human-readable time string."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _hex_alpha(color, alpha_hex):
    """Append alpha hex suffix to a #RRGGBB color. Returns color as-is if not hex."""
    if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        return f"{color}{alpha_hex}"
    return color


# ─── Signals ────────────────────────────────────────────────

class Signals(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(str)
    results = pyqtSignal(int, int)
    product = pyqtSignal(str, bool)
    finished = pyqtSignal(dict)


# ─── Card Widget ────────────────────────────────────────────

class Card(QFrame):
    """Rounded card container with border"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(Colors.BORDER))
        painter.setBrush(QColor(Colors.BG_CARD))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)


# ─── Badge Widget ───────────────────────────────────────────

class Badge(QLabel):
    """Small pill-shaped status badge"""
    def __init__(self, text="", color=Colors.ACCENT, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(24)
        self.setMinimumWidth(52)
        self._apply(color)

    def _apply(self, color):
        bg = _hex_alpha(color, "18")
        border = _hex_alpha(color, "35")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 0 12px;
                font-size: 8pt;
                font-weight: 600;
            }}
        """)

    def update_style(self, color, text=None):
        if text:
            self.setText(text)
        self._apply(color)


# ─── Header Bar ─────────────────────────────────────────────

class HeaderBar(QFrame):
    """Top bar with gradient background"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor(Colors.BG_CARD))
        grad.setColorAt(0.5, QColor("#131A2A"))
        grad.setColorAt(1, QColor(Colors.BG_CARD))
        painter.fillRect(self.rect(), grad)
        painter.setPen(QColor(Colors.BORDER))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Main Window ────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Coupang Partners Thread Auto - Main Window"""

    MAX_LOG_LINES = 2000

    COUPANG_LINK_PATTERN = re.compile(
        r'https?://(?:link\.coupang\.com|www\.coupang\.com)[^\s<>"\']*',
        re.IGNORECASE
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coupang Partners Thread Auto")
        self.setMinimumSize(1000, 700)
        self.resize(1120, 760)

        self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)
        self._stop_event = threading.Event()
        self._stop_event.set()  # Initially not running
        self._urls_lock = threading.Lock()
        self.link_queue = queue.Queue()
        self.processed_urls = set()

        self.signals = Signals()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.results.connect(self._set_results)
        self.signals.product.connect(self._add_product)
        self.signals.finished.connect(self._on_finished)

        self._build_ui()
        self.setStyleSheet(global_stylesheet())

    @property
    def is_running(self):
        return not self._stop_event.is_set()

    @is_running.setter
    def is_running(self, value):
        if value:
            self._stop_event.clear()
        else:
            self._stop_event.set()

    # ━━━━━━━━━━━━━━━━━━━━━ UI BUILD ━━━━━━━━━━━━━━━━━━━━━

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        # Content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 10)
        content_layout.setSpacing(12)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_output_panel())
        splitter.setSizes([440, 580])
        content_layout.addWidget(splitter, 1)

        root.addWidget(content, 1)
        self._build_statusbar()

    def _build_header(self):
        header = HeaderBar()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        # Brand
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)

        brand_icon = QLabel("C")
        brand_icon.setFixedSize(34, 34)
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.ACCENT};
                color: #FFFFFF;
                border-radius: 8px;
                font-size: 15pt;
                font-weight: 700;
            }}
        """)
        brand_layout.addWidget(brand_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_label = QLabel("Coupang Partners")
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 14pt; font-weight: 700; letter-spacing: -0.3px;")
        sub_label = QLabel("Thread Auto")
        sub_label.setStyleSheet(f"color: {Colors.ACCENT}; font-size: 9pt; font-weight: 600;")
        title_col.addWidget(title_label)
        title_col.addWidget(sub_label)
        brand_layout.addLayout(title_col)
        layout.addLayout(brand_layout)

        layout.addStretch()

        # Online indicator
        online_dot = QLabel()
        online_dot.setFixedSize(8, 8)
        online_dot.setStyleSheet(f"background-color: {Colors.SUCCESS}; border-radius: 4px;")
        layout.addWidget(online_dot)

        # Status badge
        self.status_badge = Badge("Ready", Colors.SUCCESS)
        layout.addWidget(self.status_badge)

        # Settings button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(90, 34)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setProperty("class", "ghost")
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        return header

    def _build_input_panel(self):
        panel = Card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Section header
        header = QHBoxLayout()
        icon_label = QLabel("*")
        icon_label.setStyleSheet(f"color: {Colors.ACCENT}; font-size: 14pt; font-weight: 700;")
        icon_label.setFixedWidth(20)
        header.addWidget(icon_label)

        sec_label = QLabel("Start New Automation")
        sec_label.setStyleSheet(f"font-size: 12pt; font-weight: 700; color: {Colors.TEXT_PRIMARY}; letter-spacing: -0.2px;")
        header.addWidget(sec_label)
        header.addStretch()

        self.link_count_badge = Badge("0 links", Colors.TEXT_MUTED)
        header.addWidget(self.link_count_badge)
        layout.addLayout(header)

        # Hint
        hint = QLabel("Paste Coupang Partners URLs below (one per line)")
        hint.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(hint)

        # Text area (plain text to prevent rich-text paste issues)
        self.links_text = QPlainTextEdit()
        self.links_text.setPlaceholderText(
            "https://link.coupang.com/a/xxx\n"
            "https://link.coupang.com/a/yyy"
        )
        self.links_text.textChanged.connect(self._update_link_count)
        layout.addWidget(self.links_text, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.start_btn = QPushButton("Trigger Automation")
        self.start_btn.setFixedHeight(44)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                color: #FFFFFF;
                border: none;
                border-radius: {Radius.MD};
                font-size: 11pt;
                font-weight: 700;
                padding: 0 28px;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_LIGHT}; }}
            QPushButton:pressed {{ background-color: {Colors.ACCENT_DARK}; }}
            QPushButton:disabled {{ background-color: {Colors.BG_ELEVATED}; color: {Colors.TEXT_MUTED}; }}
        """)
        self.start_btn.clicked.connect(self.start_upload)
        btn_row.addWidget(self.start_btn)

        self.add_btn = QPushButton("Add Links")
        self.add_btn.setFixedHeight(44)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setEnabled(False)
        self.add_btn.setProperty("class", "outline-success")
        self.add_btn.clicked.connect(self.add_links_to_queue)
        btn_row.addWidget(self.add_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "outline-danger")
        self.stop_btn.clicked.connect(self.stop_upload)
        btn_row.addWidget(self.stop_btn)

        layout.addLayout(btn_row)
        return panel

    def _build_output_panel(self):
        panel = Card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {Colors.TEXT_MUTED};
                padding: 12px 22px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 10pt;
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                color: {Colors.TEXT_SECONDARY};
            }}
            QTabBar::tab:selected {{
                color: {Colors.ACCENT};
                border-bottom-color: {Colors.ACCENT};
            }}
        """)

        # Tab 1: Log
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(16, 10, 16, 16)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_icon = QLabel("$")
        log_icon.setStyleSheet(f"color: {Colors.ACCENT}; font-family: {Typography.FAMILY_MONO}; font-size: 12pt; font-weight: 700;")
        log_icon.setFixedWidth(18)
        log_header.addWidget(log_icon)
        log_title = QLabel("Automation Logs")
        log_title.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;")
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_layout.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(self.MAX_LOG_LINES)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_TERMINAL};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.LG};
                padding: 14px;
                color: {Colors.TEXT_SECONDARY};
                font-family: {Typography.FAMILY_MONO};
                font-size: 9pt;
            }}
        """)
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_tab, "Log")

        # Tab 2: Results
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setContentsMargins(16, 10, 16, 16)
        result_layout.setSpacing(12)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        self.stat_success, self._stat_success_val = self._build_stat_card("Success", "0", Colors.SUCCESS)
        self.stat_failed, self._stat_failed_val = self._build_stat_card("Failed", "0", Colors.ERROR)
        self.stat_total, self._stat_total_val = self._build_stat_card("Total", "0", Colors.INFO)
        stats_row.addWidget(self.stat_success)
        stats_row.addWidget(self.stat_failed)
        stats_row.addWidget(self.stat_total)
        result_layout.addLayout(stats_row)

        # Product list
        list_header = QHBoxLayout()
        list_label = QLabel("Processed Items")
        list_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9pt; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;")
        list_header.addWidget(list_label)
        list_header.addStretch()
        result_layout.addLayout(list_header)

        self.products_list = QListWidget()
        self.products_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG_INPUT};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.LG};
                padding: 6px;
                font-size: 9pt;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: {Radius.SM};
                border-bottom: 1px solid {Colors.BORDER};
            }}
            QListWidget::item:last-child {{
                border-bottom: none;
            }}
        """)
        result_layout.addWidget(self.products_list, 1)
        self.tabs.addTab(result_tab, "Results")

        layout.addWidget(self.tabs)
        return panel

    def _build_stat_card(self, label, value, color):
        card = QFrame()
        bg_color = _hex_alpha(color, "0D")
        border_color = _hex_alpha(color, "25")
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {Radius.LG};
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        val_label = QLabel(value)
        val_label.setAlignment(Qt.AlignCenter)
        val_label.setStyleSheet(f"color: {color}; font-size: 22pt; font-weight: 700; background: transparent; border: none;")
        layout.addWidget(val_label)

        name_label = QLabel(label.upper())
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 8pt; font-weight: 600; letter-spacing: 1px; background: transparent; border: none;")
        layout.addWidget(name_label)

        return card, val_label

    def _build_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_label = QLabel("System Online")
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 9pt;")
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 9pt;")
        self.statusbar.addWidget(self.status_label, 1)
        self.statusbar.addPermanentWidget(self.progress_label)

    # ━━━━━━━━━━━━━━━━━━━━━ SLOTS ━━━━━━━━━━━━━━━━━━━━━

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_msg = html.escape(message)
        color = Colors.TEXT_SECONDARY
        if "Error" in message or "failed" in message.lower() or "error" in message.lower():
            color = Colors.ERROR
        elif "success" in message.lower():
            color = Colors.SUCCESS
        elif "===" in message:
            color = Colors.ACCENT
        self.log_text.append(
            f'<span style="color:{Colors.TEXT_MUTED}">[{timestamp}]</span> '
            f'<span style="color:{color}">{safe_msg}</span>'
        )

    def _set_status(self, message):
        self.status_label.setText(message)
        if "error" in message.lower() or "cancel" in message.lower():
            self.status_badge.update_style(Colors.ERROR, message[:14])
        elif "complete" in message.lower() or "done" in message.lower():
            self.status_badge.update_style(Colors.SUCCESS, message[:14])
        else:
            self.status_badge.update_style(Colors.WARNING, message[:14])

    def _set_progress(self, message):
        self.progress_label.setText(message)

    def _set_results(self, success, failed):
        total = success + failed
        self._stat_success_val.setText(str(success))
        self._stat_failed_val.setText(str(failed))
        self._stat_total_val.setText(str(total))

    def _add_product(self, title, success):
        icon = "\u2714" if success else "\u2718"
        color = Colors.SUCCESS if success else Colors.ERROR
        item_text = f"  {icon}  {title[:55]}"
        self.products_list.addItem(item_text)
        item = self.products_list.item(self.products_list.count() - 1)
        item.setForeground(QColor(color))

    def _on_finished(self, results):
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_badge.update_style(Colors.SUCCESS, "Ready")

        while not self.link_queue.empty():
            try:
                self.link_queue.get_nowait()
            except queue.Empty:
                break

        parse_failed = results.get('parse_failed', 0)
        if results.get('cancelled'):
            msg = (f"Upload cancelled.\n\n"
                   f"  Completed: {results.get('uploaded', 0)}\n"
                   f"  Failed: {results.get('failed', 0)}")
            if parse_failed > 0:
                msg += f"\n  Parse errors: {parse_failed}"
            QMessageBox.information(self, "Cancelled", msg)
        else:
            msg = (f"Upload finished.\n\n"
                   f"  Success: {results.get('uploaded', 0)}\n"
                   f"  Failed: {results.get('failed', 0)}")
            if parse_failed > 0:
                msg += f"\n  Parse errors: {parse_failed}"
            QMessageBox.information(self, "Complete", msg)

    def _update_link_count(self):
        content = self.links_text.toPlainText()
        links = self.COUPANG_LINK_PATTERN.findall(content)
        unique_links = list(dict.fromkeys(links))
        count = len(unique_links)
        if count > 0:
            self.link_count_badge.update_style(Colors.ACCENT, f"{count} links")
        else:
            self.link_count_badge.update_style(Colors.TEXT_MUTED, "0 links")

    def _extract_links(self, content: str) -> list:
        links = self.COUPANG_LINK_PATTERN.findall(content)
        unique_links = list(dict.fromkeys(links))
        return [(url, None) for url in unique_links]

    # ━━━━━━━━━━━━━━━━━━━━━ ACTIONS ━━━━━━━━━━━━━━━━━━━━━

    @staticmethod
    def _sanitize_profile_name(username):
        """Sanitize username for use as profile directory name."""
        name = username.split('@')[0] if '@' in username else username
        return re.sub(r'[^\w\-.]', '_', name)

    def open_settings(self):
        from src.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.pipeline = CoupangPartnersPipeline(config.gemini_api_key)

    def start_upload(self):
        content = self.links_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Notice", "Please enter Coupang Partners links.")
            return

        api_key = config.gemini_api_key
        if not api_key or len(api_key.strip()) < 10:
            QMessageBox.critical(self, "Setup Required", "Please set a valid Gemini API key in Settings.")
            return

        link_data = self._extract_links(content)

        if not link_data:
            QMessageBox.warning(self, "Notice", "No valid Coupang links found.")
            return

        config.load()
        interval = max(config.upload_interval, 30)

        reply = QMessageBox.question(
            self, "Confirm",
            f"Process {len(link_data)} link(s) and upload?\n"
            f"Upload interval: {_format_interval(interval)}\n\n"
            f"(You can add more links while running)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.products_list.clear()
        self.status_badge.update_style(Colors.WARNING, "Running")

        # Reset stats
        self._stat_success_val.setText("0")
        self._stat_failed_val.setText("0")
        self._stat_total_val.setText("0")

        with self._urls_lock:
            self.processed_urls.clear()
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)

        clean_links = "\n".join([item[0] for item in link_data])
        self.links_text.setPlainText(clean_links)

        thread = threading.Thread(
            target=self._run_upload_queue,
            args=(interval,),
            daemon=True
        )
        thread.start()

    def add_links_to_queue(self):
        content = self.links_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Notice", "Please enter links to add.")
            return

        link_data = self._extract_links(content)

        if not link_data:
            QMessageBox.warning(self, "Notice", "No valid Coupang links found.")
            return

        added = 0
        with self._urls_lock:
            for item in link_data:
                url = item[0]
                if url not in self.processed_urls:
                    self.link_queue.put(item)
                    self.processed_urls.add(url)
                    added += 1

        if added > 0:
            self.signals.log.emit(f"Added {added} new link(s) (queue: {self.link_queue.qsize()})")
            clean_links = "\n".join([item[0] for item in link_data])
            self.links_text.setPlainText(clean_links)
        else:
            QMessageBox.information(self, "Notice", "All links are already queued or processed.")

    def _run_upload_queue(self, interval):
        from src.computer_use_agent import ComputerUseAgent
        from src.threads_playwright_helper import ThreadsPlaywrightHelper

        results = {
            'total': 0,
            'processed': 0,
            'parse_failed': 0,
            'uploaded': 0,
            'failed': 0,
            'cancelled': False,
            'details': []
        }

        def log(msg):
            self.signals.log.emit(msg)
            self.signals.progress.emit(msg)

        try:
            log(f"Upload started (queue: {self.link_queue.qsize()})")
            self.signals.status.emit("Processing...")

            ig_username = config.instagram_username
            if ig_username:
                profile_name = self._sanitize_profile_name(ig_username)
                profile_dir = f".threads_profile_{profile_name}"
            else:
                profile_dir = ".threads_profile"

            log(f"Starting browser (profile: {profile_dir})")
            agent = ComputerUseAgent(
                api_key=config.gemini_api_key,
                headless=False,
                profile_dir=profile_dir
            )
            agent.start_browser()

            try:
                agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
            except Exception:
                pass

            helper = ThreadsPlaywrightHelper(agent.page)

            if not helper.check_login_status():
                log("Login required - please log in via browser (60s timeout)")
                for wait_sec in range(20):
                    time.sleep(3)
                    remaining = 60 - (wait_sec * 3)
                    if wait_sec % 3 == 0:
                        log(f"Waiting for login... ~{remaining}s remaining")
                    if helper.check_login_status():
                        log("Login confirmed!")
                        break
                else:
                    log("Login failed - timed out after 60s")
                    results['cancelled'] = True
                    self.signals.finished.emit(results)
                    return

            log("Threads login verified")

            processed_count = 0
            empty_count = 0

            while not self._stop_event.is_set():
                try:
                    item = self.link_queue.get(timeout=5)
                    empty_count = 0
                except queue.Empty:
                    empty_count += 1
                    if empty_count >= 6:
                        log("Queue empty. Finishing.")
                        break
                    log("Waiting for new links...")
                    continue

                if self._stop_event.is_set():
                    results['cancelled'] = True
                    break

                processed_count += 1
                url, keyword = item if isinstance(item, tuple) else (item, None)
                results['total'] += 1

                log(f"===== Item {processed_count} (queue: {self.link_queue.qsize()}) =====")

                log("Analyzing product...")
                try:
                    post_data = self.pipeline.process_link(url, user_keywords=keyword)
                    if not post_data:
                        results['parse_failed'] += 1
                        log("Parse failed - skipping")
                        continue

                    results['processed'] += 1
                    product_name = post_data.get('product_title', '')[:30]
                    log(f"Parsed: {product_name}")

                except Exception as e:
                    results['parse_failed'] += 1
                    log(f"Parse error: {str(e)[:50]}")
                    continue

                log("Uploading to Threads...")
                try:
                    agent.page.goto("https://www.threads.net", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(2)

                    posts_data = [
                        {'text': post_data['first_post']['text'], 'image_path': post_data['first_post'].get('media_path')},
                        {'text': post_data['second_post']['text'], 'image_path': None}
                    ]

                    success = helper.create_thread_direct(posts_data)

                    if success:
                        results['uploaded'] += 1
                        log(f"Upload success: {product_name}")
                        self.signals.product.emit(product_name, True)
                    else:
                        results['failed'] += 1
                        log(f"Upload failed: {product_name}")
                        self.signals.product.emit(product_name, False)

                    results['details'].append({
                        'product_title': product_name,
                        'url': url,
                        'success': success
                    })

                except Exception as e:
                    results['failed'] += 1
                    log(f"Upload error: {str(e)[:50]}")
                    self.signals.product.emit(product_name, False)

                self.signals.results.emit(results['uploaded'], results['failed'])

                if not self._stop_event.is_set():
                    log(f"Waiting {_format_interval(interval)} before next item...")

                    for sec in range(interval):
                        if self._stop_event.is_set():
                            results['cancelled'] = True
                            break
                        remaining = interval - sec
                        if remaining % 60 == 0 and remaining > 0:
                            log(f"Wait... {_format_interval(remaining)}")
                        time.sleep(1)

            try:
                agent.save_session()
                agent.close()
            except Exception:
                pass

            log("=" * 40)
            log(f"Done: success {results['uploaded']} / failed {results['failed']} / parse_err {results['parse_failed']}")

            if results['cancelled']:
                self.signals.status.emit("Cancelled")
            else:
                self.signals.status.emit("Complete")

            self.signals.finished.emit(results)

        except Exception as e:
            log(f"Fatal error: {e}")
            self.signals.status.emit("Error")
            self.signals.finished.emit(results)

    def stop_upload(self):
        if self.is_running:
            self.signals.log.emit("Stop requested... will finish current task.")
            self.signals.status.emit("Stopping...")
            self.status_badge.update_style(Colors.WARNING, "Stopping")
            self.is_running = False
            self.pipeline.cancel()
