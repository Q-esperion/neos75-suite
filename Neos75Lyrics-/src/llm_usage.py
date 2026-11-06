#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM usage/balance scene: DeepSeek balance, Zhipu coding-plan quota, local GLM usage."""
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import lyrics_screen as L
import zcode_agent

W, H = 480, 360
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TTL = 300.0

_cache = {"deepseek": {"t": 0.0, "data": None},
          "zhipu": {"t": 0.0, "data": None}}
_last_error = {"deepseek": "", "zhipu": ""}


def _provider_deepseek_key():
    """Fall back to the key stored by ZCode for its DeepSeek provider."""
    path = Path.home() / ".zcode" / "v2" / "provider_config.json"
    try:
        pc = json.loads(path.read_text(encoding="utf-8"))
        rules = ((pc.get("config") or {}).get("providerConfigRules") or {}).get("providerRules") or []
        for rule in rules:
            if rule.get("providerId") == "deepseek":
                return (((rule.get("config") or {}).get("access") or {}).get("apiKey") or "").strip() or None
    except Exception:
        pass
    return None


def _get_json(url, key, timeout=12):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def deepseek(cfg, force=False):
    """{'total': '12.22', 'granted': '0.00', 'topped': '12.22', 'currency': 'CNY'}"""
    now = time.time()
    c = _cache["deepseek"]
    if not force and c["data"] and now - c["t"] < TTL:
        return c["data"]
    key = (cfg.get("deepseek_key") or "").strip() or _provider_deepseek_key()
    if not key:
        _last_error["deepseek"] = "未配置 API Key"
        return c["data"]
    try:
        data = _get_json("https://api.deepseek.com/user/balance", key)
        infos = (data.get("balance_infos") or [{}])[0]
        out = {"total": infos.get("total_balance") or "—",
               "granted": infos.get("granted_balance") or "0.00",
               "topped": infos.get("topped_up_balance") or "0.00",
               "currency": infos.get("currency") or "CNY",
               "available": bool(data.get("is_available"))}
        _cache["deepseek"].update({"t": now, "data": out})
        _last_error["deepseek"] = ""
        return out
    except Exception as exc:
        _last_error["deepseek"] = str(exc)[:60]
        return c["data"]


def zhipu(cfg, force=False):
    """{'level': 'lite', 'windows': [{'label', 'used', 'limit', 'pct', 'reset'}]}"""
    now = time.time()
    c = _cache["zhipu"]
    if not force and c["data"] and now - c["t"] < TTL:
        return c["data"]
    key = (cfg.get("zhipu_api_key") or "").strip()
    if not key:
        _last_error["zhipu"] = "未配置 API Key"
        return c["data"]
    try:
        data = _get_json("https://open.bigmodel.cn/api/monitor/usage/quota/limit", key)
        payload = data.get("data") or {}
        out = {"level": (payload.get("level") or "").upper(), "windows": []}
        for item in payload.get("limits") or []:
            unit, number = item.get("unit"), item.get("number")
            label = {3: "5小时窗口", 6: "本周窗口"}.get(unit, f"窗口{unit}/{number}")
            reset = item.get("nextResetTime")
            out["windows"].append({
                "label": label,
                "used": item.get("currentValue") or 0,
                "limit": item.get("usage") or 0,
                "pct": item.get("percentage") or 0,
                "reset": (reset / 1000) if isinstance(reset, (int, float)) else None,
            })
        _cache["zhipu"].update({"t": now, "data": out})
        _last_error["zhipu"] = ""
        return out
    except Exception as exc:
        _last_error["zhipu"] = str(exc)[:60]
        return c["data"]


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _panel(draw, x0, y0, x1, y1):
    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=(24, 28, 38))


def render(cfg, out_path):
    base = L.module_bg(cfg, "mon", (W, H), veil=0.55)
    img = base if base is not None else Image.new("RGB", (W, H), cfg.get("bg_color") or "#090a0d")
    draw = ImageDraw.Draw(img)
    accent = cfg.get("accent") or "#4D6BFE"

    f_title = _font(FONT_BOLD, 20)
    draw.text((36, 30), "大模型用量", font=f_title, fill=(246, 247, 250), anchor="lm")
    draw.text((W - 36, 30), time.strftime("%H:%M"), font=_font(FONT, 14), fill=(110, 118, 132), anchor="rm")

    ds = deepseek(cfg) or {}
    zp = zhipu(cfg) or {}
    local = zcode_agent.snapshot().get("usage") or {}

    # --- DeepSeek card (left) ---
    _panel(draw, 36, 56, 226, 168)
    draw.text((52, 74), "DeepSeek 余额", font=_font(FONT, 14), fill=(140, 148, 162), anchor="lm")
    if ds:
        cur = "¥" if (ds.get("currency") or "CNY").upper() == "CNY" else "$"
        draw.text((52, 106), f"{cur}{ds.get('total', '—')}", font=_font(FONT_BOLD, 30),
                  fill=(246, 247, 250), anchor="lm")
        draw.text((52, 146), f"赠金 {ds.get('granted', '—')} · 充值 {ds.get('topped', '—')}",
                  font=_font(FONT, 13), fill=(150, 158, 172), anchor="lm")
    else:
        draw.text((52, 112), "—" + (f"（{_last_error['deepseek'][:18]}）" if _last_error["deepseek"] else ""),
                  font=_font(FONT, 16), fill=(120, 128, 142), anchor="lm")

    # --- Zhipu card (right): remaining quota as two donut rings ---
    _panel(draw, 254, 56, 444, 168)
    level = zp.get("level") or "CODING"
    draw.text((270, 74), f"智谱 Coding {level} · 剩余", font=_font(FONT, 14), fill=(140, 148, 162), anchor="lm")
    if zp and zp.get("windows"):
        ring_colors = [accent, (0, 200, 150)]       # 5h window blue, weekly green
        centers = [(308, 118), (400, 118)]
        labels = ["5小时", "本周"]
        for i, wdw in enumerate(zp["windows"][:2]):
            rem_pct = max(0, min(100, 100 - int(wdw.get("pct") or 0)))
            cx, cy = centers[i]
            r = 25
            box = [cx - r, cy - r, cx + r, cy + r]
            draw.ellipse(box, outline=(44, 50, 64), width=6)
            if rem_pct > 0:
                draw.arc(box, start=-90, end=-90 + 360 * rem_pct / 100.0,
                         fill=ring_colors[i % 2], width=6)
            draw.text((cx, cy), f"{rem_pct:02d}", font=_font(FONT_BOLD, 21),
                      fill=(246, 247, 250), anchor="mm")
            remaining = max(0, (wdw.get("limit") or 0) - (wdw.get("used") or 0))
            draw.text((cx, cy + r + 12), f"{labels[i]} 剩{zcode_agent._hum(remaining)}",
                      font=_font(FONT, 12), fill=(150, 158, 172), anchor="mm")
    else:
        msg = _last_error["zhipu"][:20] or "等待数据"
        draw.text((270, 112), "—" + (f"（{msg}）" if msg != "等待数据" else ""),
                  font=_font(FONT, 16), fill=(120, 128, 142), anchor="lm")

    # --- Local GLM usage (bottom) ---
    _panel(draw, 36, 186, 444, 306)
    draw.text((52, 204), "GLM 今日用量（本地统计）", font=_font(FONT, 14), fill=(140, 148, 162), anchor="lm")
    tokens = local.get("tokens") or 0
    reqs = local.get("requests") or 0
    cache = local.get("cache") or 0
    draw.text((52, 240), zcode_agent._hum(tokens), font=_font(FONT_BOLD, 40), fill=(246, 247, 250), anchor="lm")
    draw.text((52, 290), f"tokens · 缓存命中 {_zhum(cache)}",
              font=_font(FONT, 12), fill=(120, 128, 142), anchor="lm")
    draw.text((330, 240), f"{reqs}", font=_font(FONT_BOLD, 40), fill=accent, anchor="rm")
    draw.text((330, 290), "模型请求次数", font=_font(FONT, 12), fill=(120, 128, 142), anchor="rm")

    draw.text((36, 322), f"余额每 5 分钟刷新 · DeepSeek {time.strftime('%H:%M', time.localtime(_cache['deepseek']['t'])) if _cache['deepseek']['t'] else '—'} · 智谱 {time.strftime('%H:%M', time.localtime(_cache['zhipu']['t'])) if _cache['zhipu']['t'] else '—'}",
              font=_font(FONT, 12), fill=(110, 118, 132), anchor="lm")
    draw.rectangle([60, 338, 420, 339], fill=(60, 64, 76))
    draw.rectangle([60, 338, 60 + 90, 339], fill=accent)

    img.save(out_path, "JPEG", quality=46, optimize=True, progressive=False, subsampling=2)
    if Path(out_path).stat().st_size > 9000:
        img.save(out_path, "JPEG", quality=38, optimize=True, progressive=False, subsampling=2)
    return Path(out_path).stat().st_size


def _zhum(tokens):
    t = tokens or 0
    if t >= 1_000_000:
        return f"{t / 1_000_000:.1f}M"
    if t >= 1_000:
        return f"{t / 1000:.1f}K"
    return str(t)
