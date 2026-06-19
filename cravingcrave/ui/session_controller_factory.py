"""Builds a SessionController wired to the current context (keeps MainWindow lean)."""

from __future__ import annotations

from ..session.session_controller import SessionController


def build_controller(context, patient, substance: str, exposure_cues, loop: bool = False):
    return SessionController(
        repos=context.repos,
        config=context.config,
        patient=patient,
        clinician=context.clinician,
        substance=substance,
        exposure_cues=exposure_cues,
        loop=loop,
    )
