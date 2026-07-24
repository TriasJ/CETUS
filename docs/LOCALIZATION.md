# Localization (i18n)

CETUS ships bilingual: **Spanish (`es`, default)** and **English (`en`)**. The UI never
hard-codes a language — every string goes through `tr("some.key")`, which resolves against
per-locale JSON tables. Adding a language is a **drop-in**: no code changes, no rebuild of
the logic, just two data files.

## How it works

| Piece | Location | Purpose |
|-------|----------|---------|
| UI strings | `cravingcrave/resources/i18n/<code>.json` | flat `{"key": "text"}` table read by `tr()` |
| In-app manual | `cravingcrave/resources/help/<code>.json` | `{"title", "sections":[{"id","title","html"}]}` |
| Runtime | `cravingcrave/services/i18n.py` | singleton `I18n`, `tr()`, `set_locale()`, `available_locales()` |
| Persistence | `app_setting` table, key `locale` | the clinic's chosen language, saved locally |

- **Default** locale is `es` (`DEFAULT_LOCALE` in `services/i18n.py` and `config.py`).
- A **missing UI key** falls back to returning the key string (so nothing crashes).
- A **missing help file** for a locale falls back to the default-locale manual, so a new UI
  language never shows an empty Help window.
- Languages are **auto-discovered**: `available_locales()` scans `resources/i18n/*.json` and
  reads each file's `"_language.name"` for the native display name shown in the switcher.

## Switching language (as a clinician)

The language selector appears in two places and applies **immediately** (live re-render, no
restart), persisting for the next launch:

- **Login screen** — a selector above the login card (switch before signing in).
- **Settings → Idioma / Language** — a dropdown listing every installed language by its
  native name.

## Adding a new language (e.g. French, `fr`)

1. **Copy the reference table** and translate every value (keep the keys unchanged):
   ```
   cp cravingcrave/resources/i18n/es.json cravingcrave/resources/i18n/fr.json
   ```
   - Set `"_language.name"` to the language's own native name, e.g. `"Français"`.
   - Translate `"app.language"` and all other values. **Do not add or remove keys** — the
     test suite enforces exact key parity with `es.json`.

2. **(Optional but recommended) translate the manual**:
   ```
   cp cravingcrave/resources/help/es.json cravingcrave/resources/help/fr.json
   ```
   - Keep every section `id` and their order identical to `es.json` (contextual Help jumps
     use the ids). Translate `title` and the `html` body. Preserve DOI/PMID citations.
   - If you skip this, French UI simply shows the Spanish manual (graceful fallback).

3. **Run the tests** — parity and discovery are checked automatically:
   ```
   QT_QPA_PLATFORM=offscreen pytest tests/ui/test_localization.py -q
   ```

That's it. The new language appears in both switchers on next launch. No Python changes.

## For developers: adding a new UI string

1. Add the key to **every** `resources/i18n/*.json` (at minimum `es.json` and `en.json`).
   `tests/ui/test_localization.py::test_every_locale_has_the_same_keys_as_default` fails if
   a locale is missing it.
2. Use it in code via `tr("your.key")`. Supports `str.format` kwargs: `tr("x", name=foo)`.
3. Keys are dotted and grouped by area (`app.*`, `login.*`, `settings.*`, `exposure.*`, …).

## Notes

- The internal package id stays `cravingcrave`; the product name is **CETUS**. Neither is a
  translatable string.
- Locale files are bundled into the frozen `dist/CETUS.exe` by `cravingcrave.spec`; adding a
  language means rebuilding the exe to distribute it (running from source needs no rebuild).
