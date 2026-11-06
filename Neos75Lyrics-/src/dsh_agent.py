#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek Harness (DSH) scene: token usage, live cost, local-model speed.

Data source: ~/.dsh/sessions/<workspace>/session-*/session.v4.jsonl.zstd —
zstd-compressed JSONL where `assistant/message` events carry the model id,
token usage (input / output / cache) and the wall-clock time; step/start /
step/end pairs bound each generation so an output speed can be derived.

DSH has no subscription, so there is no plan quota: API models are billed per
token (configurable price table, estimates marked as such) while models
configured under `dsh_local_models` are free and show usage + speed only.

render(cfg, out_path, lock_state=None) follows the zcode_agent page language.
"""
import glob
import json
import os
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import lyrics_screen as L
from zcode_agent import lock_glyph

W, H = 480, 360
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

DSH_DIR = Path.home() / ".dsh"
SESSIONS_GLOB = str(DSH_DIR / "sessions" / "*" / "session-*" / "session.v4.jsonl.zstd")
RUNNING_WINDOW = 90          # seconds since last session write => running

# per-1M-token price estimates (CNY); overridable via config "dsh_prices"
DEFAULT_PRICES = {
    "default": {"in_miss": 2.0, "in_hit": 0.5, "out": 8.0},
    "deepseek-chat": {"in_miss": 2.0, "in_hit": 0.5, "out": 8.0},
    "deepseek-flash": {"in_miss": 2.0, "in_hit": 0.5, "out": 8.0},
    "deepseek-reasoner": {"in_miss": 4.0, "in_hit": 1.0, "out": 16.0},
}

_state = {"sessions": {}, "scanned_at": 0.0}
_lock = threading.Lock()
_thread_started = False


# ----------------------------------------------------------------- scanning
def _parse_session(path):
    """Decompress one session file; return (meta, events)."""
    import zstandard as zstd
    meta = {"cwd": "", "title": ""}
    events = []          # (time_s, model, in_tok, out_tok, cache_tok)
    steps = []           # (time_s, kind)
    try:
        dctx = zstd.ZstdDecompressor()
        with open(path, "rb") as fh:
            text = dctx.stream_reader(fh).read().decode("utf-8", errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("type")
            ts = (obj.get("time") or 0)
            ts = ts / 1000 if ts > 1e11 else float(ts or 0)
            if t == "session":
                meta["cwd"] = obj.get("cwd") or ""
            elif t == "session/title":
                meta["title"] = (obj.get("data") or {}).get("title") or meta["title"]
            elif t == "assistant/message":
                data = obj.get("data") or {}
                model = ((data.get("message") or {}).get("source") or {}).get("model") or "?"
                u = data.get("usage") or {}
                events.append((ts, model,
                               int(u.get("inputTokens") or 0),
                               int(u.get("outputTokens") or 0),
                               int(u.get("cacheReadTokens") or 0)))
            elif t in ("step/start", "step/end"):
                steps.append((ts, "end" if t == "step/end" else "start"))
    except Exception:
        pass
    return meta, events, steps


def _speed_of(events, step_bounds):
    """Latest output speed (tok/s): output tokens over the full step window."""
    speeds = []
    for ts, _m, _i, out, _c in events:
        if not out:
            continue
        for s0, s1 in step_bounds:
            if s0 <= ts <= s1:
                dt = max(1.0, s1 - s0)
                speeds.append(out / dt)
                break
    return speeds


def _scan():
    files = glob.glob(SESSIONS_GLOB)
    sessions = []
    for path in files:
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            continue
        with _lock:
            cached = _state["sessions"].get(path)
        if cached and cached["mtime"] == mtime:
            sessions.append(cached)
            continue
        meta, events, steps = _parse_session(path)
        events.sort(key=lambda e: e[0])
        starts = [ts for ts, k in steps if k == "start"]
        ends = [ts for ts, k in steps if k == "end"]
        bounds = []
        for s0 in starts:
            after = [e for e in ends if e >= s0]
            if after:
                bounds.append((s0, after[0]))
        speeds = _speed_of(events, bounds)
        # project name from the workspace folder: --C-...-deepseek-harness-default-workspace--
        folder = Path(path).parts[-3] if len(Path(path).parts) >= 3 else ""
        project = meta["cwd"].replace("/", "\\").split("\\")[-1] if meta["cwd"] else \
            folder.strip("-").split("--")[-1].replace("-", " ")
        rec = {"path": path, "mtime": mtime, "title": meta["title"],
               "project": project or "DSH", "events": events,
               "speeds": speeds, "last_ts": events[-1][0] if events else mtime}
        with _lock:
            _state["sessions"][path] = rec
        sessions.append(rec)
    with _lock:
        _state["scanned_at"] = time.time()
    return sessions


def _merger():
    while True:
        try:
            _scan()
        except Exception:
            pass
        time.sleep(20.0)


def start():
    global _thread_started
    if not _thread_started:
        _thread_started = True
        threading.Thread(target=_merger, daemon=True).start()


def snapshot():
    """Merged view: status, today usage/cost, per-model rows, recent sessions."""
    start()
    with _lock:
        recs = list(_state["sessions"].values())
        scanned_at = _state["scanned_at"]
    recs.sort(key=lambda r: r["last_ts"], reverse=True)
    now = time.time()
    running = any(now - r["mtime"] < RUNNING_WINDOW for r in recs)

    midnight_ts = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
    cfg = L.load_config()
    prices = dict(DEFAULT_PRICES)
    prices.update(cfg.get("dsh_prices") or {})
    local_marks = [m.lower() for m in (cfg.get("dsh_local_models") or [])]

    def is_local(model):
        low = (model or "").lower()
        return any(mark in low for mark in local_marks)

    def rates(model):
        return prices.get(model) or prices.get("default") or DEFAULT_PRICES["default"]

    today_in = today_out = today_cache = 0
    today_cost = 0.0
    total_in = total_out = total_cost = 0.0
    total_cost = 0.0
    per_model = {}
    requests_today = 0
    last_model = ""
    for rec in recs:
        for ts, model, tin, tout, tcache in rec["events"]:
            row = per_model.setdefault(model, {"in": 0, "out": 0, "cache": 0,
                                               "req": 0, "cost": 0.0, "local": is_local(model)})
            row["in"] += tin
            row["out"] += tout
            row["cache"] += tcache
            row["req"] += 1
            total_in += tin
            total_out += tout
            if not row["local"]:
                rt = rates(model)
                total_cost += (tin * rt["in_miss"] + tcache * rt["in_hit"]
                               + tout * rt["out"]) / 1e6
                row["cost"] += (tin * rt["in_miss"] + tcache * rt["in_hit"]
                                + tout * rt["out"]) / 1e6
            if ts >= midnight_ts:
                today_in += tin
                today_out += tout
                today_cache += tcache
                requests_today += 1
                if not row["local"]:
                    rt = rates(model)
                    today_cost += (tin * rt["in_miss"] + tcache * rt["in_hit"]
                                   + tout * rt["out"]) / 1e6
                last_model = model

    # latest speed from the most recent session with any speed sample
    speed = None
    for rec in recs:
        if rec["speeds"]:
            speed = rec["speeds"][-1]
            break

    sessions_view = [{"project": r["project"], "title": r["title"],
                      "when": max(r["last_ts"], r["mtime"]),
                      "state": ("running" if now - r["mtime"] < RUNNING_WINDOW
                                else "done")}
                     for r in recs[:3]]

    return {"running": running, "today_in": today_in, "today_out": today_out,
            "today_cache": today_cache, "today_cost": today_cost,
            "requests_today": requests_today, "total_cost": total_cost,
            "models": per_model, "speed": speed, "last_model": last_model,
            "sessions": sessions_view, "scanned_at": scanned_at}


# ------------------------------------------------------------------ helpers
def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _clip(draw, text, font, max_width):
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


# ------------------------------------------------------------------- render
def render(cfg, out_path, lock_state=None):
    """Draw the DSH page. lock_state: 'lock' (orange dot) / None (blue dot)."""
    snap = snapshot()
    base = L.module_bg(cfg, "mon", (W, H), veil=0.55)
    img = base if base is not None else Image.new("RGB", (W, H), cfg.get("bg_color") or "#090a0d")
    draw = ImageDraw.Draw(img)
    accent = cfg.get("accent") or "#4D6BFE"
    GREEN = (0, 200, 150)
    YELLOW = (255, 176, 32)

    # top bar: status right after the title; yellow running, green idle
    f_title = _font(FONT_BOLD, 24)
    draw.text((36, 34), "DeepSeek Harness", font=f_title, fill=(246, 247, 250), anchor="lm")
    dx = 36 + draw.textbbox((0, 0), "DeepSeek Harness", font=f_title)[2] + 14
    if snap["running"]:
        st_txt, st_col, dot = "任务进行中", YELLOW, YELLOW
    else:
        st_txt, st_col, dot = "空闲", GREEN, GREEN
    draw.ellipse([dx, 26, dx + 16, 42], fill=dot)
    draw.text((dx + 26, 34), st_txt, font=_font(FONT, 17), fill=st_col, anchor="lm")
    locked_dot = (lock_state == "lock")
    lock_glyph(draw, 432, 34, 24, (255, 176, 32) if locked_dot else accent, locked_dot)

    # recent sessions
    sessions = snap.get("sessions") or []
    draw.text((36, 74), "最近会话", font=_font(FONT, 15), fill=(140, 148, 162), anchor="lm")
    if sessions:
        dot_map = {"running": (0, 200, 160), "done": (110, 118, 132)}
        for i, s in enumerate(sessions[:3]):
            y = 122 + i * 52
            sd = dot_map.get(s["state"], (110, 118, 132))
            draw.ellipse([36, y - 7, 50, y + 7], fill=sd)
            proj = _clip(draw, s["project"], _font(FONT_BOLD, 17), 130)
            draw.text((62, y), proj, font=_font(FONT_BOLD, 17), fill=(246, 247, 250), anchor="lm")
            title_w = W - 62 - 190
            if s.get("title") and title_w > 60:
                draw.text((62 + draw.textbbox((0, 0), proj + "  ", font=_font(FONT_BOLD, 17))[2], y),
                          _clip(draw, s["title"], _font(FONT, 16), title_w),
                          font=_font(FONT, 16), fill=(170, 176, 190), anchor="lm")
            when = time.strftime("%m-%d %H:%M", time.localtime(s.get("when") or 0))
            state_txt = "进行中" if s["state"] == "running" else "已完成"
            draw.text((W - 36, y - 10), state_txt, font=_font(FONT_BOLD, 16),
                      fill=(255, 176, 32) if s["state"] == "running" else (170, 176, 190),
                      anchor="rm")
            draw.text((W - 36, y + 14), when, font=_font(FONT, 15), fill=(120, 128, 142), anchor="rm")
    else:
        draw.text((36, 110), "未找到 DSH 会话", font=_font(FONT, 15), fill=(110, 118, 132), anchor="lm")

    draw.rectangle([36, 262, W - 36, 263], fill=(44, 50, 64))

    # bottom: tokens (left) / speed (mid) / today cost (right) — same size
    tin, tout = snap.get("today_in") or 0, snap.get("today_out") or 0
    draw.text((36, 300), _hum(tin + tout), font=_font(FONT_BOLD, 36),
              fill=(246, 247, 250), anchor="lm")
    draw.text((36, 338), f"今日 tokens · 入 {_hum(tin)} 出 {_hum(tout)}",
              font=_font(FONT, 12), fill=(120, 128, 142), anchor="lm")

    spd = snap.get("speed")
    spd_txt = "—" if not spd else (f"{spd:.0f}" if spd >= 100 else f"{spd:.1f}")
    draw.text((240, 300), spd_txt, font=_font(FONT_BOLD, 36),
              fill=(246, 247, 250), anchor="lm")
    draw.text((240, 338), "输出 tok/s", font=_font(FONT, 12),
              fill=(120, 128, 142), anchor="lm")

    cost = snap.get("today_cost") or 0.0
    draw.text((W - 36, 300), f"¥{cost:.2f}", font=_font(FONT_BOLD, 36),
              fill=accent, anchor="rm")
    draw.text((W - 36, 338), "今日 API 费用", font=_font(FONT, 12),
              fill=(120, 128, 142), anchor="rm")

    draw.rectangle([60, 352, 420, 353], fill=(60, 64, 76))
    draw.rectangle([60, 352, 60 + 90, 353], fill=accent)

    img.save(out_path, "JPEG", quality=46, optimize=True, progressive=False, subsampling=2)
    if Path(out_path).stat().st_size > 9000:
        img.save(out_path, "JPEG", quality=38, optimize=True, progressive=False, subsampling=2)
    return Path(out_path).stat().st_size
