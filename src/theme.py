"""
Coupang Partners Thread Auto - Design System
"Stitch Blue" Theme - Generated from Google Stitch AI

Centralized color palette, typography, and stylesheet constants.
"""


class Colors:
    """Color palette - Stitch Blue Dark Theme"""
    # Backgrounds (deep navy-slate gradient)
    BG_DARK = "#101622"
    BG_CARD = "#1A2233"
    BG_INPUT = "#141C2B"
    BG_ELEVATED = "#222D40"
    BG_HOVER = "#283448"
    BG_TERMINAL = "#080C14"

    # Accent (Electric Blue)
    ACCENT = "#0D59F2"
    ACCENT_LIGHT = "#3B7BFF"
    ACCENT_DARK = "#0A47C8"
    ACCENT_GLOW = "rgba(13, 89, 242, 0.15)"
    ACCENT_SHADOW = "rgba(13, 89, 242, 0.30)"

    # Semantic
    SUCCESS = "#22C55E"
    SUCCESS_BG = "rgba(34, 197, 94, 0.10)"
    WARNING = "#F59E0B"
    WARNING_BG = "rgba(245, 158, 11, 0.10)"
    ERROR = "#EF4444"
    ERROR_BG = "rgba(239, 68, 68, 0.10)"
    INFO = "#3B82F6"
    INFO_BG = "rgba(59, 130, 246, 0.10)"

    # Text (slate tones)
    TEXT_PRIMARY = "#E2E8F0"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#4A5568"
    TEXT_ACCENT = "#3B82F6"

    # Borders
    BORDER = "#2D3748"
    BORDER_LIGHT = "#374151"
    BORDER_ACTIVE = "#0D59F2"

    # Misc
    SCROLLBAR = "#2D3748"
    SCROLLBAR_HOVER = "#4A5568"
    SHADOW = "rgba(0, 0, 0, 0.5)"
    OVERLAY = "rgba(16, 22, 34, 0.90)"


class Typography:
    """Font definitions - Inter + JetBrains Mono"""
    FAMILY = "Inter, Segoe UI, Pretendard, sans-serif"
    FAMILY_MONO = "JetBrains Mono, Cascadia Code, Consolas, monospace"

    TITLE_XL = f"font-family: {FAMILY}; font-size: 20pt; font-weight: 700; letter-spacing: -0.5px;"
    TITLE_LG = f"font-family: {FAMILY}; font-size: 16pt; font-weight: 700; letter-spacing: -0.3px;"
    TITLE_MD = f"font-family: {FAMILY}; font-size: 13pt; font-weight: 600;"
    TITLE_SM = f"font-family: {FAMILY}; font-size: 11pt; font-weight: 600;"
    BODY = f"font-family: {FAMILY}; font-size: 10pt; font-weight: 400;"
    BODY_SM = f"font-family: {FAMILY}; font-size: 9pt; font-weight: 400;"
    CAPTION = f"font-family: {FAMILY}; font-size: 8pt; font-weight: 500; letter-spacing: 0.5px;"
    MONO = f"font-family: {FAMILY_MONO}; font-size: 9.5pt;"


class Radius:
    SM = "6px"
    MD = "8px"
    LG = "12px"
    XL = "16px"
    PILL = "100px"


def global_stylesheet():
    """Application-wide base stylesheet - Stitch Blue theme"""
    c = Colors
    r = Radius
    t = Typography
    return f"""
        /* ===== Base ===== */
        QMainWindow, QDialog {{
            background-color: {c.BG_DARK};
        }}
        QWidget {{
            font-family: {t.FAMILY};
            font-size: 10pt;
            color: {c.TEXT_PRIMARY};
        }}
        QLabel {{
            color: {c.TEXT_PRIMARY};
            background: transparent;
        }}
        QFrame {{
            background: transparent;
        }}

        /* ===== Scrollbar ===== */
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {c.SCROLLBAR};
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c.SCROLLBAR_HOVER};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 6px;
            margin: 2px 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c.SCROLLBAR};
            border-radius: 3px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c.SCROLLBAR_HOVER};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}

        /* ===== Text Input ===== */
        QTextEdit, QPlainTextEdit {{
            background-color: {c.BG_TERMINAL};
            border: 1px solid {c.BORDER};
            border-radius: {r.LG};
            padding: 14px;
            color: {c.TEXT_PRIMARY};
            selection-background-color: {c.ACCENT};
            selection-color: #FFFFFF;
            font-family: {t.FAMILY_MONO};
            font-size: 10pt;
        }}
        QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {c.ACCENT};
            border-width: 1.5px;
        }}
        QLineEdit {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 10px 14px;
            color: {c.TEXT_PRIMARY};
            font-size: 10pt;
        }}
        QLineEdit:focus {{
            border-color: {c.ACCENT};
            border-width: 1.5px;
        }}
        QLineEdit:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
        }}
        QLineEdit::placeholder {{
            color: {c.TEXT_MUTED};
        }}

        /* ===== Buttons ===== */
        QPushButton {{
            background-color: {c.ACCENT};
            color: #FFFFFF;
            border: none;
            border-radius: {r.MD};
            padding: 10px 28px;
            font-weight: 600;
            font-size: 10pt;
        }}
        QPushButton:hover {{
            background-color: {c.ACCENT_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {c.ACCENT_DARK};
        }}
        QPushButton:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
        }}

        /* Ghost / Secondary */
        QPushButton[class="ghost"] {{
            background-color: transparent;
            color: {c.TEXT_SECONDARY};
            border: 1px solid {c.BORDER};
        }}
        QPushButton[class="ghost"]:hover {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_PRIMARY};
            border-color: {c.BORDER_LIGHT};
        }}

        /* Outline variants */
        QPushButton[class="outline-danger"] {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1px solid {c.ERROR};
        }}
        QPushButton[class="outline-danger"]:hover {{
            background-color: {c.ERROR};
            color: #FFFFFF;
        }}

        QPushButton[class="outline-success"] {{
            background-color: transparent;
            color: {c.SUCCESS};
            border: 1px solid {c.SUCCESS};
        }}
        QPushButton[class="outline-success"]:hover {{
            background-color: {c.SUCCESS};
            color: #FFFFFF;
        }}

        /* ===== Lists ===== */
        QListWidget {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.LG};
            padding: 6px;
            color: {c.TEXT_PRIMARY};
            outline: none;
        }}
        QListWidget::item {{
            padding: 8px 12px;
            border-radius: {r.SM};
        }}
        QListWidget::item:selected {{
            background-color: {c.ACCENT_GLOW};
            color: {c.ACCENT_LIGHT};
        }}
        QListWidget::item:hover {{
            background-color: {c.BG_ELEVATED};
        }}

        /* ===== SpinBox ===== */
        QSpinBox {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 8px 10px;
            color: {c.TEXT_PRIMARY};
            font-size: 10pt;
        }}
        QSpinBox:focus {{
            border-color: {c.ACCENT};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background-color: {c.BG_ELEVATED};
            border: none;
            width: 22px;
            border-radius: 3px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {c.BG_HOVER};
        }}

        /* ===== Checkbox ===== */
        QCheckBox {{
            color: {c.TEXT_PRIMARY};
            font-size: 10pt;
            spacing: 10px;
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border: 2px solid {c.BORDER_LIGHT};
            border-radius: {r.SM};
            background-color: {c.BG_INPUT};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c.ACCENT};
            border-color: {c.ACCENT};
        }}
        QCheckBox::indicator:hover {{
            border-color: {c.ACCENT};
        }}

        /* ===== GroupBox ===== */
        QGroupBox {{
            background-color: {c.BG_CARD};
            border: 1px solid {c.BORDER};
            border-radius: {r.LG};
            margin-top: 14px;
            padding: 20px 16px 16px 16px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 2px 10px;
            color: {c.TEXT_PRIMARY};
            font-size: 10pt;
        }}

        /* ===== Splitter ===== */
        QSplitter::handle {{
            background-color: {c.BORDER};
            width: 1px;
        }}
        QSplitter::handle:hover {{
            background-color: {c.ACCENT};
        }}

        /* ===== StatusBar ===== */
        QStatusBar {{
            background-color: {c.BG_CARD};
            color: {c.TEXT_SECONDARY};
            border-top: 1px solid {c.BORDER};
            padding: 4px 16px;
            font-size: 9pt;
        }}

        /* ===== MessageBox ===== */
        QMessageBox {{
            background-color: {c.BG_CARD};
        }}
        QMessageBox QLabel {{
            color: {c.TEXT_PRIMARY};
            font-size: 10pt;
            min-width: 280px;
        }}
        QMessageBox QPushButton {{
            background-color: {c.ACCENT};
            color: white;
            border: none;
            border-radius: {r.MD};
            padding: 8px 24px;
            min-width: 80px;
            font-weight: 600;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {c.ACCENT_LIGHT};
        }}

        /* ===== ToolTip ===== */
        QToolTip {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            border-radius: {r.SM};
            padding: 8px 12px;
            font-size: 9pt;
        }}
    """
