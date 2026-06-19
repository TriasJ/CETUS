"""The four Urge-Specific Coping Skills (USCS), Monti / Mellentin protocol.

Each step references an i18n key rather than literal Spanish, so the UI resolves
the displayed text and the clinical sequence stays language-independent and
testable. Order matters: name the affect first, then the two cognitive
restructuring moves, then commit to an alternative behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import CopingSkill


@dataclass(frozen=True)
class CopingStep:
    skill: CopingSkill
    title_key: str    # i18n key for the short step title
    prompt_key: str   # i18n key for the guiding prompt


USCS_STEPS: tuple[CopingStep, ...] = (
    CopingStep(CopingSkill.NAME_FEELING, "uscs.name_feeling.title", "uscs.name_feeling.prompt"),
    CopingStep(CopingSkill.RECALL_NEGATIVE, "uscs.recall_negative.title", "uscs.recall_negative.prompt"),
    CopingStep(CopingSkill.RECALL_BENEFIT, "uscs.recall_benefit.title", "uscs.recall_benefit.prompt"),
    CopingStep(CopingSkill.ALTERNATIVE_ACTION, "uscs.alternative_action.title", "uscs.alternative_action.prompt"),
)
