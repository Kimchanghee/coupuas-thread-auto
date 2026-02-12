import main
import io


class _StreamWithoutBuffer:
    pass


class _StreamWithBuffer:
    def __init__(self):
        self.buffer = io.BytesIO()


class _FakeMainWindow:
    def __init__(self):
        self.visible = False
        self._auth_data = None
        self._login_ref = None

    def show(self):
        self.visible = True


def test_to_utf8_text_stream_preserves_stream_without_buffer():
    stream = _StreamWithoutBuffer()
    converted = main._to_utf8_text_stream(stream)
    assert converted is stream


def test_to_utf8_text_stream_skips_non_standard_stream():
    stream = _StreamWithBuffer()
    converted = main._to_utf8_text_stream(stream, std_stream=object())
    assert converted is stream


def test_to_utf8_text_stream_wraps_standard_stream():
    stream = _StreamWithBuffer()
    converted = main._to_utf8_text_stream(stream, std_stream=stream)
    assert converted is not stream
    assert converted.encoding.lower() == "utf-8"
    converted.detach()


def test_create_main_window_sets_auth_and_keeps_login_reference():
    login_window = object()
    auth_result = {"token": "abc123"}

    main_window = main._create_main_window(
        login_window,
        auth_result,
        main_window_cls=_FakeMainWindow,
    )

    assert main_window.visible is True
    assert main_window._auth_data == auth_result
    assert main_window._login_ref is login_window
