import os

from PyQt6.QtWidgets import QApplication, QLabel

from src.theme import (
    Breakpoints,
    Colors,
    ControlHeight,
    Radius,
    Spacing,
    Typography,
    global_stylesheet,
)
from src.ui_components import (
    Card,
    InlineHelpPanel,
    PipelineRail,
    SectionCard,
    StatusPill,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    return QApplication.instance() or QApplication([])


def _contrast_ratio(foreground: str, background: str) -> float:
    def luminance(hex_color: str) -> float:
        channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    first, second = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def test_editorial_control_room_tokens_match_the_blueprint():
    assert {
        "ink": Colors.INK,
        "porcelain": Colors.PORCELAIN,
        "paper": Colors.PAPER,
        "slate": Colors.SLATE,
        "line": Colors.LINE,
        "signal": Colors.SIGNAL_TEAL,
        "deep": Colors.DEEP_TEAL,
        "amber": Colors.AMBER,
        "coral": Colors.CORAL,
        "emerald": Colors.EMERALD,
        "sky": Colors.SKY,
    } == {
        "ink": "#101C24",
        "porcelain": "#F4F1EA",
        "paper": "#FFFEFB",
        "slate": "#52636D",
        "line": "#D7DDD9",
        "signal": "#0D7C84",
        "deep": "#075D63",
        "amber": "#F2A93B",
        "coral": "#D9544D",
        "emerald": "#27856A",
        "sky": "#DCEFF1",
    }
    assert Colors.BG_DARK == Colors.PORCELAIN
    assert Colors.BG_CARD == Colors.PAPER
    assert Colors.BG_SIDEBAR == Colors.INK
    assert Colors.ACCENT == Colors.SIGNAL_TEAL
    assert Colors.SUCCESS == Colors.EMERALD
    assert Colors.WARNING == Colors.AMBER
    assert Colors.ERROR == Colors.CORAL

    assert (
        Spacing.XS,
        Spacing.SM,
        Spacing.MD,
        Spacing.LG,
        Spacing.XL,
        Spacing.XXL,
        Spacing.XXXL,
    ) == (4, 8, 12, 16, 24, 32, 48)
    assert (Radius.INPUT, Radius.CARD, Radius.HERO) == ("8px", "12px", "16px")
    assert (
        ControlHeight.ICON,
        ControlHeight.INPUT,
        ControlHeight.PRIMARY,
        ControlHeight.FIXED_FOOTER,
    ) == (40, 44, 48, 64)
    assert (
        Typography.CAPTION_SIZE,
        Typography.BODY_SIZE,
        Typography.SECTION_SIZE,
        Typography.PAGE_TITLE_SIZE,
        Typography.DISPLAY_SIZE,
    ) == (12, 14, 17, 22, 26)
    assert Typography.FAMILY_MONO in Typography.MONO
    assert Breakpoints.navigation_width(1360) == 240
    assert Breakpoints.navigation_width(900) == 190
    assert Breakpoints.navigation_width(760) == 72
    assert Breakpoints.DPI_QA_SCALES == (100, 125, 150, 175, 200)


def test_inverse_navigation_text_meets_body_contrast():
    assert _contrast_ratio(Colors.TEXT_ON_INK_MUTED, Colors.INK) >= 4.5
    assert _contrast_ratio(Colors.TEXT_ON_INK, Colors.SIGNAL_TEAL) >= 4.5


def test_global_styles_include_accessible_focus_and_disabled_states():
    stylesheet = global_stylesheet()
    assert "font-family: Pretendard" in stylesheet or Typography.FAMILY in stylesheet
    assert "QPushButton:focus" in stylesheet
    assert "QPushButton:disabled" in stylesheet
    assert "QLineEdit:focus" in stylesheet
    assert "QLineEdit:disabled" in stylesheet
    assert "QComboBox:focus" in stylesheet
    assert Colors.SIGNAL_TEAL in stylesheet
    assert Colors.PORCELAIN in stylesheet


def test_editorial_cards_and_status_pills_keep_public_content_contracts():
    app = _app()
    card = Card(accessible_name="실행 요약")
    section = SectionCard("연결 설정", "Threads 계정과 연결 상태를 관리합니다.")
    help_panel = InlineHelpPanel("도움말", "첫 번째 안내")
    pill = StatusPill("사용 가능", "available")
    try:
        margins = card.content_layout.contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            24,
            24,
            24,
            24,
        )
        card.set_compact(True)
        margins = card.content_layout.contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            16,
            16,
            16,
            16,
        )

        body_item = QLabel("본문")
        section.add_widget(body_item)
        assert section.body_layout.indexOf(body_item) == 0
        assert section.accessibleName() == "연결 설정"
        section.set_subtitle("")
        assert not section.subtitle_label.isVisible()

        help_panel.set_content("새 도움말", "두 번째 안내")
        assert help_panel.title_label.text() == "새 도움말"
        assert help_panel.body_label.text() == "두 번째 안내"

        assert pill.status == "success"
        assert pill.height() == 28
        pill.set_status("retry", "재시도")
        assert pill.status == "warning"
        assert pill.text() == "재시도"
        pill.set_status("not-a-state")
        assert pill.status == "neutral"
    finally:
        for widget in (card, section, help_panel, pill):
            widget.deleteLater()
        app.processEvents()


def test_pipeline_rail_reports_each_stage_and_supports_complete_and_error_states():
    app = _app()
    rail = PipelineRail()
    changes = []
    rail.progressChanged.connect(changes.append)
    rail.resize(760, 96)
    rail.show()
    try:
        app.processEvents()
        assert rail.stages == ("링크 분석", "콘텐츠 생성", "Threads 업로드", "완료")
        assert rail.stage_count == 4
        assert len(rail._stage_nodes) == 4
        assert len(rail._connectors) == 3
        assert rail._stage_nodes[0].text() == "1"
        assert "진행 중" in rail.accessibleDescription()

        rail.set_current_stage(2)
        app.processEvents()
        assert changes == [2]
        assert [node.text() for node in rail._stage_nodes[:2]] == ["✓", "✓"]
        assert rail._stage_nodes[2].text() == "3"
        assert "Threads 업로드 진행 중" in rail.accessibleDescription()

        rail.set_current_stage(2, error=True)
        assert rail._stage_nodes[2].text() == "!"
        assert "Threads 업로드 오류" in rail.accessibleDescription()

        rail.reset()
        assert rail.current_index == 0
        rail.set_step(0, "complete")
        assert rail.current_index == 1
        rail.set_step(1, "failed")
        assert rail._stage_nodes[1].text() == "!"

        rail.complete()
        assert all(node.text() == "✓" for node in rail._stage_nodes)
        assert rail.current_index == 4
    finally:
        rail.close()
        rail.deleteLater()
        app.processEvents()
