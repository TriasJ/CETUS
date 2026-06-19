# scripts/ — developer & QA helpers

Not part of the shipped app. Run from the project root with the venv Python.

| Script | Purpose |
|---|---|
| `functional_test.py` | End-to-end functional test against the real media library (PASS/FAIL report). |
| `grade_media.py` | Apply the default appetitive-intensity grade (renames cues `g01…gNN`). |
| `montage.py <category>` | Build a labeled contact sheet of a media category (for grading/review). |
| `make_screenshots.py` | Render the core screens to `docs/screenshots/`. |
| `demo_real_media.py` | Screenshot exposure + gallery using the real media. |
| `demo_sounds.py` | Screenshot the ambient selector + audio-cue placeholder. |
| `demo_video.py` | Verify a real video cue plays (`hasVideo`) + screenshot. |
| `demo_admin.py` | Screenshot the admin recovery dialog. |

For end-user content acquisition (CC images/sounds/video, Gemini), see `../tools/`.
One-off diagnostics that have served their purpose live in `../_backup/scripts/`.
