"""
Orchestrates thread scanning, classification, and deletion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .browser import MessagesSession
from .models import Thread
from .classifier import Classification, SenderKind, classify_thread, reclassify_with_full_thread


@dataclass
class ProcessingResult:
    total_threads: int = 0
    automated: list[Classification] = field(default_factory=list)
    contacts: list[Classification] = field(default_factory=list)
    deleted: list[Classification] = field(default_factory=list)
    skipped: list[Classification] = field(default_factory=list)
    questions: list[Classification] = field(default_factory=list)
    invitations: list[Classification] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run(
    *,
    dry_run: bool = config.DRY_RUN,
    confirm_each: bool = config.CONFIRM_EACH_DELETE,
    deep_scan: bool = False,
) -> ProcessingResult:
    """
    Main entry point.

    dry_run=True   → classify + report only, no deletions.
    deep_scan=True → open each automated thread to read all messages before
                     deciding; slower but more accurate (catches threads where
                     you replied to a bot).
    """
    result = ProcessingResult()

    with MessagesSession() as session:
        print("\n[manager] Navigating to Google Messages…")
        session.navigate_and_pair()

        print("[manager] Loading conversation list…")
        threads = session.list_threads()
        result.total_threads = len(threads)
        print(f"[manager] Found {len(threads)} threads.\n")

        for thread in threads:
            clsn = _process_single_thread(session, thread, deep_scan=deep_scan)

            if clsn.kind == SenderKind.AUTOMATED:
                result.automated.append(clsn)
            else:
                result.contacts.append(clsn)
                if clsn.has_question:
                    result.questions.append(clsn)
                if clsn.has_invitation:
                    result.invitations.append(clsn)

        # Deletion pass
        for clsn in result.automated:
            ok = session.delete_thread(
                Thread(
                    thread_id=clsn.thread_id,
                    sender=clsn.sender,
                    preview=clsn.preview,
                ),
                dry_run=dry_run,
                confirm=confirm_each,
            )
            if ok:
                result.deleted.append(clsn)
            else:
                result.skipped.append(clsn)

    return result


def _process_single_thread(
    session: MessagesSession, thread: Thread, *, deep_scan: bool
) -> Classification:
    clsn = classify_thread(thread)

    if deep_scan and clsn.kind == SenderKind.AUTOMATED:
        try:
            session.open_thread(thread)
            raw_messages = session.read_messages_in_open_thread()
            msgs = [{"text": m.text, "outgoing": m.outgoing} for m in raw_messages]
            reclassify_with_full_thread(clsn, msgs)
        except Exception as exc:
            print(f"  [processor] deep-scan failed for {thread.sender!r}: {exc}")

    return clsn
