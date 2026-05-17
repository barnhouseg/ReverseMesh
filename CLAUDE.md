# GoogleMessageManager — Project Skills File

*Consolidated from the founding session. Read this before making any changes.*

---

## What This Project Is

GoogleMessageManager automates inbox hygiene for **Google Messages Web**
(messages.google.com) using Playwright browser automation.

The design philosophy is **treat SMS exactly like email**:

- Automated messages (bots, OTPs, marketing, shipping, reminders, bank alerts)
  are identified and **deleted**.
- Messages from real contacts are **never moved, archived, or deleted** — full
  stop, no exceptions, even if the content looks automated.
- Contact threads are scanned for **questions** (need a reply) and
  **invitations** (need an RSVP) and surfaced prominently in the report.
- Every run produces **actionable inbox recommendations**.
- **Dry-run is the default.** Nothing is deleted unless you explicitly pass
  `--live`.

---

## Session History & Key Decisions

### Decision: email model for SMS
The user explicitly framed this as an email-management problem. The analogy
drove every design choice: contacts = trusted senders (never touch); automated
= newsletters/notifications (delete after processing); questions/invitations =
items requiring action.

### Decision: safe-by-default classifier
The classifier errs on the side of protection. Anything ambiguous is classified
as CONTACT. An automated thread is only deleted when positively identified by
at least one signal (short code, ALL-CAPS sender, content keyword, etc.).

### Decision: outgoing-reply override
If the user has ever replied to a thread (even a bot thread), that thread is
upgraded to CONTACT and is never deleted. Rationale: if you replied to it,
you care about it. Requires `--deep` flag to detect (it opens each thread).

### Decision: alphanumeric sender heuristic
Single-word title-case names (Mom, Alice, Frank) must NOT be flagged as
automated. Only ALL-CAPS senders or senders with embedded digits (USBANK,
Amazon1) are flagged. This was validated and fixed via failing tests before
the code was shipped.

### Decision: package name GoogleMessageManager
Renamed from the original `messages_manager` snake_case package. All imports,
the session data directory (`~/.GoogleMessageManager/`), and the entry point
(`run.py`) use this name consistently.

### Decision: prior repo content deleted
The repository previously contained a Fusion360 add-in (ReverseMesh). All of
that content — `Reverse.py`, `graveyard.py`, `Reverse.manifest`, `ModulesWin/`,
`ModulesMac/`, `Resources/` — was removed. The repo is now exclusively
GoogleMessageManager.

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
CLAUDE.md                       ← this file
README.md                       ← user-facing quickstart
requirements.txt                ← playwright only
```

### Data flow

```
MessagesSession.list_threads()
    │  returns [Thread]
    ▼
classifier.classify_thread(thread)      ← preview-based, instant, no I/O
    │  returns Classification
    ▼
[if --deep] open thread in browser
classifier.reclassify_with_full_thread()
    │  upgrades AUTOMATED→CONTACT if outgoing replies found
    ▼
processor collects:
  - automated[]   → passed to delete_thread()
  - contacts[]    → scanned for questions / invitations
    ▼
reporter.print_report()
  - Summary counts
  - Automated threads (deleted or would-be deleted)
  - Contact threads with questions
  - Contact threads with invitations
  - Recommendations
```

### Module responsibilities

| Module | Key exports | Notes |
|---|---|---|
| `models.py` | `Thread`, `Message` | No imports from other project modules; safe to import anywhere |
| `classifier.py` | `classify_thread()`, `reclassify_with_full_thread()`, `Classification`, `SenderKind` | Stateless pure functions; fully unit-testable without a browser |
| `browser.py` | `MessagesSession` | Wraps Playwright; handles QR pairing, lazy-scroll, right-click delete |
| `processor.py` | `run()`, `ProcessingResult` | Ties session + classifier; returns structured result |
| `reporter.py` | `print_report()` | Formats terminal output; generates recommendations list |
| `config.py` | module-level constants | Single source of truth for all thresholds |

---

## Classification Rules

Applied in priority order — first match wins:

| Priority | Signal | Verdict | Notes |
|---|---|---|---|
| 1 | Sender in `CONTACT_SAFELIST` | **CONTACT** | Absolute override, no exceptions |
| 2 | Sender is 4–6 digits only | **AUTOMATED** | North American short codes |
| 3 | Sender is ALL-CAPS (no spaces, no digits) | **AUTOMATED** | USPS, BANK, ALERTS |
| 4 | Sender has embedded digits with letters | **AUTOMATED** | Amazon1, US2Bank |
| 5 | Sender matches a `KNOWN_AUTOMATED_SENDER_FRAGMENTS` entry | **AUTOMATED** | "notify", "alert", "noreply", etc. |
| 6 | Preview matches an `AUTOMATED_CONTENT_PATTERNS` entry | **AUTOMATED** | OTP, STOP footer, promo, shipping, bank |
| 7 | Thread has ≥1 outgoing reply (`--deep` only) | **CONTACT** | Override — user replied, so protect it |
| 8 | Anything else | **CONTACT** | Safe default |

### Why single-word names are NOT alphanumeric senders
`_is_alphanumeric_sender()` in `classifier.py` only returns True when:
- The string is ALL-CAPS (e.g. `BANK`) — brand signal
- The string contains both letters and digits (e.g. `Amazon1`) — brand signal

Title-case single words with no digits (Mom, Alice, Frank) fall through to the
CONTACT default. This was the most important edge case found in testing.

---

## Question & Invitation Detection

Runs only on CONTACT threads (never on AUTOMATED). Checks the preview text
(or full thread text in `--deep` mode) for substring matches.

**Question signals** (`QUESTION_INDICATORS` in config):
- Literal `?` character
- Opener phrases: "can you", "could you", "would you", "will you", "did you",
  "have you", "are you", "do you", "how are", "when are", "where are", etc.
- Action phrases: "let me know", "thoughts?", "feedback?"

**Invitation signals** (`INVITATION_INDICATORS` in config):
- Direct: "you're invited", "join us", "come to", "rsvp", "save the date"
- Event types: "party", "birthday", "wedding", "baby shower", "graduation",
  "game night", "movie night", "happy hour", "dinner", "lunch", "brunch"
- Casual: "meet up", "get together", "come over"

---

## Run Instructions

### Prerequisites (one-time)

```bash
pip install playwright
playwright install chromium
```

### First run — QR pairing

```bash
python run.py
```

The browser opens to messages.google.com. Scan the QR code from your phone:
**Messages → ⋮ → Device Pairing**

The session is saved to `~/.GoogleMessageManager/`. Subsequent runs skip the
QR step entirely.

### Common invocations

```bash
# Safe audit — no changes made:
python run.py

# Live mode — delete automated threads, prompt before each:
python run.py --live

# Live mode, no prompts (cron-friendly):
python run.py --live --no-confirm

# Deep scan — read full thread before deciding (slower, more accurate):
python run.py --deep

# Headless — no visible browser (requires existing session):
python run.py --headless

# Full automation:
python run.py --live --no-confirm --headless --deep
```

### Tests (no browser, no pairing needed)

```bash
python -m pytest tests/test_classifier.py -v
# Expected: 19 passed
```

---

## Customisation Guide

All tuning is in `GoogleMessageManager/config.py`. Edit that file only —
never hardcode values elsewhere.

### Protect a specific contact or number

```python
CONTACT_SAFELIST = [
    "+15551234567",   # exact number match (any format)
    "Chase",          # display name match
]
```

### Add an automated-content pattern

```python
AUTOMATED_CONTENT_PATTERNS = [
    ...
    "your reservation",   # hotel / restaurant bots
    "flight update",      # airline alerts
    "your prescription",  # pharmacy bots
]
```

### Temporarily protect a short code you want to keep

```python
# Keep Chase OTPs for 24h before deleting:
CONTACT_SAFELIST = ["72166"]
```

Remove the entry on the next run once you've read the messages.

### Add custom question or invitation phrases

```python
QUESTION_INDICATORS = [
    ...
    "ping me",        # informal "let me know"
    "lmk",            # text shorthand
]

INVITATION_INDICATORS = [
    ...
    "trivia night",
    "open house",
]
```

### Make headless permanent

```python
HEADLESS = True
```

### Disable per-deletion confirmation permanently

```python
CONFIRM_EACH_DELETE = False
```

---

## Recommended Workflows

### Daily automated cleanup (cron)

```cron
# 08:00 every day — fully silent, headless
0 8 * * * cd /path/to/GoogleMessageManager && python run.py --live --no-confirm --headless
```

Requires an existing paired session. Run `python run.py` once manually first
to complete QR pairing.

### Weekly deep review

```bash
python run.py --deep --live
```

`--deep` opens every flagged thread to catch cases where you replied to a
bot-looking sender. Slower (~2–5s per automated thread) but catches edge cases.

### Audit without changes (anytime)

```bash
python run.py
```

Safe to run whenever. Shows you exactly what would be deleted.

### Opting out of a high-volume sender

1. Reply `STOP` to the sender.
2. Add the short code to `CONTACT_SAFELIST` temporarily so the tool doesn't
   delete the STOP-confirmation reply before you see it.
3. Remove the safelist entry on the next run.

### Enable Messages built-in spam protection

In the Google Messages app: **⋮ → Settings → General → Spam protection**

Filters the worst senders before they reach the inbox, reducing load on this
tool.

### Label contacts in Google Contacts

Saving numbers in Google Contacts ensures they appear as display names (e.g.
"Alice Johnson") rather than raw numbers. Names with a space are never
mis-classified as alphanumeric automated senders.

---

## Safety Guarantees

1. **Dry-run by default** — no deletions without explicit `--live`.
2. **Contact-safe** — unknown = CONTACT. The classifier only deletes on
   positive identification, never on suspicion.
3. **Outgoing-reply upgrade** — `--deep` catches any thread where you replied;
   those are upgraded to CONTACT and left alone.
4. **Safelist** — explicit list in `config.py` that overrides every other rule.
5. **Per-deletion confirmation** — in `--live` mode without `--no-confirm`,
   you approve each deletion at the terminal.
6. **No archive, no mute, no label changes** — the only write operation is
   deletion of confirmed-AUTOMATED threads. Contact threads are read-only.

---

## Browser DOM Notes (messages.google.com, 2025)

Google Messages Web uses a custom element set. Selectors target multiple
variants to survive minor DOM updates:

| Element | Primary selector | Fallbacks |
|---|---|---|
| Conversation list item | `mws-conversation-list-item` | `.conversation-list-item`, `[data-e2e='conversation-item']` |
| Thread ID | `data-e2e-conversation-id` attr | `data-conversation-id`, `id` |
| Sender name | `.sender-name` | `.name`, `.contact-name`, `.conversation-participants` |
| Preview text | `.snippet-text` | `.preview`, `.last-message` |
| Unread badge | `.unread-indicator` | `.unread-dot`, `[aria-label*='unread']` |
| Message bubble | `mws-message-part` | `.message-wrapper`, `[data-e2e='message-bubble']` |
| Outgoing | `.outgoing` class | `.sent`, `[data-e2e='outgoing']` |

If Google updates the DOM, update the selector lists in `browser.py`. The
logic does not need to change — only the CSS selectors.

---

## Adding New Features

### New automated-sender type
Add detection in `classifier._is_short_code()` or
`classifier._is_alphanumeric_sender()`, and add a test in
`tests/test_classifier.py`.

### New content category (e.g. "action required")
1. Add patterns to `config.py`.
2. Add a scan function in `classifier.py` (follow the pattern of
   `_scan_contact_content`).
3. Add a field to `Classification`.
4. Surface it in `reporter.print_report()`.
5. Add unit tests.

### Scheduling via launchd (macOS)

```xml
<!-- ~/Library/LaunchAgents/com.googlemessagemanager.plist -->
<plist version="1.0"><dict>
  <key>Label</key><string>com.googlemessagemanager</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/run.py</string>
    <string>--live</string><string>--no-confirm</string><string>--headless</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
</dict></plist>
```
