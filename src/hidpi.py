# -*- coding: utf-8 -*-
"""
High-DPI / 화면 맞춤 스케일 유틸.

어떤 모니터 해상도·배율(100/125/150%)·작은 노트북 화면에서도
UI가 "동일한 비율"로 보이고, 창이 화면을 벗어나 텍스트/버튼이
잘리는 문제가 없도록 보장한다.

핵심 아이디어:
- 절대좌표(setGeometry) + 고정크기 창은 큰 화면 기준(1280x800)으로
  만들어져 있어, 작은/고배율 화면에선 아래쪽이 잘린다.
- QApplication 생성 "전에" 화면 작업영역에 맞춘 글로벌 스케일
  팩터(QT_SCALE_FACTOR)를 계산해 적용하면, 페인팅/폰트/좌표가
  한꺼번에 동일 비율로 축소되어 어디서나 같은 모습으로 들어맞는다.

모든 함수는 실패 시 조용히 무시(=축소 없음)하여 항상 안전하다.
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
    - 하이DPI 스케일 환경변수 설정
    - 작은/고배율 화면이면 화면 맞춤 글로벌 스케일(QT_SCALE_FACTOR) 적용
    - 분수 배율(125/150%)도 반올림 없이 그대로 반영(PassThrough)
    """
    if sys.platform == "win32":
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        # 사용자가 직접 지정한 QT_SCALE_FACTOR는 존중
        if "QT_SCALE_FACTOR" not in os.environ:
            factor = compute_fit_scale_factor()
            if factor < 0.999:
                os.environ["QT_SCALE_FACTOR"] = f"{factor:.3f}"
                logger.info("화면 맞춤 UI 스케일 적용: %.3f", factor)

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
