"""Tests for the message classifier."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from messages_manager.models import Thread
from messages_manager.classifier import SenderKind, classify_thread, reclassify_with_full_thread


def _thread(sender: str, preview: str = "", unread: bool = False) -> Thread:
    return Thread(thread_id="t1", sender=sender, preview=preview, is_unread=unread)


# ── Short-code senders ────────────────────────────────────────────────────────

def test_short_code_5_digits():
    clsn = classify_thread(_thread("73741"))
    assert clsn.kind == SenderKind.AUTOMATED

def test_short_code_6_digits():
    clsn = classify_thread(_thread("737411"))
    assert clsn.kind == SenderKind.AUTOMATED

def test_standard_phone_not_automated():
    clsn = classify_thread(_thread("+15551234567"))
    assert clsn.kind == SenderKind.CONTACT

def test_ten_digit_phone_not_automated():
    clsn = classify_thread(_thread("5551234567"))
    assert clsn.kind == SenderKind.CONTACT


# ── Alphanumeric senders ──────────────────────────────────────────────────────

def test_alphanumeric_sender():
    clsn = classify_thread(_thread("USBANK"))
    assert clsn.kind == SenderKind.AUTOMATED

def test_alphanumeric_sender_mixed():
    clsn = classify_thread(_thread("Amazon1"))
    assert clsn.kind == SenderKind.AUTOMATED

def test_real_name_not_automated():
    clsn = classify_thread(_thread("Alice Johnson"))
    assert clsn.kind == SenderKind.CONTACT


# ── Content-based detection ───────────────────────────────────────────────────

def test_otp_content():
    clsn = classify_thread(_thread("5551234567", preview="Your verification code is 482910"))
    assert clsn.kind == SenderKind.AUTOMATED

def test_stop_footer():
    clsn = classify_thread(_thread("5551234567", preview="Sale! Reply STOP to unsubscribe."))
    assert clsn.kind == SenderKind.AUTOMATED

def test_promotional_content():
    clsn = classify_thread(_thread("5551234567", preview="50% off today only! Shop now."))
    assert clsn.kind == SenderKind.AUTOMATED

def test_normal_conversation_not_automated():
    clsn = classify_thread(_thread("Mom", preview="Are you coming for dinner tonight?"))
    assert clsn.kind == SenderKind.CONTACT


# ── Question detection ────────────────────────────────────────────────────────

def test_question_mark_detected():
    clsn = classify_thread(_thread("Alice", preview="Can you pick me up at 6?"))
    assert clsn.has_question is True

def test_question_keyword_detected():
    clsn = classify_thread(_thread("Bob", preview="Let me know when you're free."))
    assert clsn.has_question is True

def test_no_question_in_normal_message():
    clsn = classify_thread(_thread("Carol", preview="OK sounds good!"))
    assert clsn.has_question is False


# ── Invitation detection ──────────────────────────────────────────────────────

def test_invitation_detected():
    clsn = classify_thread(_thread("Dave", preview="You're invited to my birthday party!"))
    assert clsn.has_invitation is True

def test_event_detected():
    clsn = classify_thread(_thread("Eve", preview="Come to our game night on Friday."))
    assert clsn.has_invitation is True

def test_dinner_invitation():
    clsn = classify_thread(_thread("Frank", preview="Want to grab dinner Saturday?"))
    assert clsn.has_invitation is True


# ── Reclassification after outgoing replies ───────────────────────────────────

def test_automated_with_reply_becomes_contact():
    clsn = classify_thread(_thread("73741", preview="Your code is 123456"))
    assert clsn.kind == SenderKind.AUTOMATED
    # User replied to this bot thread
    messages = [
        {"text": "Your code is 123456", "outgoing": False},
        {"text": "STOP", "outgoing": True},
    ]
    reclassify_with_full_thread(clsn, messages)
    assert clsn.kind == SenderKind.CONTACT  # upgraded — do not delete


# ── Safelist ──────────────────────────────────────────────────────────────────

def test_safelist_overrides_short_code(monkeypatch):
    import messages_manager.config as cfg
    monkeypatch.setattr(cfg, "CONTACT_SAFELIST", ["73741"])
    clsn = classify_thread(_thread("73741"))
    assert clsn.kind == SenderKind.CONTACT
    assert clsn.safe is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
