# -*- coding: utf-8 -*-
"""
픽셀 단위 자동 검수 — 모든 페이지 위젯의 boundary/겹침/텍스트 너비 부족 자동 감지.

검사 항목:
  A. 자식 위젯이 부모 rect를 벗어나는지 (잘림)
  B. 같은 부모 안 형제 위젯끼리 겹치는지 (overlap)
  C. QLabel/QPushButton/QCheckBox의 텍스트 sizeHint가 실제 width보다 큰지 (텍스트 잘림)
"""
import sys, os, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QCheckBox, QLineEdit,
    QSpinBox, QTextEdit, QPlainTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPalette, QColor, QFontMetrics

from src.theme import Colors, global_stylesheet, resolve_fonts
from src.main_window import MainWindow


# 검사 대상 위젯 타입 (자체 paintEvent로 그리는 SectionFrame, HeaderBar 등은 제외)
TEXTUAL_TYPES = (QLabel, QPushButton, QCheckBox, QLineEdit, QSpinBox)


def widget_id(w):
    name = w.objectName() or ""
    txt = ""
    if hasattr(w, "text"):
        try:
            txt = w.text() or ""
        except Exception:
            pass
    txt = txt.replace("\n", " ").strip()[:30]
    return f"{type(w).__name__}({name!r}|{txt!r})"


def check_boundary(widget, parent, parent_rect, issues):
    """자식이 부모 rect 안에 있는지."""
    g = widget.geometry()
    if g.left() < 0 or g.top() < 0 or g.right() > parent_rect.right() or g.bottom() > parent_rect.bottom():
        # SectionFrame 같은 페이지 직속 카드의 부모가 ScrollArea content면 OK
        # 진짜 문제는 카드 안 자식이 카드 밖으로 나가는 경우
        issues.append(
            f"BOUNDARY  {widget_id(widget)}  geom={g.x()},{g.y()},{g.width()}x{g.height()}"
            f"  parent={widget_id(parent)} rect={parent_rect.width()}x{parent_rect.height()}"
        )


def check_text_width(widget, issues):
    """QLabel/QPushButton/QCheckBox 텍스트가 위젯 너비를 넘는지."""
    if not isinstance(widget, TEXTUAL_TYPES):
        return
    txt = ""
    try:
        txt = widget.text() or ""
    except Exception:
        return
    # placeholder도 입력란이면 검사
    if isinstance(widget, QLineEdit) and not txt:
        txt = widget.placeholderText() or ""
    if not txt or txt.startswith("<"):  # rich-text는 sizeHint 부정확
        return
    fm = QFontMetrics(widget.font())
    needed = fm.horizontalAdvance(txt)
    # 패딩 예상치 — 실제 global stylesheet의 QPushButton padding 11px 28px 기준 좌우 합 56px
    # ghost class는 9px 14px → 28px. 안전을 위해 기본은 큰 값으로.
    if isinstance(widget, QPushButton):
        # ghost class면 28px, 기본 56px
        try:
            cls = widget.property("class")
        except Exception:
            cls = None
        pad = 36 if cls == "ghost" else 60
    elif isinstance(widget, QCheckBox):
        pad = 30  # indicator + spacing
    elif isinstance(widget, QLineEdit):
        # spinbox 내부 lineedit는 spinbox 자체 padding을 상속받지 않음 — 별도 처리
        if widget.objectName() == "qt_spinbox_lineedit":
            pad = 4   # spinbox lineedit 자체는 거의 padding 없음
        else:
            pad = 32
    else:
        pad = 8
    have = widget.width()
    if needed + pad > have + 2:
        issues.append(
            f"TEXT_FIT  {widget_id(widget)}  text-pixels={needed}  width={have}  needed={needed + pad}"
        )


def check_overlap_among_siblings(parent, parent_name, issues):
    """같은 부모 안 형제 위젯끼리 rect overlap (visible 위젯만)."""
    children = [c for c in parent.children() if isinstance(c, QWidget) and c.isVisible()]
    n = len(children)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = children[i], children[j]
            ga, gb = a.geometry(), b.geometry()
            # 교집합
            inter = ga.intersected(gb)
            if inter.isValid() and inter.width() > 0 and inter.height() > 0:
                # 정상적인 stacked 조합 (icon_bg 위에 icon_label 같은 의도된 stacking) 무시:
                # 둘 다 같은 위치/크기면 의도된 stacking으로 보고 건너뜀
                if ga == gb:
                    continue
                # 정상적인 라벨+아이콘 같은 작은 겹침은 무시 (5px 이하)
                if inter.width() < 4 and inter.height() < 4:
                    continue
                issues.append(
                    f"OVERLAP   in {parent_name}  "
                    f"{widget_id(a)} {ga.x()},{ga.y()},{ga.width()}x{ga.height()}  ⇆  "
                    f"{widget_id(b)} {gb.x()},{gb.y()},{gb.width()}x{gb.height()}  "
                    f"inter={inter.width()}x{inter.height()}"
                )


def walk(widget, parent_name, issues, depth=0):
    # boundary 검사 (자식이 위젯 안에 들어 있는지)
    for child in widget.children():
        if not isinstance(child, QWidget):
            continue
        if not child.isVisible():
            continue
        check_boundary(child, widget, widget.rect(), issues)
        check_text_width(child, issues)
    # 형제 겹침
    check_overlap_among_siblings(widget, parent_name, issues)
    # 재귀
    for child in widget.children():
        if isinstance(child, QWidget) and child.isVisible():
            walk(child, f"{parent_name}>{type(child).__name__}", issues, depth + 1)


def main():
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(Colors.BG_DARK))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_INPUT))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_CARD))
    pal.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_ELEVATED))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    app.setPalette(pal)
    resolve_fonts()
    app.setStyleSheet(global_stylesheet())

    win = MainWindow()
    win.show()
    win.activateWindow()
    app.processEvents()

    for page_idx in (0, 1, 2):
        win._switch_page(page_idx)
        app.processEvents()
        print(f"\n========== PAGE {page_idx} ==========")
        issues = []
        walk(win, "MainWindow", issues)
        if issues:
            for it in issues:
                print(it)
            print(f"  TOTAL ISSUES: {len(issues)}")
        else:
            print("  CLEAN ✓")

    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
