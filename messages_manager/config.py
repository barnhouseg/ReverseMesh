"""
Configuration for Google Messages Manager.
Edit CONTACT_SAFELIST and AUTOMATED_SENDERS to tune behavior.
"""

import os

# ── Browser ──────────────────────────────────────────────────────────────────
MESSAGES_URL = "https://messages.google.com/web"
HEADLESS = False          # False = show the browser window (required for QR pairing)
BROWSER_TIMEOUT_MS = 30_000
PAGE_LOAD_WAIT_MS = 5_000

# ── Safety ────────────────────────────────────────────────────────────────────
DRY_RUN = True            # True = report only; False = actually delete threads
CONFIRM_EACH_DELETE = True  # prompt before each deletion when DRY_RUN is False

# ── Session persistence ───────────────────────────────────────────────────────
# Storing the browser profile avoids re-pairing every run.
USER_DATA_DIR = os.path.expanduser("~/.google_messages_manager")

# ── Short-code detection ──────────────────────────────────────────────────────
# North American short codes are 5–6 digits.
# International short codes vary; extend as needed.
SHORT_CODE_MAX_DIGITS = 6

# ── Automated-sender keyword patterns (case-insensitive) ─────────────────────
# If ANY of these appear in the sender name or number the thread is flagged.
KNOWN_AUTOMATED_SENDER_FRAGMENTS = [
    "notify", "alert", "update", "info", "support", "service",
    "noreply", "no-reply", "donotreply", "promo",
]

# ── Automated-content patterns (case-insensitive substrings) ─────────────────
AUTOMATED_CONTENT_PATTERNS = [
    # opt-out footers
    "reply stop", "text stop", "reply help", "msg&data rates",
    "opt out", "unsubscribe",
    # verification / OTP
    "verification code", "one-time", "one time password", " otp",
    "your code is", "your pin is", "confirm your",
    "security code", "login code", "sign-in code",
    # generic promotional
    "% off", "save up to", "limited time", "act now",
    "click here", "tap here", "shop now", "order now",
    "exclusive deal", "special offer", "you've been selected",
    "you have been selected", "congratulations, you",
    "free gift", "free trial", "claim your",
    "your package", "your order", "your shipment",  # shipping bots
    "delivery attempt", "out for delivery",
    # appointment / reminder bots
    "reminder:", "appointment reminder", "your appointment",
    "scheduled for", "confirmed for",
    # bank / account alerts
    "account balance", "transaction alert", "low balance",
    "payment due", "payment received", "payment confirmed",
    # political / survey spam
    "paid for by", "authorized by", "this message was sent",
    "survey:", "take our survey",
]

# ── Question detection patterns ───────────────────────────────────────────────
QUESTION_INDICATORS = [
    "?",
    "what time", "what day", "what date", "what do you",
    "when are", "when can", "when will", "when do",
    "where are", "where is", "where do",
    "who is", "who are", "who will",
    "how are", "how do", "how can", "how much", "how many",
    "can you", "could you", "would you", "will you",
    "did you", "have you", "are you", "do you",
    "let me know", "let us know",
    "thoughts?", "opinion?", "feedback?",
    "is it ok", "is that ok", "is this ok",
    "is that good", "does that work",
    "you available", "you free", "you around",
]

# ── Invitation detection patterns ─────────────────────────────────────────────
INVITATION_INDICATORS = [
    "you're invited", "you are invited", "invite you",
    "join us", "join me", "come to", "come over",
    "party", "birthday", "celebration", "gathering",
    "happy hour", "drinks", "dinner", "lunch", "brunch", "breakfast",
    "bbq", "cookout", "game night", "movie night",
    "wedding", "baby shower", "graduation",
    "meet up", "meetup", "get together",
    "event on", "happening on", "rsvp",
    "save the date",
]

# ── Recommendations engine thresholds ────────────────────────────────────────
OLD_UNANSWERED_DAYS = 7   # flag contact threads with no reply older than N days
LONG_THREAD_COUNT = 50    # flag threads with > N messages as candidates for archiving

# ── Contacts safelist ─────────────────────────────────────────────────────────
# Phone numbers (any format) or display names that must NEVER be deleted,
# regardless of content patterns.  Add your own.
CONTACT_SAFELIST: list[str] = [
    # "+15551234567",
    # "Mom",
]
