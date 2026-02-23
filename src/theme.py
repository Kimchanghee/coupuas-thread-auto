# -*- coding: utf-8 -*-
"""
Coupang Partners Thread Auto - Design System
"Stitch Blue" Theme - Generated from Google Stitch AI

Centralized color palette, typography, spacing, shadows,
gradients, and stylesheet constants.
"""


class Colors:
    """Color palette - Stitch Blue Dark Theme"""
    # Backgrounds (deep navy-slate gradient)
    BG_DARK = "#101622"
    BG_CARD = "#1B2740"
    BG_INPUT = "#1A2332"
    BG_ELEVATED = "#222D40"
    BG_HOVER = "#283448"
    BG_TERMINAL = "#080C14"
    BG_SURFACE = "#161E2E"  # subtle card surfaces

    # Accent (Electric Blue)
    ACCENT = "#0D59F2"
    ACCENT_LIGHT = "#3B7BFF"
    ACCENT_DARK = "#0A47C8"
    ACCENT_GLOW = "rgba(13, 89, 242, 0.15)"
    ACCENT_SHADOW = "rgba(13, 89, 242, 0.30)"
    ACCENT_SUBTLE = "rgba(13, 89, 242, 0.08)"

    # Semantic
    SUCCESS = "#22C55E"
    SUCCESS_BG = "rgba(34, 197, 94, 0.10)"
    SUCCESS_BORDER = "rgba(34, 197, 94, 0.25)"
    WARNING = "#F59E0B"
    WARNING_BG = "rgba(245, 158, 11, 0.10)"
    WARNING_BORDER = "rgba(245, 158, 11, 0.25)"
    ERROR = "#EF4444"
    ERROR_BG = "rgba(239, 68, 68, 0.10)"
    ERROR_BORDER = "rgba(239, 68, 68, 0.25)"
    INFO = "#3B82F6"
    INFO_BG = "rgba(59, 130, 246, 0.10)"
    INFO_BORDER = "rgba(59, 130, 246, 0.25)"

    # Text (고대비 - 어두운 배경에서 선명하게)
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#CFD8DC"
    TEXT_MUTED = "#90A4AE"
    TEXT_PLACEHOLDER = "#6B7F8E"
    TEXT_ACCENT = "#3B82F6"
    TEXT_BRIGHT = "#FFFFFF"

    # Borders (밝은 톤 - Stitch 디자인)
    BORDER = "#3D4F6A"
    BORDER_LIGHT = "#506080"
    BORDER_ACTIVE = "#0D59F2"
    BORDER_SUBTLE = "#232D3F"

    # Misc
    SCROLLBAR = "#2D3748"
    SCROLLBAR_HOVER = "#4A5568"
    SHADOW = "rgba(0, 0, 0, 0.5)"
    OVERLAY = "rgba(16, 22, 34, 0.90)"


class Typography:
    """Font definitions - resolved at runtime by resolve_fonts()"""
    # Default fallbacks; resolve_fonts() replaces these with the best available system font.
    FAMILY = "Segoe UI"
    FAMILY_MONO = "Consolas"

    TITLE_XL = f"font-family: {FAMILY}; font-size: 24pt; font-weight: 700; letter-spacing: -0.5px;"
    TITLE_LG = f"font-family: {FAMILY}; font-size: 18pt; font-weight: 700; letter-spacing: -0.3px;"
    TITLE_MD = f"font-family: {FAMILY}; font-size: 14pt; font-weight: 600;"
    TITLE_SM = f"font-family: {FAMILY}; font-size: 12pt; font-weight: 600;"
    BODY = f"font-family: {FAMILY}; font-size: 12pt; font-weight: 400;"
    BODY_SM = f"font-family: {FAMILY}; font-size: 11pt; font-weight: 400;"
    CAPTION = f"font-family: {FAMILY}; font-size: 10pt; font-weight: 500; letter-spacing: 0.3px;"
    MONO = f"font-family: {FAMILY_MONO}; font-size: 11pt;"


class Radius:
    SM = "6px"
    MD = "8px"
    LG = "12px"
    XL = "16px"
    XXL = "20px"
    PILL = "100px"


class Spacing:
    """Consistent spacing scale (4px base)"""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24
    XXXL = 32


class Shadows:
    """Box shadow presets (CSS-like, for custom painting)"""
    # For QPainter-based shadow simulation
    CARD = (0, 2, 8, "rgba(0, 0, 0, 0.25)")
    ELEVATED = (0, 4, 16, "rgba(0, 0, 0, 0.35)")
    DROPDOWN = (0, 8, 24, "rgba(0, 0, 0, 0.45)")
    GLOW_ACCENT = (0, 0, 12, "rgba(13, 89, 242, 0.25)")
    GLOW_SUCCESS = (0, 0, 12, "rgba(34, 197, 94, 0.20)")
    GLOW_ERROR = (0, 0, 12, "rgba(239, 68, 68, 0.20)")


class Gradients:
    """QSS gradient definitions for common patterns"""
    # Button gradients
    ACCENT_BTN = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT_LIGHT})"
    )
    ACCENT_BTN_HOVER = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {Colors.ACCENT_LIGHT}, stop:1 #5B93FF)"
    )
    ACCENT_BTN_PRESSED = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {Colors.ACCENT_DARK}, stop:1 {Colors.ACCENT})"
    )

    # Header / bar gradients
    HEADER = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {Colors.BG_CARD}, stop:0.5 #131A2A, stop:1 {Colors.BG_CARD})"
    )
    HEADER_ACCENT = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 rgba(13, 89, 242, 0), stop:0.3 {Colors.ACCENT}, "
        f"stop:0.7 {Colors.ACCENT_LIGHT}, stop:1 rgba(59, 123, 255, 0))"
    )

    # Progress bar gradient
    PROGRESS = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT_LIGHT})"
    )

    # Surface gradients
    CARD_SUBTLE = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {Colors.BG_CARD}, stop:1 {Colors.BG_SURFACE})"
    )


class Timing:
    """Animation duration & easing constants"""
    FAST = 120
    NORMAL = 200
    SLOW = 350
    # QEasingCurve types used in code: OutCubic, InOutQuad, etc.


# ─── Utility Functions ─────────────────────────────────────


def hex_alpha(color, alpha_hex):
    """#RRGGBB 색상에 알파 hex 접미사 추가. hex가 아니면 그대로 반환."""
    if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        return f"{color}{alpha_hex}"
    return color


def semantic_bg(color, opacity="0D"):
    """시맨틱 색상의 배경 (투명도 포함) 반환"""
    return hex_alpha(color, opacity)


def semantic_border(color, opacity="25"):
    """시맨틱 색상의 테두리 (투명도 포함) 반환"""
    return hex_alpha(color, opacity)


def badge_style(color):
    """알약형 배지 스타일 생성"""
    bg = hex_alpha(color, "18")
    border = hex_alpha(color, "35")
    return f"""
        QLabel {{
            background-color: {bg};
            color: {color};
            border: 1px solid {border};
            border-radius: 12px;
            padding: 0 12px;
            font-size: 10pt;
            font-weight: 600;
        }}
    """


def stat_card_style(color):
    """통계 카드 스타일 생성 - 채움 배경 (Stitch)"""
    bg = hex_alpha(color, "1A")
    border = hex_alpha(color, "45")
    return f"""
        QFrame {{
            background-color: {bg};
            border: 2px solid {border};
            border-radius: {Radius.LG};
            padding: 10px;
        }}
    """


def ghost_btn_style():
    """고스트(투명) 버튼 스타일"""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {Colors.TEXT_SECONDARY};
            border: 1px solid {Colors.BORDER};
            border-radius: {Radius.MD};
            padding: 8px 20px;
            font-weight: 600;
            font-size: 12pt;
        }}
        QPushButton:hover {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_PRIMARY};
            border-color: {Colors.BORDER_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {Colors.BG_HOVER};
        }}
    """


def accent_btn_style(use_gradient=True):
    """액센트(기본) 버튼 스타일"""
    if use_gradient:
        return f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN};
                color: #FFFFFF;
                border: none;
                border-radius: {Radius.MD};
                padding: 10px 28px;
                font-weight: 600;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                background: {Gradients.ACCENT_BTN_HOVER};
            }}
            QPushButton:pressed {{
                background: {Gradients.ACCENT_BTN_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_MUTED};
            }}
        """
    return f"""
        QPushButton {{
            background-color: {Colors.ACCENT};
            color: #FFFFFF;
            border: none;
            border-radius: {Radius.MD};
            padding: 10px 28px;
            font-weight: 600;
            font-size: 12pt;
        }}
        QPushButton:hover {{
            background-color: {Colors.ACCENT_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {Colors.ACCENT_DARK};
        }}
        QPushButton:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
        }}
    """


def outline_btn_style(color):
    """아웃라인 버튼 스타일 (color별)"""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {color};
            border: 1px solid {color};
            border-radius: {Radius.MD};
            padding: 10px 20px;
            font-weight: 600;
            font-size: 12pt;
        }}
        QPushButton:hover {{
            background-color: {color};
            color: #FFFFFF;
        }}
        QPushButton:pressed {{
            background-color: {color};
            color: #FFFFFF;
        }}
        QPushButton:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
            border-color: {Colors.BORDER};
        }}
    """


def input_style():
    """공통 입력 필드 스타일"""
    return f"""
        QLineEdit {{
            background-color: {Colors.BG_INPUT};
            border: 1px solid {Colors.BORDER};
            border-radius: {Radius.MD};
            padding: 10px 14px;
            color: {Colors.TEXT_PRIMARY};
            font-size: 12pt;
        }}
        QLineEdit:focus {{
            border: 1.5px solid {Colors.ACCENT};
        }}
        QLineEdit:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
        }}
        QLineEdit::placeholder {{
            color: {Colors.TEXT_PLACEHOLDER};
        }}
    """


def section_title_style():
    """섹션 제목 스타일"""
    return (
        f"color: {Colors.TEXT_PRIMARY}; font-size: 13pt; font-weight: 700; "
        f"background: transparent; border: none; padding: 0;"
    )


def section_icon_style():
    """섹션 아이콘 스타일"""
    return (
        f"color: {Colors.ACCENT}; font-size: 14pt; font-weight: 700; "
        f"background: transparent;"
    )


def header_title_style(size="14pt"):
    """헤더 타이틀 스타일"""
    return (
        f"color: {Colors.TEXT_PRIMARY}; font-size: {size}; font-weight: 700; "
        f"letter-spacing: -0.3px; background: transparent;"
    )


def muted_text_style(size="9pt"):
    """연한 텍스트 스타일"""
    return f"color: {Colors.TEXT_MUTED}; font-size: {size}; background: transparent;"


def hint_text_style():
    """힌트/안내 텍스트 스타일"""
    return f"color: {Colors.TEXT_MUTED}; font-size: 9pt; background: transparent;"


def close_btn_style():
    """닫기 버튼 스타일"""
    return f"""
        QPushButton {{
            background: transparent;
            color: {Colors.TEXT_MUTED};
            border: none;
            border-radius: 8px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_PRIMARY};
        }}
    """


def tab_widget_style():
    """탭 위젯 스타일 - 필 탭 (Stitch)"""
    return f"""
        QTabWidget::pane {{
            border: none;
            background: transparent;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {Colors.TEXT_MUTED};
            padding: 10px 24px;
            margin: 4px 2px;
            border: none;
            border-radius: {Radius.MD};
            font-size: 12pt;
            font-weight: 600;
        }}
        QTabBar::tab:hover {{
            color: {Colors.TEXT_SECONDARY};
            background-color: {Colors.BG_ELEVATED};
        }}
        QTabBar::tab:selected {{
            color: #FFFFFF;
            background-color: {Colors.ACCENT};
        }}
    """


def terminal_text_style():
    """터미널/로그 텍스트 영역 스타일"""
    return f"""
        QTextEdit {{
            background-color: {Colors.BG_TERMINAL};
            border: 1px solid {Colors.BORDER};
            border-radius: {Radius.LG};
            padding: 14px;
            color: {Colors.TEXT_SECONDARY};
            font-family: {Typography.FAMILY_MONO};
            font-size: 9pt;
            selection-background-color: {Colors.ACCENT};
            selection-color: #FFFFFF;
        }}
    """


def progress_bar_style():
    """프로그레스 바 스타일"""
    return f"""
        QProgressBar {{
            background-color: {Colors.BG_INPUT};
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            height: 24px;
            text-align: center;
            color: {Colors.TEXT_SECONDARY};
            font-size: 9pt;
            font-weight: 600;
        }}
        QProgressBar::chunk {{
            background: {Gradients.PROGRESS};
            border-radius: 5px;
        }}
    """


def scroll_area_style():
    """스크롤 영역 스타일"""
    return f"""
        QScrollArea {{
            background: {Colors.BG_DARK};
            border: none;
        }}
    """


def dialog_style():
    """다이얼로그 기본 스타일"""
    return f"""
        QDialog {{
            background-color: {Colors.BG_DARK};
        }}
    """


def window_control_btn_style(is_close=False):
    """윈도우 컨트롤 버튼 (최소화/닫기)"""
    hover_bg = Colors.ERROR if is_close else Colors.BG_HOVER
    hover_color = "white" if is_close else Colors.TEXT_PRIMARY
    return f"""
        QPushButton {{
            background: {Colors.BG_ELEVATED}; border: none; border-radius: 4px;
            color: {Colors.TEXT_SECONDARY}; font-size: 9pt;
        }}
        QPushButton:hover {{ background: {hover_bg}; color: {hover_color}; }}
    """


# ─── Global Stylesheet ────────────────────────────────────


def global_stylesheet():
    """Application-wide base stylesheet - Stitch Blue theme"""
    c = Colors
    r = Radius
    t = Typography
    g = Gradients
    return f"""
        /* ===== Base ===== */
        QMainWindow, QDialog {{
            background-color: {c.BG_DARK};
        }}
        QWidget {{
            font-family: {t.FAMILY};
            font-size: 12pt;
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
            font-size: 11pt;
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
            font-size: 12pt;
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
            color: {c.TEXT_PLACEHOLDER};
        }}

        /* ===== Buttons ===== */
        QPushButton {{
            background: {g.ACCENT_BTN};
            color: #FFFFFF;
            border: 1px solid rgba(59, 123, 255, 0.55);
            border-radius: {r.MD};
            /* This app uses many fixed geometries; keep padding modest to avoid clipped text. */
            padding: 7px 14px;
            min-height: 30px;
            font-weight: 700;
            font-size: 12pt;
        }}
        QPushButton:hover {{
            background: {g.ACCENT_BTN_HOVER};
            border-color: rgba(59, 123, 255, 0.85);
        }}
        QPushButton:pressed {{
            background: {g.ACCENT_BTN_PRESSED};
        }}
        QPushButton:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
        }}

        /* Ghost / Secondary */
        QPushButton[class="ghost"] {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: {r.MD};
            padding: 7px 12px;
            font-size: 9pt;
            font-weight: 700;
        }}
        QPushButton[class="ghost"]:hover {{
            background-color: {c.BG_HOVER};
            color: #FFFFFF;
            border-color: {c.ACCENT};
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
            font-size: 12pt;
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
            font-size: 12pt;
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

        /* ===== RadioButton ===== */
        QRadioButton {{
            color: {c.TEXT_PRIMARY};
            font-size: 12pt;
            spacing: 10px;
        }}
        QRadioButton::indicator {{
            width: 20px;
            height: 20px;
            border: 2px solid {c.BORDER_LIGHT};
            border-radius: 10px;
            background-color: {c.BG_INPUT};
        }}
        QRadioButton::indicator:checked {{
            background-color: {c.ACCENT};
            border-color: {c.ACCENT};
        }}
        QRadioButton::indicator:hover {{
            border-color: {c.ACCENT};
        }}

        /* ===== ComboBox ===== */
        QComboBox {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 8px 12px;
            color: {c.TEXT_PRIMARY};
            font-size: 12pt;
        }}
        QComboBox:focus {{
            border-color: {c.ACCENT};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c.BG_CARD};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 4px;
            color: {c.TEXT_PRIMARY};
            selection-background-color: {c.ACCENT_GLOW};
            selection-color: {c.ACCENT_LIGHT};
        }}

        /* ===== ProgressBar ===== */
        QProgressBar {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: 6px;
            height: 24px;
            text-align: center;
            color: {c.TEXT_SECONDARY};
            font-size: 9pt;
            font-weight: 600;
        }}
        QProgressBar::chunk {{
            background: {g.PROGRESS};
            border-radius: 5px;
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
            font-size: 12pt;
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
            font-size: 11pt;
        }}

        /* ===== MessageBox ===== */
        QMessageBox {{
            background-color: {c.BG_CARD};
        }}
        QMessageBox QLabel {{
            color: {c.TEXT_PRIMARY};
            font-size: 12pt;
            min-width: 280px;
        }}
        QMessageBox QPushButton {{
            background: {g.ACCENT_BTN};
            color: white;
            border: none;
            border-radius: {r.MD};
            padding: 8px 24px;
            min-width: 80px;
            font-weight: 600;
        }}
        QMessageBox QPushButton:hover {{
            background: {g.ACCENT_BTN_HOVER};
        }}

        /* ===== ToolTip ===== */
        QToolTip {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            border-radius: {r.SM};
            padding: 8px 12px;
            font-size: 11pt;
        }}
    """


def resolve_fonts():
    """Resolve best available system fonts. Must call after QApplication is created."""
    from PyQt6.QtGui import QFontDatabase
    available = set(QFontDatabase.families())

    # UI font
    ui_candidates = ["Pretendard", "맑은 고딕", "Malgun Gothic",
                     "Apple SD Gothic Neo", "Segoe UI"]
    for name in ui_candidates:
        if name in available:
            Typography.FAMILY = name
            break

    # Mono font
    mono_candidates = ["JetBrains Mono", "Cascadia Code", "Consolas", "Courier New"]
    for name in mono_candidates:
        if name in available:
            Typography.FAMILY_MONO = name
            break

    # Regenerate inline style strings with resolved single font name
    f = Typography.FAMILY
    fm = Typography.FAMILY_MONO
    Typography.TITLE_XL = f"font-family: {f}; font-size: 24pt; font-weight: 700; letter-spacing: -0.5px;"
    Typography.TITLE_LG = f"font-family: {f}; font-size: 18pt; font-weight: 700; letter-spacing: -0.3px;"
    Typography.TITLE_MD = f"font-family: {f}; font-size: 14pt; font-weight: 600;"
    Typography.TITLE_SM = f"font-family: {f}; font-size: 12pt; font-weight: 600;"
    Typography.BODY = f"font-family: {f}; font-size: 12pt; font-weight: 400;"
    Typography.BODY_SM = f"font-family: {f}; font-size: 11pt; font-weight: 400;"
    Typography.CAPTION = f"font-family: {f}; font-size: 10pt; font-weight: 500; letter-spacing: 0.3px;"
    Typography.MONO = f"font-family: {fm}; font-size: 11pt;"
