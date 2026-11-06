#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZCode hook sink: append session events to a JSONL file for the screen page.

Registered in ~/.zcode/cli/config.json for SessionStart / UserPromptSubmit /
PreToolUse / PostToolUse / PostToolUseFailure / Stop. Must stay fast and silent:
no network, no output, always exit 0.
"""
import json
import os
import sys
import time
from pathlib import Path

WORK = Path(os.environ.get("NEOS75_DASH_DIR", str(Path.home() / ".neos75_dashboard")))
EVENTS = WORK / "events.jsonl"
MAX_BYTES = 2 * 1024 * 1024

TOOL_FIELDS = ("file_path", "path", "command", "description", "pattern", "url",
               "query", "skill", "command_name", "notebook_path", "file")


def detail_of(name, payload):
    """One-line human summary of a tool call, kept short for the 480px screen."""
    inp = payload.get("tool_input") or payload.get("tool_response") or {}
    if isinstance(inp, str):
        inp = {"text": inp}
    for field in TOOL_FIELDS:
        val = inp.get(field)
        if isinstance(val, str) and val.strip():
            text = " ".join(val.split())
            return f"{field}={text[:110]}"
    text = payload.get("prompt") or ""
    if isinstance(text, str) and text.strip():
        return " ".join(text.split())[:110]
    return ""


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    raw = ""
    try:
        import threading
        timer = threading.Timer(2.0, lambda: os._exit(0))
        timer.start()
        raw = sys.stdin.read()
        timer.cancel()
    except Exception:
        return
    if not raw.strip():
        return
    try:
        payload = json.loads(raw)
    except Exception:
        return
    event = payload.get("hook_event_name") or "Unknown"
    row = {
        "ts": time.time(),
        "session": (payload.get("session_id") or "")[-12:],
        "event": event,
        "tool": payload.get("tool_name") or "",
        "detail": detail_of(event, payload),
    }
    try:
        if EVENTS.exists() and EVENTS.stat().st_size > MAX_BYTES:
            data = EVENTS.read_bytes()
            keep = data[len(data) // 2:]
            nl = keep.find(b"\n")
            if nl >= 0:
                keep = keep[nl + 1:]
            tmp = EVENTS.with_suffix(".tmp")
            tmp.write_bytes(keep)
            os.replace(tmp, EVENTS)
    except Exception:
        pass
    try:
        with open(EVENTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
