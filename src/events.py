"""
공용 이벤트 클래스
"""
from PyQt6.QtCore import QEvent


class LoginStatusEvent(QEvent):
    EventType = QEvent.Type(QEvent.registerEventType())

    def __init__(self, result):
        super().__init__(LoginStatusEvent.EventType)
        self.result = result
