# -*- coding: utf-8 -*-
"""
High-DPI and monitor-aware window sizing utilities.

Qt already renders in device-independent pixels.  The previous implementation
also forced ``QT_SCALE_FACTOR`` down to 50%, which made type and click targets
unreadably small on compact or high-DPI monitors.  We now keep native Qt DPI
scaling and choose a bounded, monitor-aware logical window size instead.
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

# 설계 기준 크기(가장 큰 창: 메인 1280x800 + 타이틀바/여백 감안)
_DESIGN_W = 1300.0
_DESIGN_H = 860.0


def compute_fit_scale_factor() -> float:
    """
    화면 작업영역(작업표시줄 제외)에 설계 크기가 들어가도록 하는
    글로벌 스케일 팩터(0.5~1.0)를 반환한다. 큰 화면이면 1.0(=축소 없음).
    어떤 오류가 나도 1.0을 반환해 안전하다.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        user32 = ctypes.windll.user32
        rect = _RECT()
        SPI_GETWORKAREA = 0x0030
        if not user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return 1.0
        avail_w = float(rect.right - rect.left)
        avail_h = float(rect.bottom - rect.top)
        if avail_w <= 0 or avail_h <= 0:
            return 1.0
        # 시스템 DPI로 논리 픽셀 환산 (DPI 인식/비인식 양쪽 모두 정상 동작)
        try:
            dpi = float(user32.GetDpiForSystem() or 96)
        except Exception:
            dpi = 96.0
        scale = dpi / 96.0 if dpi > 0 else 1.0
        avail_lw = avail_w / scale
        avail_lh = avail_h / scale
        margin = 0.97  # 가장자리 여백
        factor = min(1.0, (avail_lw * margin) / _DESIGN_W, (avail_lh * margin) / _DESIGN_H)
        # 과도한 축소 방지(하한 0.5)
        return max(0.5, round(factor, 3))
    except Exception:
        return 1.0


def configure_high_dpi() -> None:
    """
    QApplication 생성 "전에" 호출해야 한다.
    - enable Qt High-DPI rendering
    - preserve fractional monitor scaling with PassThrough rounding
    - never force a global application shrink factor
    """
    if sys.platform == "win32":
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt

        if hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy") and \
                hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
            try:
                QApplication.setHighDpiScaleFactorRoundingPolicy(
                    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
                )
            except Exception:
                pass
        if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except Exception:
        logger.debug("High-DPI 속성 설정 실패", exc_info=True)


def recommended_window_size(available_width: int, available_height: int) -> tuple[int, int]:
    """Return a stable logical window size that fits the current work area.

    The maximum keeps the interface from becoming excessively stretched on 4K
    and ultrawide displays.  The lower bound is used only when the monitor has
    enough room; very small work areas always win so the window stays visible.
    """
    width = max(640, int(available_width or 0))
    height = max(480, int(available_height or 0))
    safe_width = max(640, width - 32)
    safe_height = max(480, height - 32)
    target_width = min(1360, max(960, round(width * 0.88)))
    target_height = min(900, max(640, round(height * 0.88)))
    return min(target_width, safe_width), min(target_height, safe_height)


def apply_window_size_policy(win) -> tuple[int, int]:
    """Resize a window for its monitor without applying an artificial UI zoom."""
    try:
        from PyQt6.QtGui import QGuiApplication

        screen = win.screen() if hasattr(win, "screen") else None
        screen = screen or QGuiApplication.primaryScreen()
        if screen is None:
            size = (1280, 800)
        else:
            available = screen.availableGeometry()
            size = recommended_window_size(available.width(), available.height())
        min_width = min(760, size[0])
        min_height = min(560, size[1])
        win.setMinimumSize(min_width, min_height)
        win.resize(*size)
        return size
    except Exception:
        logger.debug("모니터 맞춤 창 크기 적용 실패", exc_info=True)
        win.resize(1280, 800)
        return 1280, 800


def center_window(win) -> None:
    """창을 기본 모니터 작업영역 중앙에 배치(화면 밖으로 나가지 않도록)."""
    try:
        from PyQt6.QtGui import QGuiApplication
        screen = None
        if hasattr(win, "screen"):
            screen = win.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        w = win.width() or win.sizeHint().width()
        h = win.height() or win.sizeHint().height()
        x = avail.x() + max(0, (avail.width() - w) // 2)
        y = avail.y() + max(0, (avail.height() - h) // 2)
        win.move(x, y)
    except Exception:
        pass
