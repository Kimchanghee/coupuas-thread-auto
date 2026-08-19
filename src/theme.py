"""Thread Auto desktop design system.

The palette deliberately uses neutral midnight surfaces and a restrained
teal accent.  Keeping every widget on the same token set avoids the old
mixture of coral, bright red and saturated blue controls.
"""


class Colors:
    """Midnight Workshop palette with WCAG-friendly text contrast."""

    BG_DARK = "#0A0F1C"
    BG_CARD = "#141D2D"
    BG_INPUT = "#0F1726"
    BG_ELEVATED = "#1B273A"
    BG_HOVER = "#24334B"
    BG_TERMINAL = "#070B13"
    BG_SURFACE = "#111827"
    BG_SIDEBAR = "#0C1424"
    BG_HEADER = "#0F1829"

    ACCENT = "#2DD4BF"
    ACCENT_LIGHT = "#5EEAD4"
    ACCENT_DARK = "#14B8A6"
    ACCENT_GLOW = "rgba(45, 212, 191, 0.18)"
    ACCENT_SHADOW = "rgba(45, 212, 191, 0.32)"
    ACCENT_SUBTLE = "rgba(45, 212, 191, 0.10)"

    SUCCESS = "#3DDC97"
    SUCCESS_BG = "rgba(61, 220, 151, 0.10)"
    SUCCESS_BORDER = "rgba(61, 220, 151, 0.30)"
    WARNING = "#F6C65B"
    WARNING_BG = "rgba(246, 198, 91, 0.10)"
    WARNING_BORDER = "rgba(246, 198, 91, 0.30)"
    ERROR = "#FF6B7A"
    ERROR_BG = "rgba(255, 107, 122, 0.10)"
    ERROR_BORDER = "rgba(255, 107, 122, 0.30)"
    INFO = "#55B6FF"
    INFO_BG = "rgba(85, 182, 255, 0.10)"
    INFO_BORDER = "rgba(85, 182, 255, 0.30)"

    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#CDD6E5"
    TEXT_MUTED = "#8C9AAF"
    TEXT_PLACEHOLDER = "#5E6B80"
    TEXT_ACCENT = "#7DEBDD"
    TEXT_BRIGHT = "#FFFFFF"

    BORDER = "#25344C"
    BORDER_LIGHT = "#3A4B68"
    BORDER_ACTIVE = "#2DD4BF"
    BORDER_SUBTLE = "#1B283C"

    SCROLLBAR = "#2B3A53"
    SCROLLBAR_HOVER = "#465A7A"
    SHADOW = "rgba(0, 0, 0, 0.55)"
    OVERLAY = "rgba(10, 15, 28, 0.92)"


class Typography:
    """Font definitions — resolved at runtime by resolve_fonts()."""
    FAMILY = "Segoe UI"
    FAMILY_MONO = "Consolas"

    TITLE_XL = f"font-family: {FAMILY}; font-size: 22pt; font-weight: 700; letter-spacing: -0.5px;"
    TITLE_LG = f"font-family: {FAMILY}; font-size: 17pt; font-weight: 700; letter-spacing: -0.35px;"
    TITLE_MD = f"font-family: {FAMILY}; font-size: 13pt; font-weight: 650; letter-spacing: -0.2px;"
    TITLE_SM = f"font-family: {FAMILY}; font-size: 11pt; font-weight: 650;"
    BODY = f"font-family: {FAMILY}; font-size: 10pt; font-weight: 400;"
    BODY_SM = f"font-family: {FAMILY}; font-size: 9.5pt; font-weight: 400;"
    CAPTION = f"font-family: {FAMILY}; font-size: 9pt; font-weight: 500; letter-spacing: 0.2px;"
    MONO = f"font-family: {FAMILY_MONO}; font-size: 9pt;"


class Radius:
    SM = "6px"
    MD = "8px"
    LG = "12px"
    XL = "16px"
    XXL = "20px"
    PILL = "100px"


class Spacing:
    """Consistent spacing scale (4px base)."""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24
    XXXL = 32


class Shadows:
    """Box shadow presets (CSS-like, for custom painting)."""
    CARD = (0, 2, 10, "rgba(0, 0, 0, 0.30)")
    ELEVATED = (0, 6, 20, "rgba(0, 0, 0, 0.40)")
    DROPDOWN = (0, 10, 28, "rgba(0, 0, 0, 0.50)")
    GLOW_ACCENT = (0, 0, 14, "rgba(217, 119, 87, 0.28)")
    GLOW_SUCCESS = (0, 0, 12, "rgba(122, 184, 122, 0.22)")
    GLOW_ERROR = (0, 0, 12, "rgba(216, 106, 101, 0.22)")


class Gradients:
    """Low-contrast gradients used only for hierarchy, never decoration."""

    # Buttons — flat coral with subtle warm shift
    ACCENT_BTN = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 #38DDC8, stop:1 {Colors.ACCENT})"
    )
    ACCENT_BTN_HOVER = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 #64EBD7, stop:1 #38DDC8)"
    )
    ACCENT_BTN_PRESSED = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {Colors.ACCENT_DARK}, stop:1 #0F9F90)"
    )

    # Header — warm charcoal, near-flat
    HEADER = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {Colors.BG_HEADER}, stop:1 {Colors.BG_DARK})"
    )
    HEADER_ACCENT = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 rgba(45, 212, 191, 0), stop:0.3 {Colors.ACCENT}, "
        f"stop:0.7 {Colors.ACCENT_LIGHT}, stop:1 rgba(94, 234, 212, 0))"
    )

    # Progress
    PROGRESS = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT_LIGHT})"
    )

    # Surface
    CARD_SUBTLE = (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {Colors.BG_CARD}, stop:1 {Colors.BG_SURFACE})"
    )

    # Login splash — warm coral wash
    LOGIN_SPLASH = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        "stop:0 #090E1A, stop:0.48 #102332, stop:0.82 #155E61, stop:1 #0F766E)"
    )


class Timing:
    """Animation duration & easing constants."""
    FAST = 120
    NORMAL = 200
    SLOW = 350


# ─── Utility Functions ─────────────────────────────────────


def hex_alpha(color, alpha_hex):
    """Append alpha hex suffix to #RRGGBB. Pass-through for non-hex strings."""
    if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        return f"{color}{alpha_hex}"
    return color


def semantic_bg(color, opacity="0D"):
    return hex_alpha(color, opacity)


def semantic_border(color, opacity="35"):
    return hex_alpha(color, opacity)


def badge_style(color):
    """Pill badge."""
    bg = hex_alpha(color, "1F")
    border = hex_alpha(color, "45")
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
    """Filled stat card."""
    bg = hex_alpha(color, "1A")
    border = hex_alpha(color, "40")
    return f"""
        QFrame {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {Radius.LG};
            padding: 12px;
        }}
    """


def ghost_btn_style():
    """Ghost (transparent) button — 한국어 12pt 텍스트가 잘리지 않도록 좌우 padding 축소."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {Colors.TEXT_SECONDARY};
            border: 1px solid {Colors.BORDER_LIGHT};
            border-radius: {Radius.MD};
            padding: 9px 14px;
            font-weight: 600;
            font-size: 12pt;
        }}
        QPushButton:hover {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_PRIMARY};
            border-color: {Colors.ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {Colors.BG_HOVER};
        }}
    """


def accent_btn_style(use_gradient=True):
    """Primary accent button."""
    if use_gradient:
        return f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN};
                color: {Colors.TEXT_BRIGHT};
                border: none;
                border-radius: {Radius.MD};
                padding: 11px 28px;
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
            color: {Colors.TEXT_BRIGHT};
            border: none;
            border-radius: {Radius.MD};
            padding: 11px 28px;
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
    """Outline button per color."""
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
            color: {Colors.TEXT_BRIGHT};
        }}
        QPushButton:pressed {{
            background-color: {color};
            color: {Colors.TEXT_BRIGHT};
        }}
        QPushButton:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
            border-color: {Colors.BORDER};
        }}
    """


def input_style():
    """Standard input field."""
    return f"""
        QLineEdit {{
            background-color: {Colors.BG_INPUT};
            border: 1px solid {Colors.BORDER};
            border-radius: {Radius.MD};
            padding: 11px 14px;
            color: {Colors.TEXT_PRIMARY};
            font-size: 12pt;
        }}
        QLineEdit:focus {{
            border: 1.5px solid {Colors.ACCENT};
            background-color: {Colors.BG_CARD};
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
    return (
        f"color: {Colors.TEXT_PRIMARY}; font-size: 13pt; font-weight: 700; "
        f"background: transparent; border: none; padding: 0;"
    )


def section_icon_style():
    return (
        f"color: {Colors.ACCENT}; font-size: 14pt; font-weight: 700; "
        f"background: transparent;"
    )


def header_title_style(size="14pt"):
    return (
        f"color: {Colors.TEXT_PRIMARY}; font-size: {size}; font-weight: 700; "
        f"letter-spacing: -0.4px; background: transparent;"
    )


def muted_text_style(size="9pt"):
    return f"color: {Colors.TEXT_MUTED}; font-size: {size}; background: transparent;"


def hint_text_style():
    return f"color: {Colors.TEXT_MUTED}; font-size: 9pt; background: transparent;"


def close_btn_style():
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
    """Pill tabs (Claude)."""
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
            color: {Colors.TEXT_BRIGHT};
            background-color: {Colors.ACCENT};
        }}
    """


def terminal_text_style():
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
            selection-color: {Colors.TEXT_BRIGHT};
        }}
    """


def progress_bar_style():
    return f"""
        QProgressBar {{
            background-color: {Colors.BG_INPUT};
            border: 1px solid {Colors.BORDER};
            border-radius: 7px;
            height: 24px;
            text-align: center;
            color: {Colors.TEXT_SECONDARY};
            font-size: 9pt;
            font-weight: 600;
        }}
        QProgressBar::chunk {{
            background: {Gradients.PROGRESS};
            border-radius: 6px;
        }}
    """


def scroll_area_style():
    return f"""
        QScrollArea {{
            background: {Colors.BG_DARK};
            border: none;
        }}
    """


def dialog_style():
    return f"""
        QDialog {{
            background-color: {Colors.BG_DARK};
        }}
    """


def window_control_btn_style(is_close=False):
    hover_bg = Colors.ERROR if is_close else Colors.BG_HOVER
    hover_color = Colors.TEXT_BRIGHT if is_close else Colors.TEXT_PRIMARY
    return f"""
        QPushButton {{
            background: {Colors.BG_ELEVATED}; border: none; border-radius: 6px;
            color: {Colors.TEXT_SECONDARY}; font-size: 9pt;
        }}
        QPushButton:hover {{ background: {hover_bg}; color: {hover_color}; }}
    """


# ─── Global Stylesheet ────────────────────────────────────


def global_stylesheet():
    """Application-wide base stylesheet — Midnight Workshop."""
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
            width: 8px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {c.SCROLLBAR};
            border-radius: 4px;
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
            height: 8px;
            margin: 2px 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c.SCROLLBAR};
            border-radius: 4px;
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
            selection-color: {c.TEXT_BRIGHT};
            font-family: {t.FAMILY_MONO};
            font-size: 9pt;
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
            background-color: {c.BG_CARD};
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
            color: {c.TEXT_BRIGHT};
            border: none;
            border-radius: {r.MD};
            padding: 9px 18px;
            min-height: 22px;
            font-weight: 650;
            font-size: 10pt;
        }}
        QPushButton:hover {{
            background: {g.ACCENT_BTN_HOVER};
        }}
        QPushButton:pressed {{
            background: {g.ACCENT_BTN_PRESSED};
        }}
        QPushButton:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
        }}

        QPushButton[class="ghost"] {{
            background-color: transparent;
            color: {c.TEXT_SECONDARY};
            border: 1px solid {c.BORDER_LIGHT};
            padding: 9px 14px;        /* base QPushButton 28px padding override → 한국어 텍스트 잘림 방지 */
        }}
        QPushButton[class="ghost"]:hover {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_PRIMARY};
            border-color: {c.ACCENT};
        }}

        QPushButton[class="outline-danger"] {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1px solid {c.ERROR};
        }}
        QPushButton[class="outline-danger"]:hover {{
            background-color: {c.ERROR};
            color: {c.TEXT_BRIGHT};
        }}

        QPushButton[class="outline-success"] {{
            background-color: transparent;
            color: {c.SUCCESS};
            border: 1px solid {c.SUCCESS};
        }}
        QPushButton[class="outline-success"]:hover {{
            background-color: {c.SUCCESS};
            color: {c.TEXT_BRIGHT};
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
            padding: 9px 12px;
            border-radius: {r.SM};
        }}
        QListWidget::item:selected {{
            background-color: {c.ACCENT_GLOW};
            color: {c.ACCENT_LIGHT};
        }}
        QListWidget::item:hover {{
            background-color: {c.BG_ELEVATED};
        }}

        /* ===== SpinBox — 텍스트 우측 정렬, up/down은 우측 끝 한 덩어리 ===== */
        QSpinBox {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 6px 30px 6px 12px;   /* 우측 패딩으로 버튼 자리 확보 */
            color: {c.TEXT_PRIMARY};
            font-size: 12pt;
            font-weight: 600;
            qproperty-alignment: 'AlignVCenter | AlignLeft';
        }}
        QSpinBox:focus {{
            border-color: {c.ACCENT};
        }}
        QSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            background-color: {c.BG_ELEVATED};
            border: none;
            border-top-right-radius: {r.MD};
            border-left: 1px solid {c.BORDER};
            border-bottom: 1px solid {c.BORDER_SUBTLE};
            width: 24px;
        }}
        QSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            background-color: {c.BG_ELEVATED};
            border: none;
            border-bottom-right-radius: {r.MD};
            border-left: 1px solid {c.BORDER};
            width: 24px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {c.ACCENT};
        }}
        QSpinBox::up-arrow {{
            image: none;
            width: 0; height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {c.TEXT_SECONDARY};
        }}
        QSpinBox::down-arrow {{
            image: none;
            width: 0; height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {c.TEXT_SECONDARY};
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
            border-radius: 7px;
            height: 24px;
            text-align: center;
            color: {c.TEXT_SECONDARY};
            font-size: 9pt;
            font-weight: 600;
        }}
        QProgressBar::chunk {{
            background: {g.PROGRESS};
            border-radius: 6px;
        }}

        /* ===== GroupBox ===== */
        QGroupBox {{
            background-color: {c.BG_CARD};
            border: 1px solid {c.BORDER};
            border-radius: {r.LG};
            margin-top: 14px;
            padding: 22px 18px 18px 18px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 18px;
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
            background-color: {c.BG_HEADER};
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
            color: {c.TEXT_BRIGHT};
            border: none;
            border-radius: {r.MD};
            padding: 9px 26px;
            min-width: 88px;
            font-weight: 600;
        }}
        QMessageBox QPushButton:hover {{
            background: {g.ACCENT_BTN_HOVER};
        }}

        /* ===== ToolTip ===== */
        QToolTip {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: {r.SM};
            padding: 8px 12px;
            font-size: 11pt;
        }}
    """


def resolve_fonts():
    """Resolve best available system fonts. Call after QApplication is created."""
    from PyQt6.QtGui import QFontDatabase
    available = set(QFontDatabase.families())

    ui_candidates = ["Pretendard", "SUIT", "Noto Sans KR", "맑은 고딕",
                     "Malgun Gothic", "Apple SD Gothic Neo", "Inter",
                     "Segoe UI Variable", "Segoe UI"]
    for name in ui_candidates:
        if name in available:
            Typography.FAMILY = name
            break

    mono_candidates = ["JetBrains Mono", "Cascadia Code", "Consolas", "Courier New"]
    for name in mono_candidates:
        if name in available:
            Typography.FAMILY_MONO = name
            break

    f = Typography.FAMILY
    fm = Typography.FAMILY_MONO
    Typography.TITLE_XL = f"font-family: {f}; font-size: 22pt; font-weight: 700; letter-spacing: -0.5px;"
    Typography.TITLE_LG = f"font-family: {f}; font-size: 17pt; font-weight: 700; letter-spacing: -0.35px;"
    Typography.TITLE_MD = f"font-family: {f}; font-size: 13pt; font-weight: 650; letter-spacing: -0.2px;"
    Typography.TITLE_SM = f"font-family: {f}; font-size: 11pt; font-weight: 650;"
    Typography.BODY = f"font-family: {f}; font-size: 10pt; font-weight: 400;"
    Typography.BODY_SM = f"font-family: {f}; font-size: 9.5pt; font-weight: 400;"
    Typography.CAPTION = f"font-family: {f}; font-size: 9pt; font-weight: 500; letter-spacing: 0.2px;"
    Typography.MONO = f"font-family: {fm}; font-size: 9pt;"
