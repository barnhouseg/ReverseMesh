"""
Playwright-based browser automation for messages.google.com.

Pairing:
  On first run the browser opens, shows the QR code, and waits for you
  to scan it from your phone (Messages → Device Pairing).  The session
  is then persisted in USER_DATA_DIR so subsequent runs skip the QR step.

DOM notes (as of 2025):
  - Conversation list: <mws-conversation-list-item> elements inside
    <mws-conversations-list>.
  - Each item exposes data-e2e-conversation-id as the stable thread ID.
  - Sender name/number lives in .sender-name or .name (varies).
  - Preview lives in .snippet-text or .preview.
  - Unread badge: .unread-indicator or aria-label containing "unread".
  - Delete: right-click on list item → context menu → "Delete".
"""

from __future__ import annotations

from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PWTimeout,
)

from . import config
from .models import Message, Thread


class MessagesSession:
    """Manages a persistent Playwright session against messages.google.com."""

    def __init__(self) -> None:
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> "MessagesSession":
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=config.USER_DATA_DIR,
            headless=config.HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self

    def stop(self) -> None:
        try:
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def __enter__(self) -> "MessagesSession":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ── Navigation ────────────────────────────────────────────────────────────

    def navigate_and_pair(self) -> None:
        """Open Messages Web; wait for QR pairing if not already connected."""
        page = self._page
        page.goto(config.MESSAGES_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)

        # If we land on the pairing page, wait up to 2 min for the user to scan QR.
        if self._on_pairing_page():
            print("\n[browser] QR code displayed.  Scan from your phone (Messages → Device Pairing).")
            print("[browser] Waiting up to 2 minutes…")
            for _ in range(24):  # 24 × 5s = 2 min
                page.wait_for_timeout(5_000)
                if not self._on_pairing_page():
                    break
            else:
                raise RuntimeError("Timed out waiting for QR pairing.")

        print("[browser] Connected to Messages Web.")
        self._wait_for_conversation_list()

    def _on_pairing_page(self) -> bool:
        return "qr" in self._page.url.lower() or bool(
            self._page.query_selector("mw-qr-code, .qr-code-container, [data-e2e='qr-code']")
        )

    def _wait_for_conversation_list(self) -> None:
        self._page.wait_for_selector(
            "mws-conversation-list-item, .conversation-list-item, [data-e2e='conversation-item']",
            timeout=config.BROWSER_TIMEOUT_MS,
        )

    # ── Thread enumeration ────────────────────────────────────────────────────

    def list_threads(self) -> list[Thread]:
        """
        Return all visible threads in the conversation list.
        Scrolls to the bottom to load lazy-rendered items.
        """
        page = self._page
        self._scroll_conversation_list_to_bottom()

        items = page.query_selector_all(
            "mws-conversation-list-item, .conversation-list-item, [data-e2e='conversation-item']"
        )
        threads: list[Thread] = []
        for item in items:
            try:
                thread = self._parse_thread_item(item)
                if thread:
                    threads.append(thread)
            except Exception as exc:
                print(f"[browser] Warning: could not parse thread item – {exc}")
        return threads

    def _parse_thread_item(self, item) -> Optional[Thread]:
        # Thread ID
        tid = (
            item.get_attribute("data-e2e-conversation-id")
            or item.get_attribute("data-conversation-id")
            or item.get_attribute("id")
            or ""
        )

        # Sender – try multiple selectors used across Messages Web versions
        sender = self._inner_text(item, [
            ".sender-name", ".name", "[data-e2e='sender-name']",
            ".conversation-participants", ".contact-name",
        ])

        # Preview text
        preview = self._inner_text(item, [
            ".snippet-text", ".preview", "[data-e2e='message-preview']",
            ".message-preview", ".last-message",
        ])

        # Unread
        unread_el = item.query_selector(
            ".unread-indicator, .unread-dot, [aria-label*='unread'], .notification-badge"
        )
        is_unread = unread_el is not None

        # Timestamp
        timestamp = self._inner_text(item, [
            ".timestamp", ".time", "[data-e2e='timestamp']",
        ])

        if not sender:
            return None  # skip malformed items

        return Thread(
            thread_id=tid,
            sender=sender.strip(),
            preview=preview.strip(),
            is_unread=is_unread,
            timestamp=timestamp.strip(),
        )

    @staticmethod
    def _inner_text(parent, selectors: list[str]) -> str:
        for sel in selectors:
            el = parent.query_selector(sel)
            if el:
                txt = el.inner_text()
                if txt and txt.strip():
                    return txt.strip()
        return ""

    def _scroll_conversation_list_to_bottom(self) -> None:
        """Incrementally scroll the sidebar to trigger lazy-load."""
        page = self._page
        list_el = page.query_selector(
            "mws-conversations-list, .conversation-list, [data-e2e='conversation-list']"
        )
        if not list_el:
            return
        prev_count = 0
        for _ in range(30):  # max 30 scroll steps
            list_el.evaluate("el => el.scrollTop += 800")
            page.wait_for_timeout(400)
            count = len(page.query_selector_all(
                "mws-conversation-list-item, .conversation-list-item"
            ))
            if count == prev_count:
                break
            prev_count = count

    # ── Thread inspection ─────────────────────────────────────────────────────

    def open_thread(self, thread: Thread) -> None:
        """Click on a thread to open it in the message pane."""
        page = self._page
        # Try by thread ID attribute first, fall back to sender text match
        item = (
            page.query_selector(f"[data-e2e-conversation-id='{thread.thread_id}']")
            or page.query_selector(f"[data-conversation-id='{thread.thread_id}']")
        )
        if item:
            item.click()
        else:
            # Fallback: find by sender name visible text
            page.locator(
                "mws-conversation-list-item, .conversation-list-item"
            ).filter(has_text=thread.sender).first.click()
        page.wait_for_timeout(1_200)

    def read_messages_in_open_thread(self) -> list[Message]:
        """Return all messages in the currently open thread."""
        page = self._page
        page.wait_for_selector(
            "mws-message-part, .message-wrapper, [data-e2e='message-bubble']",
            timeout=config.BROWSER_TIMEOUT_MS,
        )
        bubbles = page.query_selector_all(
            "mws-message-part, .message-wrapper, [data-e2e='message-bubble'], .message-row"
        )
        messages: list[Message] = []
        for bubble in bubbles:
            text = bubble.inner_text().strip()
            if not text:
                continue
            outgoing = bool(
                bubble.query_selector(".outgoing, .sent, [data-e2e='outgoing']")
                or "outgoing" in (bubble.get_attribute("class") or "")
                or "sent" in (bubble.get_attribute("class") or "")
            )
            messages.append(Message(text=text, outgoing=outgoing))
        return messages

    # ── Deletion ──────────────────────────────────────────────────────────────

    def delete_thread(self, thread: Thread, *, dry_run: bool = True, confirm: bool = True) -> bool:
        """
        Delete the thread from the conversation list.

        Returns True if deleted (or would-be deleted in dry-run).
        """
        if dry_run:
            print(f"  [dry-run] Would delete: {thread.sender!r}")
            return True

        if confirm:
            ans = input(f"  Delete conversation with {thread.sender!r}? [y/N] ").strip().lower()
            if ans != "y":
                print("  Skipped.")
                return False

        page = self._page
        item = (
            page.query_selector(f"[data-e2e-conversation-id='{thread.thread_id}']")
            or page.query_selector(f"[data-conversation-id='{thread.thread_id}']")
        )
        if not item:
            # Fallback: locate by sender text
            item = page.locator(
                "mws-conversation-list-item, .conversation-list-item"
            ).filter(has_text=thread.sender).first.element_handle()

        if not item:
            print(f"  [browser] Could not locate thread item for {thread.sender!r} – skipped.")
            return False

        # Right-click → context menu
        item.click(button="right")
        page.wait_for_timeout(600)

        # Try to click "Delete" in the context menu
        deleted = False
        for sel in [
            "text=Delete", "[data-e2e='delete-option']", ".delete-option",
            "button:has-text('Delete')", "li:has-text('Delete')",
        ]:
            el = page.query_selector(sel)
            if el:
                el.click()
                deleted = True
                break

        if not deleted:
            print(f"  [browser] Delete menu item not found for {thread.sender!r}.")
            page.keyboard.press("Escape")
            return False

        # Confirm the deletion dialog if one appears
        page.wait_for_timeout(800)
        for sel in [
            "button:has-text('Delete')", "button:has-text('OK')",
            "[data-e2e='confirm-delete']", ".confirm-delete",
        ]:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                break

        page.wait_for_timeout(800)
        print(f"  [browser] Deleted: {thread.sender!r}")
        return True
