#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Network traffic scene for the Neos75 screen: live rates + 3-minute history."""
import threading
import time
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import lyrics_screen as L
import monitor

W, H = 480, 360
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

HISTORY_SECONDS = 180
_lock = threading.Lock()
_hist = deque(maxlen=HISTORY_SECONDS)     # (ts, down_bps, up_bps)
_last = {"t": 0.0, "recv": 0, "sent": 0}
_totals = {"recv": 0, "sent": 0}          # boot-time cumulative from the OS
_thread_started = False


def _sampler():
    global _last
    import psutil
    while True:
        try:
            now = time.time()
            c = psutil.net_io_counters()
            with _lock:
                _totals["recv"], _totals["sent"] = c.bytes_recv, c.bytes_sent
                if _last["t"]:
                    dt = max(0.05, now - _last["t"])
                    down = max(0.0, (c.bytes_recv - _last["recv"]) / dt)
                    up = max(0.0, (c.bytes_sent - _last["sent"]) / dt)
                    _hist.append((now, down, up))
                _last = {"t": now, "recv": c.bytes_recv, "sent": c.bytes_sent}
        except Exception:
            pass
        time.sleep(1.0)


def start():
    global _thread_started
    if not _thread_started:
        _thread_started = True
        threading.Thread(target=_sampler, daemon=True).start()


def rate_now():
    with _lock:
        if _hist:
            return _hist[-1][1], _hist[-1][2]
    return None, None


def totals():
    with _lock:
        return dict(_totals)


def history():
    with _lock:
        return list(_hist)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def render(cfg, out_path):
    """Draw the traffic card; same visual language as scenes.render_info."""
    start()
    base = L.module_bg(cfg, "mon", (W, H), veil=0.55)
    img = base if base is not None else Image.new("RGB", (W, H), cfg.get("bg_color") or "#090a0d")
    draw = ImageDraw.Draw(img)
    accent = cfg.get("accent") or "#4D6BFE"

    f_title = _font(FONT_BOLD, 20)
    draw.text((36, 30), "网络流量", font=f_title, fill=(246, 247, 250), anchor="lm")
    tot = totals()
    f_sub = _font(FONT, 15)
    draw.text((W - 36, 30), f"累计 ↓{_fmt_gb(tot.get('recv'))} ↑{_fmt_gb(tot.get('sent'))}",
              font=f_sub, fill=(150, 158, 172), anchor="rm")

    down, up = rate_now()
    f_big = _font(FONT_BOLD, 32)
    f_lbl = _font(FONT, 15)
    draw.text((48, 96), "↓", font=_font(FONT_BOLD, 28), fill=(0, 200, 160), anchor="lm")
    draw.text((82, 96), monitor.human_rate(down), font=f_big, fill=(246, 247, 250), anchor="lm")
    draw.text((48, 136), "实时下载", font=f_lbl, fill=(120, 128, 142), anchor="lm")
    draw.text((252, 96), "↑", font=_font(FONT_BOLD, 28), fill=accent, anchor="lm")
    draw.text((286, 96), monitor.human_rate(up), font=f_big, fill=(246, 247, 250), anchor="lm")
    draw.text((252, 136), "实时上传", font=f_lbl, fill=(120, 128, 142), anchor="lm")

    # 3-minute history bars
    hist = history()
    title = f"最近 {HISTORY_SECONDS // 60} 分钟（每秒采样）"
    draw.text((36, 182), title, font=_font(FONT, 15), fill=(140, 148, 162), anchor="lm")
    x0, y0, x1, y1 = 36, 200, W - 36, 296
    draw.rectangle([x0, y1, x1, y1 + 1], fill=(60, 64, 76))
    if len(hist) >= 2:
        peak = max((d + u for _t, d, u in hist), default=1.0) or 1.0
        n_bars = 48
        step = max(1, len(hist) // n_bars)
        bars = []
        for i in range(0, len(hist), step):
            chunk = hist[i:i + step]
            bars.append((sum(d for _t, d, u in chunk) / len(chunk),
                         sum(u for _t, d, u in chunk) / len(chunk)))
        slot = (x1 - x0) / n_bars
        bw = max(2, int(slot * 0.62))
        for i, (d, u) in enumerate(bars[:n_bars]):
            bx = x0 + int(i * slot)
            hd = int((y1 - y0 - 14) * min(1.0, d / peak))
            hu = int((y1 - y0 - 14) * min(1.0, u / peak))
            hd = max(hd, 1 if d > 2 else 0)
            hu = max(hu, 1 if u > 2 else 0)
            if hd:
                draw.rectangle([bx, y1 - hd, bx + bw, y1], fill=(0, 200, 160))
            if hu:
                draw.rectangle([bx, y1 - hd - hu, bx + bw, y1 - hd], fill=accent)

    f_tip = _font(FONT, 14)
    draw.text((36, 312), f"峰值 {_fmt_peak(hist)}", font=f_tip, fill=(120, 128, 142), anchor="lm")
    draw.text((W - 36, 312), time.strftime("%H:%M:%S"), font=f_tip, fill=(120, 128, 142), anchor="rm")
    draw.rectangle([60, 338, 420, 339], fill=(60, 64, 76))
    draw.rectangle([60, 338, 60 + 90, 339], fill=accent)

    img.save(out_path, "JPEG", quality=46, optimize=True, progressive=False, subsampling=2)
    if Path(out_path).stat().st_size > 9000:
        img.save(out_path, "JPEG", quality=38, optimize=True, progressive=False, subsampling=2)
    return Path(out_path).stat().st_size


def _fmt_gb(nbytes):
    try:
        gb = (nbytes or 0) / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.2f}GB"
        mb = (nbytes or 0) / (1024 ** 2)
        if mb >= 1:
            return f"{mb:.0f}MB"
        return f"{(nbytes or 0) / 1024:.0f}KB"
    except Exception:
        return "—"


def _fmt_peak(hist):
    if not hist:
        return "—"
    peak = max(d + u for _t, d, u in hist)
    return monitor.human_rate(peak)
