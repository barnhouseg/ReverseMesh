#!/usr/bin/env python3
"""
GoogleMessageManager — CLI entry point
=======================================
Scans your Google Messages inbox via the web interface, deletes automated/spam
threads, and highlights contact threads that contain questions or invitations.

Usage
-----
  # Dry run (default) — classify and report, no deletions:
  python run.py

  # Live run — actually delete automated threads (with per-thread confirmation):
  python run.py --live

  # Live run, no per-thread prompts:
  python run.py --live --no-confirm

  # Deep scan — open each automated thread to check for outgoing replies:
  python run.py --deep

  # Headless (requires an existing paired session):
  python run.py --headless

Prerequisites
-------------
  pip install playwright
  playwright install chromium

First run
---------
  The browser opens and shows the Google Messages QR pairing screen.
  Scan it from your phone: Messages → ⋮ → Device Pairing.
  The session is saved to ~/.GoogleMessageManager/ — no re-pairing on
  subsequent runs.
"""

import argparse
import sys

from GoogleMessageManager import config
from GoogleMessageManager.processor import run
from GoogleMessageManager.reporter import print_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GoogleMessageManager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--live", action="store_true",
        help="Actually delete automated threads (default: dry run only)",
    )
    p.add_argument(
        "--no-confirm", action="store_true",
        help="Skip per-thread confirmation prompts when --live is set",
    )
    p.add_argument(
        "--deep", action="store_true",
        help="Open each flagged thread and read all messages before deciding "
             "(slower but catches threads where you have replied to bots)",
    )
    p.add_argument(
        "--headless", action="store_true",
        help="Run browser in headless mode (requires an existing paired session)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.headless:
        config.HEADLESS = True

    dry_run = not args.live
    confirm = not args.no_confirm

    if not dry_run:
        print("\n[!] LIVE MODE: automated threads will be permanently deleted.")
        if confirm:
            print("[!] You will be prompted before each deletion.")
        else:
            print("[!] --no-confirm: all automated threads deleted without prompting.")
        ans = input("\nProceed? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            sys.exit(0)

    result = run(dry_run=dry_run, confirm_each=confirm, deep_scan=args.deep)
    print_report(result, dry_run=dry_run)


if __name__ == "__main__":
    main()
