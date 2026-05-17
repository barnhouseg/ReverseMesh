# GoogleMessageManager — Project Skills File

This document captures everything Claude needs to understand and work on the
GoogleMessageManager project effectively.

---

## Project Overview

GoogleMessageManager is a Python tool that automates inbox hygiene for
**Google Messages Web** (messages.google.com).  It treats the SMS inbox the
same way a good email client treats email:

- **Automated messages** (bots, OTP codes, marketing, shipping alerts,
  appointment reminders, bank alerts) are identified and deleted.
- **Contact messages** (real humans) are **never** moved, archived, or deleted.
- Contact threads are scanned for **questions** (need a reply) and
  **invitations** (need an RSVP) and surfaced in the report.
- Every run ends with **actionable recommendations** to keep the inbox lean.

---

## Architecture

```
run.py                          ← CLI entry point (argparse)
GoogleMessageManager/
├── __init__.py
├── config.py                   ← All tunable thresholds and pattern lists
├── models.py                   ← Thread / Message dataclasses (no deps)
├── classifier.py               ← Classification engine (no browser dep)
├── browser.py                  ← Playwright session, scroll-load, deletion
├── processor.py                ← Orchestration pipeline
└── reporter.py                 ← Formatted report + inbox recommendations
tests/
└── test_classifier.py          ← 19 unit tests (no browser required)
```

### Data flow

```
browser.list_threads()
    │  [Thread list]
    ▼
classifier.classify_thread()        ← preview-based, instant
    │  [Classification]
    ▼
classifier.reclassify_with_full_thread()   ← only with --deep flag
    │  [refined Classification]
    ▼
processor  →  browser.delete_thread()   ← only AUTOMATED threads
    │
    ▼
reporter.print_report()
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | `Thread(thread_id, sender, preview, is_unread, timestamp)` and `Message(text, outgoing)` — shared between classifier and browser with no cross-deps |
| `classifier.py` | Stateless classification: short-code detection, alphanumeric-sender detection, content-pattern matching, question/invitation scanning, safelist override, outgoing-reply upgrade |
| `browser.py` | `MessagesSession` — Playwright persistent context, QR pairing wait, conversation list scroll-load, thread open/read, right-click delete with confirmation dialog handling |
| `processor.py` | `run()` — ties session + classifier together; returns `ProcessingResult` |
| `reporter.py` | Formats the terminal report; generates recommendations list |
| `config.py` | Single source of truth for all thresholds; edit here, nowhere else |

---

## Classification Rules

Applied in priority order (first match wins):

| # | Signal | Verdict |
|---|---|---|
| 1 | Sender in `CONTACT_SAFELIST` | **CONTACT** — absolute protection |
| 2 | Sender is 4–6 digits only (short code) | **AUTOMATED** |
| 3 | Sender is ALL-CAPS (no spaces, no digits) | **AUTOMATED** |
| 4 | Sender contains embedded digits with letters | **AUTOMATED** |
| 5 | Sender contains a known automated fragment | **AUTOMATED** |
| 6 | Preview matches an automated content pattern | **AUTOMATED** |
| 7 | Thread has ≥1 outgoing reply (deep scan only) | **CONTACT** — override |
| 8 | Everything else | **CONTACT** (safe default) |

---

## Run Instructions

### Prerequisites

```bash
pip install playwright
playwright install chromium
```

### First run — QR pairing

```bash
python run.py
```

The browser opens to messages.google.com.  Scan the QR code from your phone:
**Messages → ⋮ → Device Pairing**.

The session is saved to `~/.GoogleMessageManager/`.  Subsequent runs skip the
QR step entirely.

### Common invocations

```bash
# Dry run (safe, no changes):
python run.py

# Live mode — delete automated threads, prompt before each:
python run.py --live

# Live mode, no prompts (useful in cron):
python run.py --live --no-confirm

# Deep scan — open each flagged thread and read all messages:
python run.py --deep

# Headless — requires existing paired session:
python run.py --headless

# Combine flags:
python run.py --live --no-confirm --headless --deep
```

### Tests (no browser needed)

```bash
python -m pytest tests/test_classifier.py -v
```

---

## Customisation Guide

All tuning lives in `GoogleMessageManager/config.py`.

### Protecting a contact

```python
CONTACT_SAFELIST = [
    "+15551234567",   # by phone number (any format)
    "Mom",            # by display name
]
```

Safelisted entries are never touched regardless of content patterns.

### Adding an automated-content pattern

```python
AUTOMATED_CONTENT_PATTERNS = [
    ...
    "your reservation",   # add hotel/restaurant bots
    "flight update",      # add airline bots
]
```

### Protecting a short-code you want to keep

Temporarily add the code to `CONTACT_SAFELIST`:

```python
CONTACT_SAFELIST = ["73741"]   # keep Chase OTP codes for now
```

Remove it once you no longer need the messages.

### Tuning question / invitation detection

Add or remove phrases in `QUESTION_INDICATORS` and `INVITATION_INDICATORS`.
Both are plain substring lists (case-insensitive).

### Running in headless mode permanently

```python
HEADLESS = True
```

### Disabling per-thread confirmation in code

```python
CONFIRM_EACH_DELETE = False
```

---

## Recommended Workflows

### Daily cron (headless, fully automatic)

```cron
0 8 * * * cd /path/to/GoogleMessageManager && python run.py --live --no-confirm --headless
```

Runs at 08:00 every day.  Requires an existing paired session.

### Weekly review run (interactive)

```bash
python run.py --deep --live
```

The `--deep` flag opens each flagged thread to catch any cases where you
previously replied to an automated sender — those are upgraded to CONTACT and
skipped.

### Checking the inbox without touching anything

```bash
python run.py
```

Dry-run is the default.  Safe to run at any time.

### Opting out of high-volume senders

When the report shows many automated threads from the same sender, reply
`STOP` to that sender once.  Add the short code to `CONTACT_SAFELIST`
temporarily so the tool does not delete the STOP-confirmation reply before
you see it, then remove it on the next run.

### Enabling Messages built-in spam protection

In the Google Messages app: **⋮ → Settings → General → Spam protection**.
This filters the worst offenders before they reach the inbox at all,
reducing the load on this tool.

### Labelling contacts in Google Contacts

Saving phone numbers in Google Contacts ensures they appear by display name
(e.g. "Alice Johnson") rather than raw number.  Display names with spaces are
never mis-classified as alphanumeric automated senders.

---

## Safety Guarantees

1. **Dry-run by default** — no deletions without `--live`.
2. **Contact-safe** — a thread is CONTACT unless positively identified as
   automated.  The classifier errs on the side of protection.
3. **Outgoing-reply override** — if you ever replied to a thread that looks
   automated, `--deep` catches it and upgrades it to CONTACT.
4. **Safelist** — explicit list in `config.py` that overrides all other rules.
5. **Confirmation prompts** — in live mode without `--no-confirm`, you approve
   each deletion interactively.
