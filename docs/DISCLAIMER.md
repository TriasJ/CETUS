# Clinical & safety disclaimer

CETUS is an **adjunct tool to support clinician-delivered therapy**. It is **not**:

- a medical device,
- a standalone or self-guided treatment,
- a diagnostic instrument,
- a substitute for professional clinical judgment or care.

## Evidence

The evidence base for **non-VR digital cue exposure therapy (CET)** is **mixed-to-null**
in rigorous randomized controlled trials. The most directly comparable purpose-built app
(Mellentin et al. 2019) was non-inferior to in-person group CET but **did not** improve
drinking outcomes beyond CBT. Pooled findings for adjacent approaches are heterogeneous.
Treat all in-app metrics as **descriptive and exploratory** — sample sizes per patient
are small and no statistical inference is implied.

## Risks

Deliberate exposure to substance cues can **provoke craving** and may carry **relapse
risk**, especially for vulnerable patients. Some evidence (e.g. Ekhtiari 2022) raises the
possibility that certain conditions can blunt within-session habituation. Use only:

- with informed patient **consent** (the app gates each session on it),
- under **direct professional supervision**,
- with a **safety plan** and the **ALTO** (STOP) button + crisis contacts configured
  (Ajustes → contacts).

## Data & privacy

All data is stored **locally** (SQLite in `data/`). Patient records use a **pseudonymous
code**; CSV/PDF exports never put names in filenames. Protect the machine and the `data/`
folder — they may contain PII. Do not commit `data/` to version control.

## Media & licensing

Cue media are the responsibility of the deploying clinic. Use only Creative-Commons or
owned media and verify clinical appropriateness. Some methamphetamine cues shipped during
development were AI-generated (see `media/meth/_provenance.txt`); review before use.

No warranty of clinical efficacy or safety is made or implied. The authors accept no
liability for clinical use. See `LICENSE`.
