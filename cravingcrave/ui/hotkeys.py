"""Central hotkey registry + the keyboard-only accessibility input filter.

Two things live here:

* A **registry** of every rebindable action (id, default key, i18n label, scope) plus
  helpers to resolve per-action overrides from the ``app_setting`` store. Screens build
  their ``QShortcut`` objects from the *resolved* bindings instead of hard-coding keys, so
  a clinic can remap them in Settings.
* ``AccessibilityInput`` — an application-level event filter that implements the
  keyboard-only exposure scheme for a disability keyboard (Enter, +, −, arrows, 0–9):
  arrows switch cues, digits ``1/2/3`` select the size/blur/dim axis, ``+``/``−`` adjust
  the selected axis, ``0`` toggles mute, and while the VAS prompt is open digits set the
  rating and Enter submits. It is installed only while accessibility mode is ON.

Adding an action = add one ``HotkeyAction`` to ``ACTIONS`` (and its i18n label). Keys are
stored/compared as ``QKeySequence`` *PortableText* so defaults, settings and captured keys
all agree.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence

SETTING_PREFIX = "hotkey."            # per-action override key in app_setting
KBMODE_SETTING = "accessibility_kbmode"


class Scope(enum.Enum):
    GLOBAL = "global"        # window-level (panic/help/fullscreen)
    EXPOSURE = "exposure"    # standard exposure shortcuts
    ACCESS = "access"        # keyboard-only accessibility preset


@dataclass(frozen=True)
class HotkeyAction:
    id: str
    default_key: str         # QKeySequence PortableText, e.g. "Right", "Shift+T", "+", "1"
    label_key: str           # i18n key
    scope: Scope
    rebindable: bool = True   # panic is False (safety-critical)


# Disability-keyboard keyset the ACCESS preset is restricted to when rebinding.
ACCESSIBILITY_KEYSET = frozenset(
    {str(d) for d in range(10)} | {"+", "-", "Left", "Right", "Up", "Down", "Return", "Enter"}
)

# The registry. GLOBAL + EXPOSURE defaults reproduce the pre-0.4.0 bindings exactly.
ACTIONS: tuple[HotkeyAction, ...] = (
    # --- global (MainWindow) ---
    HotkeyAction("global.panic", "Esc", "hotkey.panic", Scope.GLOBAL, rebindable=False),
    HotkeyAction("global.help", "F1", "hotkey.help", Scope.GLOBAL),
    HotkeyAction("global.fullscreen", "F11", "hotkey.fullscreen", Scope.GLOBAL),
    # --- standard exposure shortcuts ---
    HotkeyAction("exposure.prev_cue", "Left", "hotkey.prev_cue", Scope.EXPOSURE),
    HotkeyAction("exposure.next_cue", "Right", "hotkey.next_cue", Scope.EXPOSURE),
    HotkeyAction("exposure.size_down", "T", "hotkey.size_down", Scope.EXPOSURE),
    HotkeyAction("exposure.size_up", "Shift+T", "hotkey.size_up", Scope.EXPOSURE),
    HotkeyAction("exposure.blur_up", "D", "hotkey.blur_up", Scope.EXPOSURE),
    HotkeyAction("exposure.blur_down", "Shift+D", "hotkey.blur_down", Scope.EXPOSURE),
    HotkeyAction("exposure.dim_up", "O", "hotkey.dim_up", Scope.EXPOSURE),
    HotkeyAction("exposure.dim_down", "Shift+O", "hotkey.dim_down", Scope.EXPOSURE),
    HotkeyAction("exposure.mute", "M", "hotkey.mute", Scope.EXPOSURE),
    HotkeyAction("exposure.reset", "R", "hotkey.reset", Scope.EXPOSURE),
    HotkeyAction("exposure.loop", "L", "hotkey.loop", Scope.EXPOSURE),
    # --- accessibility preset (handled by the event filter) ---
    HotkeyAction("access.axis_size", "1", "hotkey.axis_size", Scope.ACCESS),
    HotkeyAction("access.axis_blur", "2", "hotkey.axis_blur", Scope.ACCESS),
    HotkeyAction("access.axis_dim", "3", "hotkey.axis_dim", Scope.ACCESS),
    HotkeyAction("access.mute", "0", "hotkey.access_mute", Scope.ACCESS),
    HotkeyAction("access.intensity_inc", "+", "hotkey.intensity_inc", Scope.ACCESS),
    HotkeyAction("access.intensity_dec", "-", "hotkey.intensity_dec", Scope.ACCESS),
    HotkeyAction("access.vas_submit", "Return", "hotkey.vas_submit", Scope.ACCESS),
)

_BY_ID = {a.id: a for a in ACTIONS}


def default_bindings() -> dict[str, str]:
    return {a.id: a.default_key for a in ACTIONS}


def resolve_bindings(settings) -> dict[str, str]:
    """Defaults overlaid with any per-action override stored in ``app_setting``.

    An empty/missing override falls back to the action's default."""
    out = default_bindings()
    for a in ACTIONS:
        override = settings.get(SETTING_PREFIX + a.id)
        if override:
            out[a.id] = override
    return out


def save_binding(settings, action_id: str, keyseq: str) -> None:
    settings.set(SETTING_PREFIX + action_id, keyseq)


def reset_bindings(settings) -> None:
    """Clear every override so all actions fall back to their defaults."""
    for a in ACTIONS:
        settings.set(SETTING_PREFIX + a.id, "")


def actions_in(*scopes: Scope) -> list[HotkeyAction]:
    return [a for a in ACTIONS if a.scope in scopes]


def normalize_key(event) -> str:
    """A stable PortableText-ish token for a KeyPress, robust for the disability keys.

    Matches the tokens stored as defaults ("1", "Left", "Return", "+", "-") without
    depending on modifier quirks (e.g. numpad ``+`` or ``Shift+=``)."""
    key = event.key()
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)
    named = {
        Qt.Key.Key_Left: "Left", Qt.Key.Key_Right: "Right",
        Qt.Key.Key_Up: "Up", Qt.Key.Key_Down: "Down",
        Qt.Key.Key_Return: "Return", Qt.Key.Key_Enter: "Return",
        Qt.Key.Key_Plus: "+", Qt.Key.Key_Minus: "-",
    }
    if key in named:
        return named[key]
    text = event.text()
    if text in ("+", "-"):
        return text
    return QKeySequence(event.keyCombination()).toString(QKeySequence.SequenceFormat.PortableText)


def build_key_index(resolved: dict[str, str], action_ids: list[str]) -> dict[str, str]:
    """token -> action_id for the given actions (used by the event filter)."""
    index: dict[str, str] = {}
    for aid in action_ids:
        index[resolved[aid]] = aid
    return index


# Axis selected by the ACCESS digit actions.
_AXIS_FOR_ACTION = {
    "access.axis_size": "size",
    "access.axis_blur": "blur",
    "access.axis_dim": "dim",
}
_STEP = 10  # percent per +/- press, matching the standard shortcuts


class AccessibilityInput(QObject):
    """Application-level key filter implementing the keyboard-only exposure scheme.

    Duck-typed on the exposure screen (``screen``): it uses ``_prev_cue``/``_next_cue``,
    ``intensity`` (IntensityControls), ``vas_prompt`` (VasPrompt) and the coping/gallery
    overlays. Returns ``False`` for any key it does not own so global shortcuts (Esc panic,
    F1, F11) always fire.
    """

    def __init__(self, screen, resolved: dict[str, str]) -> None:
        super().__init__(screen)
        self.screen = screen
        self._active_axis: str | None = None
        # Cue nav (from EXPOSURE scope) + the ACCESS actions handled outside the VAS prompt.
        nav_and_axes = [
            "exposure.prev_cue", "exposure.next_cue",
            "access.axis_size", "access.axis_blur", "access.axis_dim",
            "access.mute", "access.intensity_inc", "access.intensity_dec",
        ]
        self._index = build_key_index(resolved, nav_and_axes)
        self._vas_submit = resolved["access.vas_submit"]

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        scr = self.screen
        # 1) A VAS prompt is open -> digits/±/Enter drive the rating (digits mean
        #    "rating" here). `_prompt_open` is the screen's authoritative flag for any
        #    baseline/periodic/peak/endpoint prompt.
        if scr._prompt_open:
            return self._handle_vas(event)
        # 2) Coping/gallery open -> let the panel handle keys (mirrors the periodic-VAS guard).
        if scr.coping_panel.isVisible() or scr.gallery.isVisible():
            return False
        token = normalize_key(event)
        action = self._index.get(token)
        if action is None:
            return False        # Esc/F1/F11/unknown -> pass through to global shortcuts
        return self._dispatch(action, event)

    def _dispatch(self, action: str, event) -> bool:
        scr = self.screen
        if action == "exposure.prev_cue":
            scr._prev_cue(); return True
        if action == "exposure.next_cue":
            scr._next_cue(); return True
        if action in _AXIS_FOR_ACTION:
            self._active_axis = _AXIS_FOR_ACTION[action]
            scr.intensity.highlight_axis(self._active_axis)
            return True
        if action == "access.mute":
            if not event.isAutoRepeat():
                scr.intensity.toggle_mute()
            return True
        if action in ("access.intensity_inc", "access.intensity_dec"):
            delta = _STEP if action == "access.intensity_inc" else -_STEP
            if self._active_axis == "size":
                scr.intensity.step_size(delta)
            elif self._active_axis == "blur":
                scr.intensity.step_blur(delta)
            elif self._active_axis == "dim":
                scr.intensity.step_dim(delta)
            else:
                scr.flash_axis_hint()   # no axis selected yet
            return True
        return False

    def _handle_vas(self, event) -> bool:
        scr = self.screen
        key = event.key()
        token = normalize_key(event)
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            scr.vas_prompt.set_value(int(chr(key)))
            return True
        if token == "+":
            scr.vas_prompt.set_value(scr.context.config.vas_max)
            return True
        if token == "-":
            scr.vas_prompt.nudge(-1)
            return True
        if token == self._vas_submit:
            scr.vas_prompt.submit()
            return True
        return False   # Esc etc. pass through (panic still works over the overlay)
