"""Thread Auto's *Editorial Control Room* desktop design system.

The public token names in this module pre-date the redesign and are imported
throughout the application.  They deliberately remain available as semantic
aliases, while the canonical palette below mirrors the implementation
blueprint.  Keeping the aliases here lets existing screens adopt the redesign
without duplicating raw colour values or breaking callers.
"""


class Colors:
    """Canonical palette plus backwards-compatible semantic aliases."""

    # Canonical blueprint tokens.  Do not replace these with page-local hues.
    INK = "#101C24"
    PORCELAIN = "#F4F1EA"
    PAPER = "#FFFEFB"
    SLATE = "#52636D"
    LINE = "#D7DDD9"
    SIGNAL_TEAL = "#0D7C84"
    DEEP_TEAL = "#075D63"
    AMBER = "#F2A93B"
    CORAL = "#D9544D"
    EMERALD = "#27856A"
    SKY = "#DCEFF1"

    # Legacy/public semantic names used by MainWindow, LoginWindow and dialogs.
    BG_DARK = PORCELAIN
    BG_CARD = PAPER
    BG_INPUT = "#FBFAF6"
    BG_ELEVATED = "#ECE9E1"
    BG_HOVER = SKY
    BG_TERMINAL = INK
    BG_SURFACE = PAPER
    BG_SIDEBAR = INK
    BG_HEADER = PAPER

    ACCENT = SIGNAL_TEAL
    ACCENT_LIGHT = SIGNAL_TEAL
    ACCENT_DARK = DEEP_TEAL
    ACCENT_GLOW = "rgba(13, 124, 132, 0.14)"
    ACCENT_SHADOW = "rgba(7, 93, 99, 0.22)"
    ACCENT_SUBTLE = "rgba(13, 124, 132, 0.10)"

    SUCCESS = EMERALD
    SUCCESS_BG = "rgba(39, 133, 106, 0.12)"
    SUCCESS_BORDER = "rgba(39, 133, 106, 0.34)"
    WARNING = AMBER
    WARNING_BG = "rgba(242, 169, 59, 0.16)"
    WARNING_BORDER = "rgba(242, 169, 59, 0.42)"
    ERROR = CORAL
    ERROR_BG = "rgba(217, 84, 77, 0.12)"
    ERROR_BORDER = "rgba(217, 84, 77, 0.38)"
    INFO = SIGNAL_TEAL
    INFO_BG = SKY
    INFO_BORDER = "rgba(13, 124, 132, 0.32)"

    TEXT_PRIMARY = INK
    TEXT_SECONDARY = SLATE
    TEXT_MUTED = "#5E6D74"
    TEXT_PLACEHOLDER = "#5E6D74"
    TEXT_ACCENT = DEEP_TEAL
    TEXT_BRIGHT = PAPER
    TEXT_ON_INK = PAPER
    TEXT_ON_INK_MUTED = "#B8C7CB"

    BORDER = LINE
    BORDER_LIGHT = "#BCC7C4"
    BORDER_ACTIVE = SIGNAL_TEAL
    BORDER_SUBTLE = "#E7E8E2"

    SCROLLBAR = "#B9C3C0"
    SCROLLBAR_HOVER = SLATE
    SHADOW = "rgba(16, 28, 36, 0.16)"
    OVERLAY = "rgba(16, 28, 36, 0.74)"


class Typography:
    """Korean desktop type scale, resolved at runtime by ``resolve_fonts``."""
    FAMILY = "Pretendard"
    FAMILY_MONO = "Consolas"

    DISPLAY_SIZE = 26
    PAGE_TITLE_SIZE = 22
    SECTION_SIZE = 17
    BODY_SIZE = 14
    CAPTION_SIZE = 12
    MONO_SIZE = 12

    DISPLAY = f"font-family: {FAMILY}; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;"
    PAGE_TITLE = f"font-family: {FAMILY}; font-size: 22px; font-weight: 700; letter-spacing: -0.35px;"
    SECTION = f"font-family: {FAMILY}; font-size: 17px; font-weight: 700; letter-spacing: -0.2px;"
    BODY = f"font-family: {FAMILY}; font-size: 14px; font-weight: 400;"
    CAPTION = f"font-family: {FAMILY}; font-size: 12px; font-weight: 500;"
    MONO = f"font-family: {FAMILY_MONO}; font-size: 12px;"

    # Compatibility aliases for the existing view layer.
    TITLE_XL = PAGE_TITLE
    TITLE_LG = PAGE_TITLE
    TITLE_MD = SECTION
    TITLE_SM = SECTION
    BODY_SM = BODY


class Radius:
    """Blueprint radii: input 8, card 12 and hero/modal 16 DIP."""

    INPUT = "8px"
    CARD = "12px"
    HERO = "16px"

    # Compatibility aliases.
    SM = INPUT
    MD = INPUT
    LG = CARD
    XL = HERO
    XXL = HERO
    PILL = "999px"


class Spacing:
    """Editorial spacing scale in device-independent pixels."""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48

    SPACE_4 = XS
    SPACE_8 = SM
    SPACE_12 = MD
    SPACE_16 = LG
    SPACE_24 = XL
    SPACE_32 = XXL
    SPACE_48 = XXXL


class ControlHeight:
    """Shared control heights in logical DIP (Qt handles DPI scaling)."""

    ICON = 40
    INPUT = 44
    PRIMARY = 48
    FIXED_FOOTER = 64


class Breakpoints:
    """Responsive contract from the blueprint, expressed in logical DIP."""

    MINIMUM_WIDTH = 760
    MINIMUM_HEIGHT = 560
    STANDARD_WIDTH = 900
    WIDE_WIDTH = 1180

    NAV_COMPACT = 72
    NAV_STANDARD = 190
    NAV_WIDE = 240
    CTA_SAFE_AREA = ControlHeight.FIXED_FOOTER

    DPI_QA_SCALES = (100, 125, 150, 175, 200)

    @classmethod
    def navigation_width(cls, viewport_width: int) -> int:
        """Return the layout width; never multiply it by devicePixelRatio."""

        if viewport_width >= cls.WIDE_WIDTH:
            return cls.NAV_WIDE
        if viewport_width >= cls.STANDARD_WIDTH:
            return cls.NAV_STANDARD
        return cls.NAV_COMPACT


class Shadows:
    """Box shadow presets (CSS-like, for custom painting)."""
    CARD = (0, 2, 10, "rgba(16, 28, 36, 0.08)")
    ELEVATED = (0, 6, 20, "rgba(16, 28, 36, 0.12)")
    DROPDOWN = (0, 10, 28, "rgba(16, 28, 36, 0.16)")
    GLOW_ACCENT = (0, 0, 14, "rgba(13, 124, 132, 0.20)")
    GLOW_SUCCESS = (0, 0, 12, "rgba(39, 133, 106, 0.18)")
    GLOW_ERROR = (0, 0, 12, "rgba(217, 84, 77, 0.18)")


class Gradients:
    """Compatibility paint values for a deliberately near-flat interface."""

    # The editorial language relies on colour blocks rather than decorative
    # gradients.  These names remain because several existing screens consume
    # them through QSS ``background`` declarations.
    ACCENT_BTN = Colors.SIGNAL_TEAL
    ACCENT_BTN_HOVER = Colors.DEEP_TEAL
    ACCENT_BTN_PRESSED = Colors.INK
    HEADER = Colors.PAPER
    HEADER_ACCENT = Colors.SIGNAL_TEAL
    PROGRESS = Colors.SIGNAL_TEAL
    CARD_SUBTLE = Colors.PAPER
    LOGIN_SPLASH = Colors.INK


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
    """Secondary action with a visible keyboard-focus treatment."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {Colors.TEXT_SECONDARY};
            border: 1px solid {Colors.BORDER_LIGHT};
            border-radius: {Radius.MD};
            padding: 0 16px;
            min-height: {ControlHeight.ICON}px;
            font-weight: 600;
            font-size: 10.5pt;
        }}
        QPushButton:hover {{
            background-color: {Colors.SKY};
            color: {Colors.TEXT_PRIMARY};
            border-color: {Colors.ACCENT};
        }}
        QPushButton:focus {{
            background-color: {Colors.SKY};
            color: {Colors.TEXT_PRIMARY};
            border: 2px solid {Colors.ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {Colors.BG_ELEVATED};
        }}
        QPushButton:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
            border-color: {Colors.BORDER};
        }}
    """


def accent_btn_style(use_gradient=True):
    """Primary accent button."""
    if use_gradient:
        return f"""
            QPushButton {{
                background: {Gradients.ACCENT_BTN};
                color: {Colors.TEXT_BRIGHT};
                border: 2px solid {Colors.ACCENT};
                border-radius: {Radius.MD};
                padding: 0 28px;
                min-height: {ControlHeight.PRIMARY}px;
                font-weight: 600;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background: {Gradients.ACCENT_BTN_HOVER};
                border-color: {Colors.ACCENT_DARK};
            }}
            QPushButton:focus {{
                background: {Gradients.ACCENT_BTN};
                border: 2px solid {Colors.INK};
            }}
            QPushButton:pressed {{
                background: {Gradients.ACCENT_BTN_PRESSED};
                border-color: {Colors.INK};
            }}
            QPushButton:disabled {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_MUTED};
                border-color: {Colors.BORDER};
            }}
        """
    return f"""
        QPushButton {{
            background-color: {Colors.ACCENT};
            color: {Colors.TEXT_BRIGHT};
            border: 2px solid {Colors.ACCENT};
            border-radius: {Radius.MD};
            padding: 0 28px;
            min-height: {ControlHeight.PRIMARY}px;
            font-weight: 600;
            font-size: 11pt;
        }}
        QPushButton:hover {{
            background-color: {Colors.ACCENT_LIGHT};
        }}
        QPushButton:focus {{
            border: 2px solid {Colors.INK};
        }}
        QPushButton:pressed {{
            background-color: {Colors.ACCENT_DARK};
        }}
        QPushButton:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
            border-color: {Colors.BORDER};
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
            padding: 0 20px;
            min-height: {ControlHeight.ICON}px;
            font-weight: 600;
            font-size: 10.5pt;
        }}
        QPushButton:hover {{
            background-color: {color};
            color: {Colors.TEXT_BRIGHT};
        }}
        QPushButton:pressed {{
            background-color: {color};
            color: {Colors.TEXT_BRIGHT};
        }}
        QPushButton:focus {{
            background-color: {Colors.BG_CARD};
            color: {color};
            border: 2px solid {color};
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
            padding: 0 14px;
            min-height: {ControlHeight.INPUT}px;
            color: {Colors.TEXT_PRIMARY};
            font-size: 11pt;
        }}
        QLineEdit:focus {{
            border: 2px solid {Colors.ACCENT};
            background-color: {Colors.BG_CARD};
        }}
        QLineEdit:disabled {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_MUTED};
            border-color: {Colors.BORDER_SUBTLE};
        }}
        QLineEdit::placeholder {{
            color: {Colors.TEXT_PLACEHOLDER};
        }}
    """


def section_title_style():
    return (
        f"color: {Colors.TEXT_PRIMARY}; font-size: 12pt; font-weight: 700; "
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


def muted_text_style(size="9.5pt"):
    return f"color: {Colors.TEXT_MUTED}; font-size: {size}; background: transparent;"


def hint_text_style():
    return f"color: {Colors.TEXT_MUTED}; font-size: 9.5pt; background: transparent;"


def close_btn_style():
    return f"""
        QPushButton {{
            background: transparent;
            color: {Colors.TEXT_MUTED};
            border: none;
            border-radius: 8px;
            padding: 0;
            min-height: 0;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.BG_ELEVATED};
            color: {Colors.TEXT_PRIMARY};
        }}
        QPushButton:focus {{
            background-color: {Colors.SKY};
            color: {Colors.TEXT_PRIMARY};
            border: 2px solid {Colors.ACCENT};
        }}
        QPushButton:disabled {{ color: {Colors.BORDER_LIGHT}; }}
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
        QTabBar::tab:focus {{
            color: {Colors.TEXT_PRIMARY};
            border: 2px solid {Colors.ACCENT};
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
            color: {Colors.TEXT_ON_INK_MUTED};
            font-family: {Typography.FAMILY_MONO};
            font-size: 9.5pt;
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
            min-height: 24px;
            text-align: center;
            color: {Colors.TEXT_SECONDARY};
            font-size: 9.5pt;
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
            color: {Colors.TEXT_SECONDARY}; font-size: 9.5pt; padding: 0; min-height: 0;
        }}
        QPushButton:hover {{ background: {hover_bg}; color: {hover_color}; }}
        QPushButton:focus {{
            background: {hover_bg}; color: {hover_color};
            border: 2px solid {Colors.ACCENT};
        }}
        QPushButton:disabled {{ color: {Colors.BORDER_LIGHT}; }}
    """


# ─── Global Stylesheet ────────────────────────────────────


def global_stylesheet():
    """Application-wide base stylesheet for Editorial Control Room."""
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
            font-size: 11pt;
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
            background: {c.BG_ELEVATED};
            width: 10px;
            margin: 3px 1px;
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
            background-color: {c.BG_CARD};
            border: 1px solid {c.BORDER};
            border-radius: {r.LG};
            padding: 14px;
            color: {c.TEXT_PRIMARY};
            selection-background-color: {c.ACCENT};
            selection-color: {c.TEXT_BRIGHT};
            font-family: {t.FAMILY_MONO};
            font-size: 10.5pt;
        }}
        QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {c.ACCENT};
            border-width: 2px;
        }}
        QTextEdit:disabled, QPlainTextEdit:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
            border-color: {c.BORDER_SUBTLE};
        }}
        QLineEdit {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 0 14px;
            min-height: 42px;
            color: {c.TEXT_PRIMARY};
            font-size: 11pt;
        }}
        QLineEdit:focus {{
            border-color: {c.ACCENT};
            border-width: 2px;
            background-color: {c.BG_CARD};
        }}
        QLineEdit:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
            border-color: {c.BORDER_SUBTLE};
        }}
        QLineEdit::placeholder {{
            color: {c.TEXT_PLACEHOLDER};
        }}

        /* ===== Buttons ===== */
        QPushButton {{
            background: {g.ACCENT_BTN};
            color: {c.TEXT_BRIGHT};
            border: 2px solid {c.ACCENT};
            border-radius: {r.MD};
            padding: 9px 18px;
            min-height: 24px;
            font-weight: 650;
            font-size: 10.5pt;
        }}
        QPushButton:hover {{
            background: {g.ACCENT_BTN_HOVER};
            border-color: {c.ACCENT_DARK};
        }}
        QPushButton:focus {{
            background: {g.ACCENT_BTN};
            border: 2px solid {c.INK};
        }}
        QPushButton:pressed {{
            background: {g.ACCENT_BTN_PRESSED};
            border-color: {c.INK};
        }}
        QPushButton:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
            border-color: {c.BORDER};
        }}

        QPushButton[class="ghost"] {{
            background-color: transparent;
            color: {c.TEXT_SECONDARY};
            border: 1px solid {c.BORDER_LIGHT};
            padding: 9px 14px;        /* base QPushButton 28px padding override → 한국어 텍스트 잘림 방지 */
        }}
        QPushButton[class="ghost"]:hover {{
            background-color: {c.SKY};
            color: {c.TEXT_PRIMARY};
            border-color: {c.ACCENT};
        }}
        QPushButton[class="ghost"]:focus {{
            background-color: {c.SKY};
            color: {c.TEXT_PRIMARY};
            border: 2px solid {c.ACCENT};
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
            background-color: {c.BG_CARD};
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
            background-color: {c.SKY};
            color: {c.TEXT_PRIMARY};
        }}
        QListWidget::item:hover {{
            background-color: {c.BG_ELEVATED};
        }}

        /* ===== SpinBox ===== */
        QSpinBox {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 6px 30px 6px 12px;   /* 우측 패딩으로 버튼 자리 확보 */
            color: {c.TEXT_PRIMARY};
            font-size: 10.5pt;
            font-weight: 600;
            qproperty-alignment: 'AlignVCenter | AlignLeft';
        }}
        QSpinBox:focus {{
            border: 2px solid {c.ACCENT};
        }}
        QSpinBox:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
            border-color: {c.BORDER_SUBTLE};
        }}
        /* ===== Checkbox ===== */
        QCheckBox {{
            color: {c.TEXT_PRIMARY};
            font-size: 10.5pt;
            spacing: 8px;
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
        QCheckBox:focus {{ color: {c.TEXT_PRIMARY}; }}
        QCheckBox::indicator:focus {{ border: 2px solid {c.ACCENT}; }}
        QCheckBox:disabled {{ color: {c.TEXT_MUTED}; }}
        QCheckBox::indicator:disabled {{
            background-color: {c.BG_ELEVATED};
            border-color: {c.BORDER};
        }}

        /* ===== RadioButton ===== */
        QRadioButton {{
            color: {c.TEXT_PRIMARY};
            font-size: 10.5pt;
            spacing: 8px;
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
        QRadioButton:focus {{ color: {c.TEXT_PRIMARY}; }}
        QRadioButton::indicator:focus {{ border: 2px solid {c.ACCENT}; }}
        QRadioButton:disabled {{ color: {c.TEXT_MUTED}; }}
        QRadioButton::indicator:disabled {{
            background-color: {c.BG_ELEVATED};
            border-color: {c.BORDER};
        }}

        /* ===== ComboBox ===== */
        QComboBox {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: {r.MD};
            padding: 7px 12px;
            color: {c.TEXT_PRIMARY};
            font-size: 10.5pt;
        }}
        QComboBox:focus {{
            border: 2px solid {c.ACCENT};
        }}
        QComboBox:disabled {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_MUTED};
            border-color: {c.BORDER_SUBTLE};
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
            selection-background-color: {c.SKY};
            selection-color: {c.TEXT_PRIMARY};
        }}

        /* ===== Editorial tables ===== */
        QTableView, QTableWidget {{
            background-color: {c.BG_CARD};
            alternate-background-color: {c.BG_INPUT};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER};
            border-radius: {r.CARD};
            gridline-color: {c.BORDER_SUBTLE};
            selection-background-color: {c.SKY};
            selection-color: {c.TEXT_PRIMARY};
        }}
        QHeaderView::section {{
            background-color: {c.BG_ELEVATED};
            color: {c.TEXT_SECONDARY};
            border: none;
            border-bottom: 1px solid {c.BORDER};
            padding: 8px 12px;
            font-weight: 600;
        }}

        /* ===== ProgressBar ===== */
        QProgressBar {{
            background-color: {c.BG_INPUT};
            border: 1px solid {c.BORDER};
            border-radius: 7px;
            height: 24px;
            text-align: center;
            color: {c.TEXT_SECONDARY};
            font-size: 9.5pt;
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
            font-size: 9.5pt;
        }}

        /* ===== MessageBox ===== */
        QMessageBox {{
            background-color: {c.BG_CARD};
        }}
        QMessageBox QLabel {{
            color: {c.TEXT_PRIMARY};
            font-size: 10.5pt;
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
            font-size: 10pt;
        }}
    """


def resolve_fonts():
    """Resolve best available system fonts. Call after QApplication is created."""
    from PyQt6.QtGui import QFontDatabase
    available = set(QFontDatabase.families())

    ui_candidates = ["Pretendard", "Pretendard Variable",
                     "LINE Seed Sans KR", "LINE Seed Sans KR OTF",
                     "SUIT", "Noto Sans KR", "맑은 고딕",
                     "Malgun Gothic", "Apple SD Gothic Neo", "Inter",
                     "Segoe UI Variable", "Segoe UI"]
    for name in ui_candidates:
        if name in available:
            Typography.FAMILY = name
            break

    mono_candidates = ["Consolas", "JetBrains Mono", "Cascadia Code", "Courier New"]
    for name in mono_candidates:
        if name in available:
            Typography.FAMILY_MONO = name
            break

    f = Typography.FAMILY
    fm = Typography.FAMILY_MONO
    Typography.DISPLAY = (
        f"font-family: {f}; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;"
    )
    Typography.PAGE_TITLE = (
        f"font-family: {f}; font-size: 22px; font-weight: 700; letter-spacing: -0.35px;"
    )
    Typography.SECTION = (
        f"font-family: {f}; font-size: 17px; font-weight: 700; letter-spacing: -0.2px;"
    )
    Typography.BODY = f"font-family: {f}; font-size: 14px; font-weight: 400;"
    Typography.CAPTION = f"font-family: {f}; font-size: 12px; font-weight: 500;"
    Typography.MONO = f"font-family: {fm}; font-size: 12px;"

    Typography.TITLE_XL = Typography.PAGE_TITLE
    Typography.TITLE_LG = Typography.PAGE_TITLE
    Typography.TITLE_MD = Typography.SECTION
    Typography.TITLE_SM = Typography.SECTION
    Typography.BODY_SM = Typography.BODY
