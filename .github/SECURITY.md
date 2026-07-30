# Security & privacy policy

CETUS is a **local-only clinical-support tool** that stores patient and clinician data on
the machine it runs on. Security and privacy issues are treated seriously.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security or privacy problems.** Report
privately to the maintainer (the repository owner) via a GitHub private security advisory
(Security → *Report a vulnerability*) or direct contact. Include steps to reproduce and the
affected version. We aim to acknowledge within a reasonable time and coordinate a fix and
disclosure.

## Data handling (by design)

- **All data is local.** Patient/clinician records live in a SQLite database under `data/`
  next to the app. Nothing is sent to the network at runtime — content-acquisition tools in
  `tools/` are offline utilities, never imported by the app.
- **Pseudonymity.** Patients are identified by a clinic-chosen **code**, not their name.
  CSV/PDF exports never place a name in the filename.
- **Passwords** are stored as salted **PBKDF2** hashes, never plaintext.
- **The `data/` folder must never be committed** to version control (it is git-ignored).

## Deployment guidance

- Protect the host machine and the `data/` folder with OS-level access controls; the SQLite
  file is the real trust boundary for this local app.
- Change the default admin-recovery key (`cetus-admin`) in *Ajustes* per deployment.
- Rotate any API keys used with `tools/` (Gemini, Freesound) if they were ever exposed.

## Scope

CETUS is **not a medical device** and makes no warranty of clinical efficacy or safety
(see `LICENSE` and `docs/DISCLAIMER.md`). Security reports about data confidentiality,
authentication, and local privilege are in scope; clinical-efficacy claims are not a
security matter.
