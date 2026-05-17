# GoogleMessageManager

Automates inbox hygiene for **Google Messages Web** (messages.google.com).

Treats your SMS inbox like email — deletes automated messages, never touches
real contacts, and surfaces questions and invitations that need your attention.

## Quick start

```bash
pip install playwright
playwright install chromium

# Dry run — classify and report, no deletions:
python run.py

# Live — delete automated threads (prompts before each):
python run.py --live
```

On first run the browser opens and shows the QR pairing screen.  Scan it from
your phone: **Messages → ⋮ → Device Pairing**.  The session is saved to
`~/.GoogleMessageManager/` so subsequent runs skip the QR step.

## What it does

| Thread type | Action |
|---|---|
| Short-code sender (5–6 digits) | Deleted |
| ALL-CAPS / brand+digit sender (e.g. `USBANK`, `Amazon1`) | Deleted |
| Known automated content (OTP, STOP footer, promo) | Deleted |
| Contact with a question | Flagged in report |
| Contact with an invitation / event | Flagged in report |
| Everything else | Left untouched |

## Flags

```
--live          Actually delete (default is dry run)
--no-confirm    Skip per-deletion prompts
--deep          Read full thread before deciding (catches replied-to bots)
--headless      Run without a visible browser window
```

## Configuration

All tuning is in `GoogleMessageManager/config.py`:

- `CONTACT_SAFELIST` — numbers/names that are never deleted
- `AUTOMATED_CONTENT_PATTERNS` — substring patterns that flag a thread
- `QUESTION_INDICATORS` / `INVITATION_INDICATORS` — detection phrases

See `CLAUDE.md` for the full customisation guide and recommended workflows.

## Tests

```bash
python -m pytest tests/test_classifier.py -v   # 19 tests, no browser needed
```

## Project layout

```
run.py
GoogleMessageManager/
├── config.py       ← all tunable settings
├── models.py       ← Thread / Message dataclasses
├── classifier.py   ← classification + question/invitation detection
├── browser.py      ← Playwright session management
├── processor.py    ← orchestration pipeline
└── reporter.py     ← report formatting + recommendations
tests/
└── test_classifier.py
CLAUDE.md           ← full project skills file
```
