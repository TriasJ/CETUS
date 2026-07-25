"""A button that captures a single keystroke to (re)bind a hotkey."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QPushButton

from ...services.i18n import tr

_MODIFIER_KEYS = {
    Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock,
}


class KeyCaptureButton(QPushButton):
    """Shows a binding; on click, grabs the keyboard and captures the next keystroke.

    Emits ``captured(action_id, keyseq)`` with the key as ``QKeySequence`` PortableText.
    Esc while listening cancels (keeps the old binding)."""

    captured = Signal(str, str)

    def __init__(self, action_id: str, keyseq: str, parent=None) -> None:
        super().__init__(parent)
        self.action_id = action_id
        self._keyseq = keyseq
        self._listening = False
        self._render()
        self.clicked.connect(self._start_listening)

    def set_keyseq(self, keyseq: str) -> None:
        self._keyseq = keyseq
        self._render()

    def _render(self) -> None:
        self.setText(tr("settings.hotkey_press") if self._listening else (self._keyseq or "—"))

    def _start_listening(self) -> None:
        self._listening = True
        self._render()
        self.grabKeyboard()

    def _stop_listening(self) -> None:
        self._listening = False
        self.releaseKeyboard()
        self._render()

    def keyPressEvent(self, event) -> None:
        if not self._listening:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in _MODIFIER_KEYS:
            return  # wait for a non-modifier key
        if key == Qt.Key.Key_Escape:
            self._stop_listening()  # cancel, keep old binding
            return
        seq = QKeySequence(event.keyCombination()).toString(QKeySequence.SequenceFormat.PortableText)
        # Robust tokens for the disability keys (match the registry defaults).
        override = {
            Qt.Key.Key_Left: "Left", Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Up: "Up", Qt.Key.Key_Down: "Down",
            Qt.Key.Key_Return: "Return", Qt.Key.Key_Enter: "Return",
            Qt.Key.Key_Plus: "+", Qt.Key.Key_Minus: "-",
        }
        if key in override:
            seq = override[key]
        elif event.text() in ("+", "-"):
            seq = event.text()
        self._stop_listening()
        if seq:
            self.captured.emit(self.action_id, seq)
