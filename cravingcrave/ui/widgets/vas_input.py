"""Abstract base for VAS craving-rating input widgets and factory function.

Every VAS display mode (slider, circles, stars) implements the same four-method
contract so ``VasPrompt`` and the accessibility input filter work transparently
regardless of the chosen visual style.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget


class AbstractVasInput(QWidget):
    """Contract for all VAS display modes.

    Every concrete mode must emit ``valueChanged`` on any change and implement
    the four manipulation methods so the prompt overlay and the accessibility
    input filter work transparently.
    """

    valueChanged = Signal(int)

    def __init__(self, vas_max: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vas_max = vas_max

        # Shared numeric readout — every mode shows the current number prominently.
        self.value_label = QLabel("0")
        self.value_label.setObjectName("Big")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def value(self) -> int:
        raise NotImplementedError

    def set_value(self, v: int) -> None:
        raise NotImplementedError

    def nudge(self, delta: int) -> None:
        self.set_value(self.value() + delta)

    def reset(self) -> None:
        self.set_value(0)

    def _clamp(self, v: int) -> int:
        return max(0, min(self.vas_max, v))


def create_vas_input(
    mode: str, vas_max: int = 10, parent: QWidget | None = None,
) -> AbstractVasInput:
    """Factory: create the VAS input widget for the given display mode."""
    if mode == "circles":
        from .vas_circles import CirclesVasInput
        return CirclesVasInput(vas_max, parent)
    if mode == "stars":
        from .vas_stars import StarsVasInput
        return StarsVasInput(vas_max, parent)
    from .vas_slider import SliderVasInput
    return SliderVasInput(vas_max, parent)
