"""End-to-end functional test against the REAL media library.

Drives the actual app classes (offscreen) through every feature and prints a
PASS/FAIL report. Run: python scripts/functional_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cravingcrave.app  # noqa: F401,E402  (runs media-backend fix on import)
from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.domain.models import CravingRating, CueConfig, Patient, RatingKind, Session  # noqa: E402
from cravingcrave.domain import playlist as playlist_rules  # noqa: E402
from cravingcrave.services import export  # noqa: E402
from cravingcrave.session.session_controller import SessionController  # noqa: E402
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.main_window import MainWindow  # noqa: E402
from cravingcrave.ui.screens.exposure_screen import ExposureScreen  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 12.0
        return self.t


RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        try:
            detail = fn() or ""
            RESULTS.append((name, True, detail))
        except AssertionError as exc:
            RESULTS.append((name, False, f"assertion: {exc}"))
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
    return deco


def submit_vas(screen, value):
    screen.vas_prompt.slider.slider.setValue(value)
    screen.vas_prompt._submit()


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp())
    cfg = AppConfig(data_dir=tmp / "data", media_root=ROOT / "media", db_path=tmp / "data" / "cc.db")
    ctx = AppContext.create(cfg)

    # ---- 1. media discovery ----
    @check("media library discovery (images/video/sound across categories)")
    def _():
        a_img = [m for m in ctx.media.by_category("alcohol") if m.media_type == "image"]
        a_vid = [m for m in ctx.media.by_category("alcohol") if m.media_type == "video"]
        meth = ctx.media.by_category("meth")
        snd = ctx.media.by_category("sounds")
        pos = ctx.media.by_category("positive")
        assert len(a_img) >= 5, f"alcohol images={len(a_img)}"
        assert len(a_vid) >= 1, f"alcohol video={len(a_vid)}"
        assert len(meth) >= 1 and len(snd) >= 1 and len(pos) >= 1
        return f"alcohol {len(a_img)}img/{len(a_vid)}vid, meth {len(meth)}, sounds {len(snd)}, positive {len(pos)}"

    # ---- 2. auth ----
    @check("clinician auth (register, reject wrong pw, accept correct)")
    def _():
        c = ctx.auth.register("dra.lopez", "Dra. López", "secret-123")
        assert ctx.auth.login("dra.lopez", "WRONG") is None
        assert ctx.auth.login("dra.lopez", "secret-123").id == c.id
        ctx.clinician = c

    # ---- 3. patient + cue config + graded playlist ----
    state = {}

    @check("patient create + graded cue playlist (ascending intensity)")
    def _():
        p = ctx.repos.patients.create(Patient(code="PT-FT01", primary_substance="alcohol",
                                              created_by=ctx.clinician.id))
        imgs = [m for m in ctx.media.by_category("alcohol") if m.media_type == "image"][:3]
        vids = [m for m in ctx.media.by_category("alcohol") if m.media_type == "video"][:1]
        rank = 0
        for m in imgs + vids:
            ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="alcohol",
                                            media_path=m.path, media_type=m.media_type,
                                            appetitive_rank=rank))
            rank += 1
        cues = ctx.repos.cues.list_for_patient(p.id)
        pl = playlist_rules.build_exposure_playlist(cues)
        ranks = [c.appetitive_rank for c in pl]
        assert ranks == sorted(ranks), f"not ascending: {ranks}"
        state["patient"] = p
        state["cues"] = pl
        return f"{len(pl)} cues, ranks {ranks}"

    # ---- 4. full interactive session (real cues + ambient + video + coping + gallery) ----
    window = MainWindow(ctx)
    window.resize(1180, 760)
    window.show()

    @check("full session: VAS, intensity, ambient, coping, gallery, video cue, habituation")
    def _():
        p = state["patient"]
        cues = state["cues"]
        sounds = ctx.media.by_category("sounds")
        ambient = sounds[0].absolute_path if sounds else None
        positive = [m.absolute_path for m in ctx.media.by_category("positive")]
        controller = SessionController(ctx.repos, cfg, p, ctx.clinician, "alcohol", cues, clock=FakeClock())
        screen = ExposureScreen(window, ctx, controller, positive, ambient_path=ambient)
        window._active_controller = controller
        window._active_exposure = screen

        screen._ask_baseline()
        submit_vas(screen, 7)                                  # baseline -> exposure begins
        assert controller.state.name == "EXPOSURE"
        screen._on_intensity(60, 40, 30, True, "shrink")       # shrink+blur+dim+mute
        if ambient:
            screen.ambient_btn.setChecked(True)                # ambient mute
        screen._mark_peak(); submit_vas(screen, 9)
        screen._open_coping()
        for _i in range(4):                                    # 4 USCS steps
            screen.coping_panel._input.setPlainText("respuesta")
            screen.coping_panel._advance()
        screen._open_gallery(); screen.gallery._close()
        # advance to the video cue (last in the graded list)
        while screen.controller.current_cue() and screen.controller.current_cue().media_type != "video":
            screen._next_cue()
        screen._on_periodic(); submit_vas(screen, 1)
        screen._on_periodic(); submit_vas(screen, 1)           # -> habituation
        assert screen._habituated, "habituation not reached"
        screen._end_clicked(); submit_vas(screen, 1)           # endpoint -> finalize

        s = ctx.repos.sessions.list_for_patient(p.id)[0]
        assert s.end_reason == "habituated", s.end_reason
        assert (s.baseline_vas, s.peak_vas, s.endpoint_vas) == (7, 9, 1)
        assert s.habituation_slope is not None and s.habituation_slope < 0
        ratings = ctx.repos.ratings.list_for_session(s.id)
        coping = ctx.repos.coping.list_for_session(s.id)
        inten = ctx.repos.intensity.list_for_session(s.id)
        assert len(ratings) == 5, f"ratings={len(ratings)}"
        assert len(coping) == 4, f"coping={len(coping)}"
        actions = {e.action for e in inten}
        assert {"shrink", "gallery_open", "gallery_close"} <= actions, actions
        if ambient:
            assert any(e.action == "ambient_mute" and e.muted for e in inten)
        state["session"] = s
        return f"slope={s.habituation_slope:.4f}, ratings={len(ratings)}, coping={len(coping)}, intensity_actions={sorted(actions)}"

    # ---- 5. real video playback ----
    @check("video cue actually decodes (hasVideo)")
    def _():
        from cravingcrave.ui.widgets.cue_view import CueView
        vids = [m for m in ctx.media.by_category("alcohol") if m.media_type == "video"]
        cv = CueView()
        cv.show_video(vids[0].absolute_path)
        deadline = time.time() + 5
        while time.time() < deadline:
            app.processEvents()
            if cv._player and cv._player.hasVideo():
                break
            time.sleep(0.05)
        assert cv._player.hasVideo(), "no video frames decoded"
        return f"duration={cv._player.duration()}ms"

    # ---- 6. CSV export (PII-safe) ----
    @check("CSV export: summary + timeline, no PII, code present")
    def _():
        s = state["session"]
        p = state["patient"]
        sm = export.export_sessions_summary(tmp / "sum.csv", p.code, [s])
        tl = export.export_session_timeline(tmp / "tl.csv", p.code, s,
                                            ctx.repos.ratings.list_for_session(s.id),
                                            ctx.repos.coping.list_for_session(s.id),
                                            ctx.repos.intensity.list_for_session(s.id))
        sum_txt = sm.read_text(encoding="utf-8-sig")
        assert p.code in sum_txt and "habituated" in sum_txt
        fname = export.safe_filename(p.code, "summary")
        assert "/" not in fname and "\\" not in fname
        assert "display_name" not in export.SESSION_COLUMNS
        return f"{sm.name}, {tl.name}"

    # ---- 7. cross-session progress ----
    @check("cross-session progress (2nd session persists, trend data present)")
    def _():
        p = state["patient"]
        cues = state["cues"]
        c2 = SessionController(ctx.repos, cfg, p, ctx.clinician, "alcohol", cues, clock=FakeClock())
        c2.begin()
        c2.record_rating(8, RatingKind.BASELINE)
        c2.start_exposure()
        c2.record_rating(2, RatingKind.PERIODIC)
        from cravingcrave.domain.models import EndReason
        c2.finalize(EndReason.CLINICIAN_STOP, 2)
        sessions = [s for s in ctx.repos.sessions.list_for_patient(p.id) if s.baseline_vas is not None]
        assert len(sessions) >= 2, f"sessions={len(sessions)}"
        return f"{len(sessions)} finished sessions for {p.code}"

    # ---- 8. panic path ----
    @check("panic finalizes session as 'panic' and stops media")
    def _():
        p = ctx.repos.patients.create(Patient(code="PT-FT02", primary_substance="meth",
                                              created_by=ctx.clinician.id))
        meth = ctx.media.by_category("meth")[:1]
        for r, m in enumerate(meth):
            ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path=m.path,
                                            media_type=m.media_type, appetitive_rank=r))
        cues = ctx.repos.cues.list_for_patient(p.id)
        window.start_exposure(p, "meth", cues, [])  # real flow: makes the panic button live
        screen = window._active_exposure
        screen._ask_baseline(); submit_vas(screen, 6)
        window._on_panic()
        s = ctx.repos.sessions.list_for_patient(p.id)[0]
        assert s.end_reason == "panic" and s.ended_at
        return "end_reason=panic"

    # ---- 9. custom substance round-trips end to end ----
    @check("custom substance: add -> folder -> patient/session -> metrics")
    def _():
        from cravingcrave.services import substances as _subs
        from cravingcrave.domain import reports as _reports
        key = _subs.add_custom(ctx.repos.settings, "Cocaína")
        assert key == "cocaina"
        (cfg.media_root / key).mkdir(parents=True, exist_ok=True)
        assert key in ctx.media.category_folders()
        assert _subs.display_name(ctx.repos.settings, key) == "Cocaína"
        # a patient + finished session on the custom substance
        p = ctx.repos.patients.create(Patient(code="PT-FT03", primary_substance=key,
                                              created_by=ctx.clinician.id))
        s = ctx.repos.sessions.create(Session(patient_id=p.id, clinician_id=ctx.clinician.id,
                                              substance=key, consent_given=True, app_version="t"))
        for el, v, k in [(0, 8, "baseline"), (30, 9, "peak"), (90, 2, "endpoint")]:
            ctx.repos.ratings.add(CravingRating(session_id=s.id, elapsed_sec=el, value=v, kind=k))
        s.baseline_vas, s.peak_vas, s.endpoint_vas = 8, 9, 2
        from cravingcrave.domain.models import EndReason as _ER
        s.ended_at = "2026-05-28T00:02:00+00:00"; s.end_reason = _ER.HABITUATED.value
        ctx.repos.sessions.finalize(s)
        m = _reports.session_metrics(ctx.repos.sessions.get(s.id),
                                     ctx.repos.ratings.list_for_session(s.id))
        assert m["cue_reactivity"] == 1 and round(m["pct_reduction"]) == round((9 - 2) / 9 * 100)
        return f"custom '{key}' patient+session ok; reactivity={m['cue_reactivity']}"

    # ---- report ----
    print("\n" + "=" * 78)
    print("CETUS — functional test report")
    print("=" * 78)
    passed = 0
    for name, ok, detail in RESULTS:
        tag = "PASS" if ok else "FAIL"
        passed += ok
        print(f"[{tag}] {name}")
        if detail:
            print(f"       {detail}")
    print("-" * 78)
    print(f"{passed}/{len(RESULTS)} checks passed")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
