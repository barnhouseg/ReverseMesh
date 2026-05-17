"""Shared data models (no browser dependencies)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Thread:
    thread_id: str
    sender: str
    preview: str
    is_unread: bool = False
    timestamp: str = ""


@dataclass
class Message:
    text: str
    outgoing: bool
