"""
Formats and prints the processing report plus inbox recommendations.
"""

from __future__ import annotations

from .classifier import Classification, SenderKind
from .processor import ProcessingResult


_DIVIDER = "─" * 68
_SECTION = "═" * 68


def print_report(result: ProcessingResult, *, dry_run: bool) -> None:
    print(f"\n{_SECTION}")
    print("  GOOGLE MESSAGES MANAGER — REPORT")
    mode = "DRY RUN (no changes made)" if dry_run else "LIVE RUN"
    print(f"  Mode: {mode}")
    print(_SECTION)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n  Total threads scanned : {result.total_threads}")
    print(f"  Automated (bots/spam) : {len(result.automated)}")
    print(f"  Contact threads       : {len(result.contacts)}")
    print(f"  Deleted               : {len(result.deleted)}")
    print(f"  Skipped (user choice) : {len(result.skipped)}")

    # ── Automated threads ─────────────────────────────────────────────────────
    if result.automated:
        print(f"\n{_DIVIDER}")
        print("  AUTOMATED THREADS" + (" — TO BE DELETED" if dry_run else " — DELETED"))
        print(_DIVIDER)
        for clsn in result.automated:
            tag = "[DRY-RUN]" if dry_run else "[DELETED]"
            reasons = ", ".join(clsn.reasons) if clsn.reasons else "automated content"
            print(f"  {tag}  {clsn.sender:<30}  {reasons}")
            if clsn.preview:
                print(f"            Preview: {clsn.preview[:80]}")

    # ── Questions needing a reply ─────────────────────────────────────────────
    if result.questions:
        print(f"\n{_DIVIDER}")
        print("  CONTACT THREADS WITH UNANSWERED QUESTIONS")
        print(_DIVIDER)
        for clsn in result.questions:
            print(f"  ✦  {clsn.sender}")
            print(f"     Preview : {clsn.preview[:80]}")
            print(f"     Matches : {', '.join(clsn.question_snippets)}")

    # ── Invitations ───────────────────────────────────────────────────────────
    if result.invitations:
        print(f"\n{_DIVIDER}")
        print("  CONTACT THREADS WITH INVITATIONS / EVENTS")
        print(_DIVIDER)
        for clsn in result.invitations:
            print(f"  ✦  {clsn.sender}")
            print(f"     Preview : {clsn.preview[:80]}")
            print(f"     Matches : {', '.join(clsn.invitation_snippets)}")

    # ── Errors ────────────────────────────────────────────────────────────────
    if result.errors:
        print(f"\n{_DIVIDER}")
        print("  ERRORS")
        print(_DIVIDER)
        for err in result.errors:
            print(f"  ! {err}")

    # ── Recommendations ───────────────────────────────────────────────────────
    _print_recommendations(result)

    print(f"\n{_SECTION}\n")


def _print_recommendations(result: ProcessingResult) -> None:
    recs: list[str] = []

    # Reply to open questions
    if result.questions:
        recs.append(
            f"Reply to {len(result.questions)} contact thread(s) that contain questions."
        )

    # RSVP invitations
    if result.invitations:
        recs.append(
            f"Respond to {len(result.invitations)} invitation(s) before they lapse."
        )

    # Unread contacts
    unread_contacts = [c for c in result.contacts if c.is_unread]
    if unread_contacts:
        recs.append(
            f"You have {len(unread_contacts)} unread contact thread(s)."
        )

    # Lots of automated threads → suggest opting out
    if len(result.automated) >= 5:
        recs.append(
            "You received many automated messages.  Reply STOP to the senders "
            "you no longer want to hear from to reduce future volume."
        )

    # General inbox hygiene
    recs += [
        "Enable 'Spam protection' in Messages → Settings → General to auto-block "
        "more junk before it reaches your inbox.",
        "Use Google Contacts to label important numbers so they always appear by "
        "name and are never mis-classified.",
        "Consider running this tool on a schedule (e.g. daily via cron) to keep "
        "your inbox continuously clean.",
        "For OTP / bank messages you want to keep briefly, set a 24-hour retention "
        "rule by noting the sender short codes and letting this tool skip them for "
        "a day before deleting.",
    ]

    print(f"\n{_DIVIDER}")
    print("  RECOMMENDATIONS")
    print(_DIVIDER)
    for i, rec in enumerate(recs, 1):
        _print_wrapped(f"  {i}. {rec}", width=68)


def _print_wrapped(text: str, width: int = 68) -> None:
    import textwrap
    lines = textwrap.wrap(text, width=width, subsequent_indent="     ")
    for line in lines:
        print(line)
