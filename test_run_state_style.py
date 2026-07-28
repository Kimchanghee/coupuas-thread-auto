from pathlib import Path


def test_run_state_banner_is_scoped_and_borderless():
    source = (Path(__file__).parent / "src" / "main_window.py").read_text(
        encoding="utf-8"
    )

    assert 'self._run_state_frame.setObjectName("runStateFrame")' in source
    assert source.count('f"QFrame#runStateFrame {{"') == 2

    style_starts = [
        index
        for index in range(len(source))
        if source.startswith("self._run_state_frame.setStyleSheet(", index)
    ]
    assert len(style_starts) == 2
    for start in style_starts:
        style = source[start : source.index("\n        )", start)]
        assert 'f"  border: none;"' in style
        assert "border: 1px" not in style

    for label_name in ("title", "main", "detail", "next"):
        label_start = source.index(f"self._run_state_{label_name}.setStyleSheet(")
        label_style = source[label_start : source.index("\n        )", label_start)]
        assert "border: none" in label_style
