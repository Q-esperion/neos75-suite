#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot structural patch: split the dash page into three module pages."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "Neos75Lyrics-" / "src" / "Neos75Lyrics.py"
text = SRC.read_text(encoding="utf-8")

# 1) replace the pages dict: dash -> three module pages
text = text.replace(
    """            "mon": self._page_monitor(),
            "dash": self._page_dash(),""",
    """            "mon": self._page_monitor(),
            "zcode": self._page_zcode(),
            "traffic": self._page_traffic(),
            "llm": self._page_llm(),""")

# 2) sidebar: replace the single dash entry with three entries
text = text.replace(
    '''("mon", "监控", "▤"), ("dash", "仪表", "◈"),''',
    '''("mon", "监控", "▤"), ("zcode", "ZCode", "⌘"),
                                  ("traffic", "流量", "⇅"), ("llm", "用量", "¥"),''')

# 3) replace the whole dashboard section with the three module pages
start = text.index("    # ---------------------------------------------------------------- dashboard")
end = text.index("    # ------------------------------------------------------------------ game")
new_section = '''    # --------------------------------------- zcode / traffic / llm pages
    PAGE_NAMES = {"zcode": "ZCode Agent", "traffic": "网络流量",
                  "llm": "大模型用量", "info": "信息屏"}

    def _module_page(self, key, title, subtitle, extra_builder=None):
        """Shared scaffold: head + toggle + push pill + status + preview."""
        frame = tk.Frame(self.main, bg=BG)
        head = tk.Frame(frame, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=title, bg=BG, fg=FG, font=(FONT, 15, "bold")).pack(side="left")
        tk.Label(head, text=subtitle, bg=BG, fg=DIM, font=(FONT, 9)).pack(side="left", padx=10)
        sc = self.cfg.get("scenes", {}) or {}
        var = tk.BooleanVar(value=bool(sc.get(key, True)))
        self.dash_toggle[key] = var
        tg = Toggle(head, "自动推送", var, accent=self.accent)
        tg.oncommand(self.save_cfg)
        tg.pack(side="right")
        pill(head, "推送到屏幕", lambda k=key: self.push_module_ui(k), "primary", width=10,
             size=9, accent=self.accent).pack(side="right", padx=10)

        card = Card(frame, bg=CARD, radius=20, padx=18, pady=14, expand=True)
        card.pack(fill="both", expand=True, pady=(12, 8))
        body = card.body
        st = tk.Label(body, text="—", bg=CARD, fg=MUTED, font=(FONT, 10), anchor="w",
                      justify="left", wraplength=560)
        st.pack(fill="x")
        self.dash_status[key] = st
        hint = tk.Label(body, text="", bg=CARD, fg=DIM, font=(FONT, 9), anchor="w",
                        justify="left", wraplength=560)
        hint.pack(fill="x", pady=(4, 8))
        if extra_builder:
            extra_builder(body)
        prev = tk.Label(body, bg=CARD, text="等待渲染…", fg=DIM, font=(FONT, 9))
        prev.pack(anchor="w", pady=(6, 0))
        self._module_prev[key] = prev
        self.root.after(700, self._module_tick)
        return frame, hint

    def _page_zcode(self):
        def extra(body):
            self.zcode_lock_label = tk.Label(body, text="", bg=CARD, fg=MUTED,
                                             font=(FONT, 9), anchor="w")
            self.zcode_lock_label.pack(fill="x")
            tk.Label(body, text="屏幕旋钮「按下」= 锁定/解锁；Ctrl+Alt+→/← 切下一页/上一页并锁定、"
                                "Ctrl+Alt+↓ 锁定/解锁。锁定期间歌词与轮播都让位。热键注册失败（被占用）时按钮仍可用。",
                     bg=CARD, fg=DIM, font=(FONT, 8), anchor="w",
                     justify="left", wraplength=560).pack(fill="x", pady=(4, 0))
        frame, self.zcode_hint = self._module_page("zcode", "ZCode Agent",
                                                   "hooks 事件 · 今日 token 统计", extra)
        return frame

    def _page_traffic(self):
        frame, _hint = self._module_page("traffic", "网络流量",
                                         "实时速率 · 开机累计 · 3 分钟历史")
        return frame

    def _page_llm(self):
        def extra(body):
            row = tk.Frame(body, bg=CARD)
            row.pack(fill="x", pady=(0, 4))
            tk.Label(row, text="智谱 Key", bg=CARD, fg=FG, font=(FONT, 9)).pack(side="left")
            self.zhipu_entry = tk.Entry(row, show="•", width=26, bg=CARD_HI, fg=FG,
                                        insertbackground=FG, relief="flat",
                                        highlightthickness=1, highlightbackground=BORDER,
                                        font=(FONT, 9))
            self.zhipu_entry.insert(0, self.cfg.get("zhipu_api_key") or "")
            self.zhipu_entry.pack(side="left", padx=8)
            drow = tk.Frame(body, bg=CARD)
            drow.pack(fill="x")
            tk.Label(drow, text="DeepSeek Key", bg=CARD, fg=FG, font=(FONT, 9)).pack(side="left")
            self.dseek_entry = tk.Entry(drow, show="•", width=24, bg=CARD_HI, fg=FG,
                                        insertbackground=FG, relief="flat",
                                        highlightthickness=1, highlightbackground=BORDER,
                                        font=(FONT, 9))
            self.dseek_entry.insert(0, self.cfg.get("deepseek_key") or "")
            self.dseek_entry.pack(side="left", padx=4)
            pill(drow, "保存并刷新", self._save_dash_keys, "primary", width=9, size=9,
                 accent=self.accent).pack(side="left", padx=6)
            tk.Label(body, text="DeepSeek 留空时自动读取 ZCode 已保存的 Key；余额与配额每 5 分钟刷新",
                     bg=CARD, fg=DIM, font=(FONT, 8), anchor="w",
                     justify="left", wraplength=560).pack(fill="x", pady=(4, 0))
        frame, _hint = self._module_page("llm", "大模型用量",
                                         "DeepSeek / 智谱配额 / GLM 本地统计", extra)
        return frame

    def _save_dash_keys(self):
        self.cfg["zhipu_api_key"] = self.zhipu_entry.get().strip()
        self.cfg["deepseek_key"] = self.dseek_entry.get().strip()
        try:
            import llm_usage
            llm_usage.deepseek(self.cfg, force=True)
            llm_usage.zhipu(self.cfg, force=True)
        except Exception:
            pass
        lyrics_screen.save_config(self.cfg)
        self.status_label.config(text="Key 已保存，余额正在刷新", fg=MINT)

    def _module_tick(self):
        key = self.page
        try:
            import zcode_agent
            import traffic_scene
            import llm_usage
            zcode_agent.start()
            traffic_scene.start()
            if key == "zcode":
                snap = zcode_agent.snapshot()
                st_text = {"running": "● 运行中", "waiting": "● 等待输入", "idle": "● 空闲"}
                extra = "模型产出中" if snap["state"] == "running" and (snap.get("io_age") or 9e9) < 90 else ""
                self.dash_status["zcode"].config(
                    text=f'{st_text.get(snap["state"], "● 空闲")} {extra}  今日 '
                         f'{zcode_agent._hum((snap.get("usage") or {}).get("tokens"))} tokens · '
                         f'{(snap.get("usage") or {}).get("requests", 0)} 请求',
                    fg=MINT if snap["state"] == "running" else
                       ("#FFB86B" if snap["state"] == "waiting" else MUTED))
                self._update_lock_label()
            elif key == "traffic":
                down, up = traffic_scene.rate_now()
                tot = traffic_scene.totals()
                self.dash_status["traffic"].config(
                    text=f'↓{monitor_rate(down)}  ↑{monitor_rate(up)}   '
                         f'累计 ↓{_gb(tot.get("recv"))} ↑{_gb(tot.get("sent"))}')
            elif key == "llm":
                ds = llm_usage.deepseek(self.cfg) or {}
                zp = llm_usage.zhipu(self.cfg) or {}
                if zp and zp.get("windows"):
                    quota = "  ".join(f'{w["label"]} {w["pct"]}%' for w in zp["windows"][:2])
                else:
                    quota = "未配置或等待刷新"
                self.dash_status["llm"].config(
                    text=f'DeepSeek ¥{ds.get("total", "—")}   智谱 {quota}')
            self._refresh_module_preview(key)
        except Exception as exc:
            lyrics_screen.dbg(f"module tick failed: {exc}")
        self.root.after(1500, self._module_tick)

    def _update_lock_label(self):
        try:
            eng = self.engine
            locked = getattr(eng, "locked_page", None) if eng else None
            if locked:
                self.zcode_lock_label.config(
                    text=f"🔒 已锁定：{self.PAGE_NAMES.get(locked, locked)}（Ctrl+Alt+↓ 或屏幕旋钮按下解锁）",
                    fg=MINT)
            else:
                self.zcode_lock_label.config(text="未锁定，自动模式", fg=MUTED)
        except Exception:
            pass

    def _refresh_module_preview(self, key):
        import time as _t
        now = _t.time()
        if now - getattr(self, "_module_prev_at", 0) < 5:
            return
        self._module_prev_at = now

        def work():
            try:
                tmp = lyrics_screen.WORK / "module_preview.jpg"
                if key == "traffic":
                    import traffic_scene
                    traffic_scene.render(self.cfg, tmp)
                elif key == "llm":
                    import llm_usage
                    llm_usage.render(self.cfg, tmp)
                elif key == "info":
                    import scenes
                    scenes.render_info(self.cfg, tmp)
                else:
                    import zcode_agent
                    zcode_agent.render(self.cfg, tmp)
                self.root.after(0, lambda: self._show_module_preview(key, tmp))
            except Exception as exc:
                lyrics_screen.dbg(f"module preview failed: {exc}")
        threading.Thread(target=work, daemon=True).start()

    def _show_module_preview(self, key, path):
        try:
            img = Image.open(path).resize((360, 270), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._module_preview_imgs[key] = photo
            prev = self._module_prev.get(key)
            if prev:
                prev.config(image=photo, text="")
        except Exception:
            pass

'''
text = text[:start] + new_section + text[end:]

# 4) monitor page: append rotation settings card before the final hint label
anchor = '''        tk.Label(frame, text="外观页勾选「信息屏」后，这套数据会轮流显示在键盘屏上",
                 bg=BG, fg=DIM, font=(FONT, 8)).pack(anchor="w")'''
rotcard = '''        sc = self.cfg.get("scenes", {}) or {}
        rotcard = Card(frame, bg=CARD, radius=20, padx=18, pady=10)
        rotcard.pack(fill="x", pady=(8, 0))
        row0 = rotcard.body
        tk.Label(row0, text="待机轮播", bg=CARD, fg=FG, font=(FONT, 10, "bold")).pack(side="left")
        self.dash_mode_var = tk.StringVar(value=self.cfg.get("dash_mode", "rotate"))
        for val, label in (("rotate", "轮播"), ("single", "单页")):
            rb = tk.Radiobutton(row0, text=label, value=val, variable=self.dash_mode_var,
                                command=self.save_cfg, bg=CARD, fg=FG,
                                selectcolor=CARD_HI, activebackground=CARD,
                                activeforeground=FG, font=(FONT, 9))
            rb.pack(side="left", padx=(14, 0))
        tk.Label(row0, text="单页", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(14, 4))
        self.dash_single_var = tk.StringVar(value=self.cfg.get("dash_single", "zcode"))
        self._dash_page_names = {"zcode": "zcode", "traffic": "traffic", "llm": "llm", "info": "info"}
        combo = tk.OptionMenu(row1 := row0, self.dash_single_var, *self._dash_page_names.keys(),
                              command=lambda _v: self.save_cfg())
        combo.configure(bg=CARD_HI, fg=FG, activebackground=CARD_HI,
                        highlightthickness=1, highlightbackground=BORDER,
                        font=(FONT, 9), direction="below")
        combo["menu"].configure(bg=CARD_HI, fg=FG, font=(FONT, 9))
        combo.pack(side="left")
        self.knob_hook_var = tk.BooleanVar(value=bool(self.cfg.get("knob_hook", True)))
        tkb = Toggle(row1, "旋钮锁定", self.knob_hook_var, accent=self.accent)
        tkb.oncommand(self.save_cfg)
        tkb.pack(side="left", padx=(16, 0))
        self.zcode_boost_var = tk.BooleanVar(value=bool(self.cfg.get("zcode_boost", True)))
        tb = Toggle(row1, "ZCode 运行时优先", self.zcode_boost_var, accent=self.accent)
        tb.oncommand(self.save_cfg)
        tb.pack(side="left", padx=(12, 0))
        tk.Label(row1, text="每页停留(秒)", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(12, 4))
        self.dash_dwell_var = tk.StringVar(value=str(self.cfg.get("dash_dwell", 8)))
        spin = tk.Spinbox(row1, from_=4, to=60, increment=1, textvariable=self.dash_dwell_var,
                          width=4, bg=CARD_HI, fg=FG, buttonbackground=CARD_HI,
                          insertbackground=FG, relief="flat", highlightthickness=1,
                          highlightbackground=BORDER, font=(FONT, 9))
        spin.pack(side="left")
        spin.configure(command=self.save_cfg)
        tk.Label(row0, text="ZCode 运行时优先：agent 活跃时自动停留在 ZCode 页",
                 bg=CARD, fg=DIM, font=(FONT, 8), anchor="w").pack(fill="x", pady=(4, 0))
''' + anchor
text = text.replace(anchor, rotcard, 1)

# 5) init dicts used by the module pages + hotkey setup
text = text.replace(
    """        self.primary_btns = []
        self.last_frac = 0.0""",
    """        self.primary_btns = []
        self.last_frac = 0.0
        self.dash_toggle = {}
        self.dash_status = {}
        self._module_prev = {}
        self._module_preview_imgs = {}
        self._knob_installed = False""")

# 6) hotkey setup next to the knob hook
text = text.replace(
    """        self._setup_knob_hook()
""",
    """        self._setup_knob_hook()
        self._setup_hotkeys()

    def _setup_hotkeys(self):
        \"\"\"Ctrl+Alt+Right/Left cycle pages (locking), Ctrl+Alt+Down toggles lock.\"\"\"
        try:
            import hotkey
            res = hotkey.install(self._on_hotkey)
            bad = [combo for combo, ok in res.items() if not ok]
            self._hotkey_registered = res
            if bad:
                logsetup.info("hotkeys failed to register: %s" % bad)
            else:
                logsetup.info("hotkeys registered: %s" % res)
        except Exception as exc:
            logsetup.exception("hotkeys failed: %s" % exc)

    def _on_hotkey(self, action, combo):
        try:
            if self.engine and self.engine.running:
                if action == "next":
                    self.engine.next_page()
                elif action == "prev":
                    self.engine.prev_page()
                else:
                    self.engine.toggle_lock()
            else:
                self.events.put(("knob", None))
        except Exception:
            pass
""")

# 7) quit: uninstall hotkeys too
text = text.replace(
    """        try:
            import knob_hook
            knob_hook.uninstall()
        except Exception:
            pass""",
    """        try:
            import knob_hook
            knob_hook.uninstall()
        except Exception:
            pass
        try:
            import hotkey
            hotkey.uninstall()
        except Exception:
            pass""")

# 8) knob switch toggle-on wording in save_cfg keeps working via knob_hook var
SRC.write_text(text, encoding="utf-8")
print("patched, length:", len(text))
