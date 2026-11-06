#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZCode agent progress scene: hook event stream + local token usage."""
import glob
import json
import os
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import lyrics_screen as L

W, H = 480, 360
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

WORK = Path(os.environ.get("NEOS75_DASH_DIR", str(Path.home() / ".neos75_dashboard")))
EVENTS = WORK / "events.jsonl"
ROLLOUT_DIR = Path.home() / ".zcode" / "cli" / "rollout"
ACTIVE_WINDOW = 180          # seconds: hook events within this => agent "running"

_state_lock = threading.Lock()
_state = {"rows": [], "usage": {"tokens": 0, "requests": 0, "cache": 0},
          "usage_day": "", "scanned_at": 0.0,
          "last_io_at": 0.0, "last_io_size": 0,
}
_scan_offsets = {}           # file -> bytes already parsed (per-day cache keeps totals)
_scan_thread = False


def _load_rows():
    """Tail the events file; keep the freshest 40 rows in memory."""
    try:
        size = EVENTS.stat().st_size
        with open(EVENTS, "rb") as fh:
            start = max(0, size - 64 * 1024)
            fh.seek(start)
            blob = fh.read().decode("utf-8", errors="ignore")
        if start:
            blob = blob[blob.find("\n") + 1:] if "\n" in blob else blob
        rows = []
        for line in blob.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-40:]
    except Exception:
        return []


def _day_stamp():
    return time.strftime("%Y%m%d")


def _scan_usage():
    """Incrementally parse today's model-io files for token totals."""
    import datetime
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    usage = {"tokens": 0, "requests": 0, "cache": 0}
    try:
        files = glob.glob(str(ROLLOUT_DIR / "model-io-sess_*.jsonl"))
        for path in files:
            try:
                st = os.stat(path)
                if st.st_mtime < today:
                    continue
                off = _scan_offsets.get(path, 0)
                if off == st.st_size:
                    continue  # nothing new
                tokens = reqs = cache = 0
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    if off:
                        fh.seek(off)
                    while True:
                        line = fh.readline()
                        if not line:
                            break
                        time.sleep(0)          # yield GIL: big rows parse for ms
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        resp = obj.get("response") or {}
                        u = resp.get("usage") or {}
                        it, ot = u.get("inputTokens"), u.get("outputTokens")
                        if isinstance(it, (int, float)) or isinstance(ot, (int, float)):
                            tokens += int(it or 0) + int(ot or 0)
                            reqs += 1
                            meta = ((resp.get("providerMetadata") or {}).get("anthropic") or {}).get("usage") or {}
                            cache += int(meta.get("cache_read_input_tokens") or 0)
                        time.sleep(0)          # yield GIL during heavy rows
                    _scan_offsets[path] = fh.tell()
                usage["tokens"] += tokens
                usage["requests"] += reqs
                usage["cache"] += cache
            except Exception:
                continue
    except Exception:
        pass
    return usage


def _merger():
    tick = 0
    while True:
        try:
            rows = _load_rows()
            with _state_lock:
                _state["rows"] = rows
            if tick % 2 == 0:   # rollout growth probe every 20s
                _probe_io_growth()
            if tick % 6 == 0:   # usage scan every 60s; events every 10s
                day = _day_stamp()
                with _state_lock:
                    prev = _state.get("usage") or {}
                    if _state.get("usage_day") != day:
                        _scan_offsets.clear()
                        prev = {"tokens": 0, "requests": 0, "cache": 0}
                        _state["usage_day"] = day
                inc = _scan_usage()
                with _state_lock:
                    cur = _state.get("usage") or {}
                    _state["usage"] = {
                        "tokens": prev.get("tokens", 0) + inc["tokens"],
                        "requests": prev.get("requests", 0) + inc["requests"],
                        "cache": prev.get("cache", 0) + inc["cache"],
                    }
                    _state["scanned_at"] = time.time()
        except Exception:
            pass
        tick += 1
        time.sleep(10.0)


def _probe_io_growth():
    """Total size of today's rollout files; growth means the model is producing."""
    import datetime
    try:
        today0 = datetime.datetime.now().replace(hour=0, minute=0, second=0,
                                                 microsecond=0).timestamp()
        total = 0
        newest = 0.0
        for path in glob.glob(str(ROLLOUT_DIR / "model-io-sess_*.jsonl")):
            st = os.stat(path)
            if st.st_mtime >= today0:
                total += st.st_size
                newest = max(newest, st.st_mtime)
        with _state_lock:
            prev = _state.get("last_io_size") or 0
            if total > prev and _state.get("last_io_size"):
                _state["last_io_at"] = time.time()
            elif not _state.get("last_io_size"):
                # first probe: seed the baseline; a file written <90s ago counts
                if newest and time.time() - newest < 90:
                    _state["last_io_at"] = time.time()
            _state["last_io_size"] = total
    except Exception:
        pass


def start():
    global _scan_thread
    if not _scan_thread:
        _scan_thread = True
        threading.Thread(target=_merger, daemon=True).start()


def snapshot():
    """Merged view for rendering: activity + history + today's token totals."""
    start()
    with _state_lock:
        rows = list(_state["rows"])
        usage = dict(_state["usage"])
        scanned_at = _state["scanned_at"]
        last_io_at = _state.get("last_io_at") or 0.0
    # two activity signals: hook events (tool-level detail) and rollout file
    # growth (model output; works even when hooks are not registered yet)
    last_ts = max((r.get("ts") or 0 for r in rows), default=0.0)
    age = time.time() - last_ts if last_ts else None
    io_age = time.time() - last_io_at if last_io_at else None
    if (age is not None and age < ACTIVE_WINDOW) or (io_age is not None and io_age < 90):
        state = "running"
    elif (age is not None and age < ACTIVE_WINDOW * 4) or (io_age is not None and io_age < 600):
        state = "waiting"
    else:
        state = "idle"
    # history: completed tool calls (post/failure), newest last
    history = []
    current = None
    for r in rows:
        ev, tool = r.get("event"), r.get("tool") or ""
        if ev == "PreToolUse":
            current = {"tool": tool, "detail": r.get("detail") or "", "ts": r.get("ts") or 0}
        elif ev in ("PostToolUse", "PostToolUseFailure"):
            if current and current["tool"] == tool:
                current = None
            history.append({"ok": ev == "PostToolUse", "tool": tool,
                            "detail": r.get("detail") or "", "ts": r.get("ts") or 0})
        elif ev == "UserPromptSubmit":
            history.append({"ok": True, "tool": "▶ 需求", "detail": r.get("detail") or "",
                            "ts": r.get("ts") or 0})
        elif ev == "Stop":
            history.append({"ok": True, "tool": "■ 完成", "detail": "", "ts": r.get("ts") or 0})
    return {"state": state, "age": age, "io_age": io_age, "current": current,
            "history": history[-6:], "usage": usage, "sessions": sessions(),
            "scanned_at": scanned_at}


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def lock_glyph(draw, cx, cy, size, color, locked):
    """Small padlock centered at (cx, cy). Closed shackle when locked, an
    open lifted shackle when not — colored per caller."""
    lw = max(2, int(size * 0.17))
    body_w = size * 0.82
    body_h = size * 0.62
    x0, y0 = cx - body_w / 2, cy - size * 0.05
    x1, y1 = cx + body_w / 2, y0 + body_h
    r = body_w * 0.34
    if locked:
        # closed: full arch over the body
        draw.arc([cx - r, y0 - r * 1.7, cx + r, y0 + r * 0.3],
                 start=180, end=360, fill=color, width=lw)
    else:
        # open: arch lifted and swung to the right, gap visible
        draw.arc([cx - r * 0.1, y0 - r * 2.1, cx + r * 1.7, y0 - r * 0.1],
                 start=180, end=360, fill=color, width=lw)
        draw.line([cx + r * 1.6, y0 - r * 1.1, cx + r * 1.6, y0 - r * 0.1],
                  fill=color, width=lw)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=size * 0.16, fill=color)
    kh = max(2, int(size * 0.09))
    draw.ellipse([cx - kh, cy + body_h * 0.05 - kh,
                  cx + kh, cy + body_h * 0.05 + kh], fill=(18, 20, 26))


def render(cfg, out_path, lock_state=None):
    """Draw the ZCode page. lock_state: 'lock' (orange lock) / None (blue lock)."""
    snap = snapshot()
    base = L.module_bg(cfg, "mon", (W, H), veil=0.55)
    img = base if base is not None else Image.new("RGB", (W, H), cfg.get("bg_color") or "#090a0d")
    draw = ImageDraw.Draw(img)
    accent = cfg.get("accent") or "#4D6BFE"
    GREEN = (0, 200, 150)
    YELLOW = (255, 176, 32)

    # top bar (enlarged type): task state yellow while active, green when idle
    f_title = _font(FONT_BOLD, 24)
    draw.text((36, 34), "ZCode Agent", font=f_title, fill=(246, 247, 250), anchor="lm")
    if snap["state"] == "running":
        sub, sub_col, dot = "任务进行中", YELLOW, YELLOW
    elif snap["state"] == "waiting":
        sub, sub_col, dot = "会话间歇", YELLOW, YELLOW
    else:
        sub, sub_col, dot = "空闲", GREEN, GREEN
    draw.ellipse([268, 26, 284, 42], fill=dot)
    draw.text((294, 34), sub, font=_font(FONT, 17), fill=sub_col, anchor="lm")
    # top-right: colored padlock — orange closed = locked, blue open = auto
    locked_dot = (lock_state == "lock")
    lock_glyph(draw, 432, 34, 24, (255, 176, 32) if locked_dot else accent, locked_dot)

    # recent sessions: project, title, running/done state, finish time
    sessions = snap.get("sessions") or []
    draw.text((36, 74), "最近会话", font=_font(FONT, 15), fill=(140, 148, 162), anchor="lm")
    if sessions:
        # status colors: yellow = in progress, green = done today,
        # red = errored, gray = finished more than a day ago
        dot_map = {"running": (255, 176, 32), "error": (255, 92, 92),
                   "done_today": (0, 200, 160), "done_old": (110, 118, 132),
                   "idle": (150, 158, 172)}
        text_map = {"running": (255, 176, 32), "error": (255, 92, 92),
                    "done_today": (0, 200, 160), "done_old": (170, 176, 190),
                    "idle": (150, 158, 172)}
        for i, s in enumerate(sessions[:3]):
            y = 122 + i * 52
            sd = dot_map.get(s["state"], (110, 118, 132))
            draw.ellipse([36, y - 7, 50, y + 7], fill=sd)
            proj = _clip(draw, s["project"], _font(FONT_BOLD, 17), 130)
            draw.text((62, y), proj, font=_font(FONT_BOLD, 17), fill=(246, 247, 250), anchor="lm")
            title = s.get("title") or ""
            title_w = W - 62 - 190          # leave the right column to state/time
            if title_w > 60:
                draw.text((62 + draw.textbbox((0, 0), proj + "  ", font=_font(FONT_BOLD, 17))[2], y),
                          _clip(draw, title, _font(FONT, 16), title_w),
                          font=_font(FONT, 16), fill=(170, 176, 190), anchor="lm")
            when = time.strftime("%m-%d %H:%M", time.localtime(s.get("when") or 0))
            state_txt = {"running": "进行中", "error": "出错", "done_today": "已完成",
                         "done_old": "已完成", "idle": "空闲"}.get(s["state"], "")
            draw.text((W - 36, y - 10), state_txt, font=_font(FONT_BOLD, 16),
                      fill=text_map.get(s["state"], (170, 176, 190)), anchor="rm")
            draw.text((W - 36, y + 14), when, font=_font(FONT, 15), fill=(120, 128, 142), anchor="rm")
    else:
        draw.text((36, 110), "未找到会话记录", font=_font(FONT, 15), fill=(110, 118, 132), anchor="lm")

    draw.rectangle([36, 262, W - 36, 263], fill=(44, 50, 64))

    # bottom: today usage (left, bigger) + zhipu remaining rings (right)
    usage = snap.get("usage") or {}
    draw.text((36, 296), _hum(usage.get("tokens")), font=_font(FONT_BOLD, 38),
              fill=(246, 247, 250), anchor="lm")
    draw.text((36, 334), f"今日 tokens · {usage.get('requests', 0)} 次请求",
              font=_font(FONT, 13), fill=(120, 128, 142), anchor="lm")

    try:
        import llm_usage
        zp = llm_usage.zhipu(cfg) or {}
    except Exception:
        zp = {}
    wins = (zp.get("windows") or [])[:2]
    ring_colors = [accent, GREEN]
    ring_labels = ["5h", "周"]
    centers = [(334, 300), (412, 300)]
    if wins:
        for i, wdw in enumerate(wins):
            rem_pct = max(0, min(100, 100 - int(wdw.get("pct") or 0)))
            cx, cy = centers[i]
            r = 27
            box = [cx - r, cy - r, cx + r, cy + r]
            draw.ellipse(box, outline=(44, 50, 64), width=7)
            if rem_pct > 0:
                draw.arc(box, start=-90, end=-90 + 360 * rem_pct / 100.0,
                         fill=ring_colors[i % 2], width=7)
            draw.text((cx, cy), f"{rem_pct:02d}", font=_font(FONT_BOLD, 21),
                      fill=(246, 247, 250), anchor="mm")
            remaining = max(0, (wdw.get("limit") or 0) - (wdw.get("used") or 0))
            draw.text((cx, cy + r + 11), f"{ring_labels[i]} 剩{_hum(remaining)}",
                      font=_font(FONT, 12), fill=(150, 158, 172), anchor="mm")
    else:
        draw.text((334, 300), "--", font=_font(FONT_BOLD, 24), fill=(110, 118, 132), anchor="mm")
        draw.text((412, 300), "--", font=_font(FONT_BOLD, 24), fill=(110, 118, 132), anchor="mm")
        draw.text((373, 334), "智谱配额未配置", font=_font(FONT, 12), fill=(110, 118, 132), anchor="mm")

    draw.rectangle([60, 350, 420, 351], fill=(60, 64, 76))
    draw.rectangle([60, 350, 60 + 90, 351], fill=accent)

    img.save(out_path, "JPEG", quality=46, optimize=True, progressive=False, subsampling=2)
    if Path(out_path).stat().st_size > 9000:
        img.save(out_path, "JPEG", quality=38, optimize=True, progressive=False, subsampling=2)
    return Path(out_path).stat().st_size


_sessions_cache = {"t": 0.0, "rows": []}


def sessions():
    """Recent ZCode sessions: project, title, status, last activity.

    Reads ZCode's own task index (read-only), enriched with rollout file
    freshness so an actively producing session shows as running.
    """
    now = time.time()
    if _sessions_cache["rows"] and now - _sessions_cache["t"] < 5:
        return _sessions_cache["rows"]
    rows = []
    try:
        import sqlite3
        db = Path.home() / ".zcode" / "v2" / "tasks-index.sqlite"
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        rows = cur.execute(
            """SELECT workspace_path, task_id, title, task_status, updated_at,
                      cli_last_outcome
               FROM tasks WHERE deleted = 0 AND archived = 0
               ORDER BY updated_at DESC LIMIT 3""").fetchall()
        con.close()
    except Exception:
        rows = []
    midnight = time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d")
    midnight_ts = time.mktime(midnight)
    out = []
    for ws, tid, title, status, updated, outcome in rows:
        project = (ws or "").replace("/", chr(92)).split(chr(92))[-1] or "unknown"
        mtime = 0.0
        try:
            mtime = os.path.getmtime(str(ROLLOUT_DIR / f"model-io-{tid}.jsonl"))
        except Exception:
            pass
        when = max(mtime, (updated or 0) / 1000)
        # error beats everything the index claims: an outcome/status that
        # mentions a failure means the session ended badly
        blob = f"{outcome or ''} {status or ''}".lower()
        if any(k in blob for k in ("error", "fail", "abort", "crash")):
            state = "error"
        elif mtime and (now - mtime) < 90:
            state = "running"
        elif status == "completed":
            # finished today -> green, finished earlier -> the usual gray
            state = "done_today" if when >= midnight_ts else "done_old"
        else:
            state = "idle"
        out.append({"project": project, "title": title or "", "state": state,
                    "when": when})
    _sessions_cache.update({"t": now, "rows": out})
    return out


def _clip(draw, text, font, max_width):
    """Trim with an ellipsis so the row never runs past the screen edge."""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    out = text
    while out and draw.textbbox((0, 0), out + "…", font=font)[2] > max_width:
        out = out[:-1]
    return out + "…"


def _hum(tokens):
    t = tokens or 0
    if t >= 1_000_000:
        return f"{t / 1_000_000:.1f}M"
    if t >= 1_000:
        return f"{t / 1000:.1f}K"
    return str(t)
