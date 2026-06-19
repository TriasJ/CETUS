# Publishing to GitHub

The repo is prepared but **not** git-initialized (you run git). The `.gitignore` already
excludes all PII/secrets/binaries — verified: a fresh `git init && git add -A` stages ~159
files with no `data/cravingcrave.db`, no `.exe`, no `.venv`, no `_backup/`, no `.claude/`,
no keys.

## 1. Initialize and commit

```bash
cd CETUS
git init
git add -A
git status            # sanity-check: confirm no data/ db, no .venv, no dist/
git commit -m "CETUS 0.1.0 — initial public release"
```

## 2. Create the GitHub repo and push

With the GitHub CLI:
```bash
gh repo create CETUS --public --source=. --remote=origin --push
```
Or manually: create an empty repo on github.com, then:
```bash
git remote add origin https://github.com/<you>/CETUS.git
git branch -M main
git push -u origin main
```

## 3. Ship the binaries via Releases (not git)

The one-file build (~200 MB) exceeds GitHub's 100 MB file limit, so attach it to a Release
instead of committing it. Build per OS (`build.ps1` on Windows, `build.sh` on macOS/Linux),
then:

```bash
gh release create v0.1.0 dist/CETUS.exe --title "v0.1.0" --notes-file docs/CHANGELOG.md
# add dist/CETUS (macOS/Linux builds) to the same release as you produce them
```

Tell clinics to download the binary from **Releases** and run it next to the `media/`
folder (the app creates `data/` on first run).

## Reminders

- **Never commit `data/`** — it holds patient/clinician PII.
- Rotate any API keys used with `tools/` (Gemini, Freesound) if they were ever exposed.
- The bundled `media/sample_*` files are Creative-Commons (see each `_SAMPLES.csv`);
  any media you add is your responsibility to license and vet clinically.
