"""
Classifies a conversation as AUTOMATED or CONTACT and detects
questions / invitations inside contact threads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from . import config
from .models import Thread


class SenderKind(Enum):
    AUTOMATED = auto()   # short-code, alphanumeric, known automated fragment
    CONTACT = auto()     # saved name or standard phone number with replies
    UNKNOWN = auto()     # cannot determine yet


@dataclass
class Classification:
    thread_id: str
    sender: str
    preview: str
    kind: SenderKind
    reasons: list[str] = field(default_factory=list)
    has_question: bool = False
    has_invitation: bool = False
    question_snippets: list[str] = field(default_factory=list)
    invitation_snippets: list[str] = field(default_factory=list)
    # populated after full thread inspection
    message_count: int = 0
    has_outgoing: bool = False
    is_unread: bool = False

    @property
    def safe(self) -> bool:
        """True → must never be deleted."""
        return self.kind == SenderKind.CONTACT or self.sender in config.CONTACT_SAFELIST

    @property
    def delete_candidate(self) -> bool:
        return self.kind == SenderKind.AUTOMATED and not self.safe


# ── Normalisation helpers ─────────────────────────────────────────────────────

_DIGIT_RE = re.compile(r"\D")


def _digits_only(s: str) -> str:
    return _DIGIT_RE.sub("", s)


def _is_short_code(sender: str) -> bool:
    digits = _digits_only(sender)
    return 4 <= len(digits) <= config.SHORT_CODE_MAX_DIGITS and len(digits) == len(sender.strip())


def _is_alphanumeric_sender(sender: str) -> bool:
    """
    True for SMS alphanumeric sender IDs (e.g. USBANK, Amazon1, ALERTS).
    False for ordinary human contact names (e.g. Mom, Alice, Frank).

    Heuristics:
    - Has a space → almost certainly a saved contact name (two words).
    - All uppercase AND no spaces → strong indicator of a brand/service ID.
    - Contains embedded digits (not a pure number) AND no spaces → brand ID.
    - Title-case single word with no digits → treat as a human name (safe).
    """
    stripped = sender.strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{3,20}", stripped):
        return False
    if stripped.isdigit():
        return False
    # All uppercase with no digits → brand/service (BANK, USPS, ALERTS)
    if stripped.isupper():
        return True
    # Contains digits embedded in letters → brand ID (Amazon1, US2Go)
    if re.search(r"[A-Za-z]", stripped) and re.search(r"\d", stripped):
        return True
    # Title-case or lowercase single word, no digits → human name
    return False


def _has_automated_fragment(sender: str) -> bool:
    lower = sender.lower()
    return any(frag in lower for frag in config.KNOWN_AUTOMATED_SENDER_FRAGMENTS)


def _matches_any(text: str, patterns: list[str]) -> list[str]:
    lower = text.lower()
    return [p for p in patterns if p in lower]


# ── Main classifier ───────────────────────────────────────────────────────────

def classify_thread(thread: Thread) -> Classification:
    """
    Rules (applied in order):
    1. Safelist → CONTACT (never touch).
    2. Short code → AUTOMATED.
    3. Alphanumeric sender → AUTOMATED.
    4. Known automated sender fragment → AUTOMATED.
    5. Automated content patterns in preview → AUTOMATED.
    6. Otherwise → CONTACT (safe default).

    For CONTACT threads we additionally scan for questions and invitations.
    """
    sender = thread.sender.strip()
    preview = thread.preview or ""
    clsn = Classification(
        thread_id=thread.thread_id,
        sender=sender,
        preview=preview,
        kind=SenderKind.UNKNOWN,
        is_unread=thread.is_unread,
    )

    # Rule 1 – explicit safelist
    normalised_safelist = [s.lower().strip() for s in config.CONTACT_SAFELIST]
    if sender.lower() in normalised_safelist or _digits_only(sender) in [
        _digits_only(s) for s in config.CONTACT_SAFELIST
    ]:
        clsn.kind = SenderKind.CONTACT
        clsn.reasons.append("safelist")
        _scan_contact_content(clsn, preview)
        return clsn

    # Rules 2–5 – automated detection
    if _is_short_code(sender):
        clsn.kind = SenderKind.AUTOMATED
        clsn.reasons.append(f"short-code sender ({sender})")
    elif _is_alphanumeric_sender(sender):
        clsn.kind = SenderKind.AUTOMATED
        clsn.reasons.append(f"alphanumeric sender ({sender})")
    elif _has_automated_fragment(sender):
        clsn.kind = SenderKind.AUTOMATED
        clsn.reasons.append(f"automated sender fragment")

    matched_content = _matches_any(preview, config.AUTOMATED_CONTENT_PATTERNS)
    if matched_content:
        clsn.reasons.append(f"automated content: {matched_content[:3]}")
        if clsn.kind == SenderKind.UNKNOWN:
            clsn.kind = SenderKind.AUTOMATED

    # Default to CONTACT (safe)
    if clsn.kind == SenderKind.UNKNOWN:
        clsn.kind = SenderKind.CONTACT

    if clsn.kind == SenderKind.CONTACT:
        _scan_contact_content(clsn, preview)

    return clsn


def reclassify_with_full_thread(clsn: Classification, messages: list[dict]) -> None:
    """
    Refine classification after loading the full thread.
    messages: list of {"text": str, "outgoing": bool}
    """
    clsn.message_count = len(messages)
    clsn.has_outgoing = any(m["outgoing"] for m in messages)

    # If we previously flagged AUTOMATED but find outgoing replies → upgrade to CONTACT.
    # A human replied → treat as a contact thread, do not delete.
    if clsn.kind == SenderKind.AUTOMATED and clsn.has_outgoing:
        clsn.kind = SenderKind.CONTACT
        clsn.reasons.append("has outgoing replies → upgraded to CONTACT")

    if clsn.kind == SenderKind.CONTACT:
        full_text = " ".join(m["text"] for m in messages if not m["outgoing"])
        _scan_contact_content(clsn, full_text)


def _scan_contact_content(clsn: Classification, text: str) -> None:
    lower = text.lower()

    q_matches = _matches_any(lower, config.QUESTION_INDICATORS)
    if q_matches:
        clsn.has_question = True
        clsn.question_snippets = q_matches[:5]

    inv_matches = _matches_any(lower, config.INVITATION_INDICATORS)
    if inv_matches:
        clsn.has_invitation = True
        clsn.invitation_snippets = inv_matches[:5]
