#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch: home page with per-screen toggles; move rotation settings there."""
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "Neos75Lyrics-" / "src" / "Neos75Lyrics.py"
t = P.read_text(encoding="utf-8")

# 1) pages dict: add home first (built last so module vars exist)
t = t.replace(
    """        self.pages = {
            "lyrics": self._page_lyrics(),""",
    """        self.pages = {
            "home": None,
            "lyrics": self._page_lyrics(),""")
t = t.replace(
    """            "look": self._page_look(),
            "fw": self._page_fw(),
        }
        self.show_page("lyrics")""",
    """            "look": self._page_look(),
            "fw": self._page_fw(),
        }
        self.pages["home"] = self._page_home()
        self.show_page("home")""")

# 2) sidebar: add the home entry first
t = t.replace(
    '''        for key, label, glyph in (("lyrics", "歌词", "♪"), ("game", "对局", "⚔"),''',
    '''        for key, label, glyph in (("home", "总体", "⌂"), ("lyrics", "歌词", "♪"), ("game", "对局", "⚔"),''')

# 3) new home page + shared helpers, inserted before the zcode pages section
anchor = "    # --------------------------------------- zcode / traffic / llm pages"
home_code = '''    # ------------------------------------------------------------------ home
    HOME_SCREENS = (
        ("lyrics", "歌词屏"),
        ("game", "对局比分"),
        ("info", "监控信息屏"),
        ("traffic", "网络流量"),
        ("zcode", "ZCode Agent"),
        ("llm", "大模型用量"),
    )

    def _page_home(self):
        frame = tk.Frame(self.main, bg=BG)
        head = tk.Frame(frame, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="总体设置", bg=BG, fg=FG, font=(FONT, 15, "bold")).pack(side="left")
        tk.Label(head, text="勾选参与显示与轮播的屏幕，无需进入各屏页面", bg=BG, fg=DIM,
                 font=(FONT, 9)).pack(side="left", padx=10)

        sc = self.cfg.get("scenes", {}) or {}
        self.home_vars = {}
        card1 = Card(frame, bg=CARD, radius=20, padx=20, pady=16)
        card1.pack(fill="x", pady=(12, 8))
        grid = tk.Frame(card1.body, bg=CARD)
        grid.pack(fill="x")
        tk.Label(grid, text="参与显示与轮播的屏幕", bg=CARD, fg=FG,
                 font=(FONT, 10, "bold")).grid(row=0, column=0, columnspan=3,
                                               sticky="w", pady=(0, 6))
        for i, (key, label) in enumerate(self.HOME_SCREENS):
            row, col = divmod(i, 3)
            if key == "game":
                var = tk.BooleanVar(value=bool(self.cfg.get("valorant", False)))
            else:
                var = tk.BooleanVar(value=bool(sc.get(key, True)))
            self.home_vars[key] = var
            cb = tk.Checkbutton(grid, text=label, variable=var,
                                command=lambda k=key, v=var: self._on_home_toggle(k, v),
                                bg=CARD, fg=FG, selectcolor=CARD_HI,
                                activebackground=CARD, activeforeground=FG,
                                font=(FONT, 10))
            cb.grid(row=row + 1, column=col, sticky="w", padx=(0, 18), pady=3)
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)
        tk.Label(card1.body,
                 text="关闭后对应屏幕不再推送、也不再进入轮播；左侧导航里的详细设置不受影响",
                 bg=CARD, fg=DIM, font=(FONT, 8), anchor="w").pack(fill="x", pady=(8, 0))

        # rotation + control card (moved from the monitor page)
        card2 = Card(frame, bg=CARD, radius=20, padx=20, pady=14)
        card2.pack(fill="x", pady=(0, 8))
        row0 = card2.body
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
        combo = tk.OptionMenu(row0, self.dash_single_var, "zcode", "traffic", "llm", "info",
                              command=lambda _v: self.save_cfg())
        combo.configure(bg=CARD_HI, fg=FG, activebackground=CARD_HI,
                        highlightthickness=1, highlightbackground=BORDER,
                        font=(FONT, 9), direction="below")
        combo["menu"].configure(bg=CARD_HI, fg=FG, font=(FONT, 9))
        combo.pack(side="left")
        self.knob_hook_var = tk.BooleanVar(value=bool(self.cfg.get("knob_hook", True)))
        tkb = Toggle(row0, "旋钮锁定", self.knob_hook_var, accent=self.accent)
        tkb.oncommand(self.save_cfg)
        tkb.pack(side="left", padx=(16, 0))
        self.hotkey_var = tk.BooleanVar(value=bool(self.cfg.get("hotkey_enabled", True)))
        thk = Toggle(row0, "切页热键", self.hotkey_var, accent=self.accent)
        thk.oncommand(self.save_cfg)
        thk.pack(side="left", padx=(12, 0))
        row1 = tk.Frame(row0, bg=CARD)
        row1.pack(fill="x", pady=(6, 0))
        self.zcode_boost_var = tk.BooleanVar(value=bool(self.cfg.get("zcode_boost", True)))
        tb = Toggle(row1, "ZCode 运行时优先", self.zcode_boost_var, accent=self.accent)
        tb.oncommand(self.save_cfg)
        tb.pack(side="left")
        tk.Label(row1, text="每页停留(秒)", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(16, 4))
        self.dash_dwell_var = tk.StringVar(value=str(self.cfg.get("dash_dwell", 8)))
        spin = tk.Spinbox(row1, from_=4, to=60, increment=1, textvariable=self.dash_dwell_var,
                          width=4, bg=CARD_HI, fg=FG, buttonbackground=CARD_HI,
                          insertbackground=FG, relief="flat", highlightthickness=1,
                          highlightbackground=BORDER, font=(FONT, 9))
        spin.pack(side="left")
        spin.configure(command=self.save_cfg)
        tk.Label(row0, text="屏幕旋钮「按下」= 锁定/解锁；Ctrl+Shift+→/← 切页并锁定、Ctrl+Shift+↓ 锁定/解锁",
                 bg=CARD, fg=DIM, font=(FONT, 8), anchor="w").pack(fill="x", pady=(6, 0))
        self.home_state = tk.Label(card2.body, text="", bg=CARD, fg=MUTED,
                                   font=(FONT, 9), anchor="w")
        self.home_state.pack(fill="x")
        self.root.after(800, self._home_tick)
        return frame

    def _on_home_toggle(self, key, var):
        val = bool(var.get())
        if key == "game":
            self.cfg["valorant"] = val
            try:
                self.val_var.set(val)
            except Exception:
                pass
        else:
            sc = dict(self.cfg.get("scenes", {}) or {})
            sc[key] = val
            self.cfg["scenes"] = sc
            if key == "lyrics":
                try:
                    self.lyr_push.set(val)
                except Exception:
                    pass
            if key == "info":
                try:
                    self.mon_push.set(val)
                except Exception:
                    pass
            if key in ("traffic", "zcode", "llm"):
                v = self.dash_toggle.get(key)
                if v is not None:
                    v.set(val)
        lyrics_screen.save_config(self.cfg)
        if self.engine:
            self.engine.cfg = dict(self.cfg)

    def _home_tick(self):
        if self.page != "home":
            self.root.after(2000, self._home_tick)
            return
        try:
            eng = self.engine
            locked = getattr(eng, "locked_page", None) if eng else None
            running = bool(eng and eng.running)
            mode = self.cfg.get("dash_mode", "rotate")
            mode_txt = "单页" if mode == "single" else "轮播"
            if locked:
                txt = f'{"● 同步中" if running else "● 未同步"}   🔒 已锁定：{self.PAGE_NAMES.get(locked, locked)}（Ctrl+Shift+↓ 或旋钮按下解锁）'
                color = MINT
            else:
                txt = f'{"● 同步中" if running else "● 未同步"}   自动模式（{mode_txt}）'
                color = MINT if running else MUTED
            self.home_state.config(text=txt, fg=color)
        except Exception:
            pass
        self.root.after(1500, self._home_tick)

''' + anchor
t = t.replace(anchor, home_code, 1)

# 4) remove the rotation card from the monitor page (moved to home)
rot_start = t.index('''        sc = self.cfg.get("scenes", {}) or {}
        rotcard = Card(frame, bg=CARD, radius=20, padx=18, pady=10)''')
rot_end = t.index('''        tk.Label(row0, text="ZCode 运行时优先：agent 活跃时自动停留在 ZCode 页",
                 bg=CARD, fg=DIM, font=(FONT, 8), anchor="w").pack(fill="x", pady=(4, 0))''')
rot_end = t.index("\n", rot_end) + 1
t = t[:rot_start] + t[rot_end:]

# 5) llm page status line shows remaining instead of used
t = t.replace(
    '''                if zp and zp.get("windows"):
                    quota = "  ".join(f'{w["label"]} {w["pct"]}%' for w in zp["windows"][:2])
                else:
                    quota = "未配置或等待刷新"''',
    '''                if zp and zp.get("windows"):
                    quota = "  ".join(f'{w["label"]} 剩{100 - (w["pct"] or 0)}%' for w in zp["windows"][:2])
                else:
                    quota = "未配置或等待刷新"''')

# 6) hotkey_enabled handling in save_cfg
t = t.replace(
    """        try:
            if hasattr(self, "knob_hook_var"):
                self.cfg["knob_hook"] = bool(self.knob_hook_var.get())
                import knob_hook
                if self.cfg["knob_hook"] and not self._knob_installed:
                    self._knob_installed = knob_hook.install(
                        lambda: self._on_knob_press())
                elif not self.cfg["knob_hook"] and self._knob_installed:
                    knob_hook.uninstall()
                    self._knob_installed = False
        except Exception:
            pass""",
    """        try:
            if hasattr(self, "knob_hook_var"):
                self.cfg["knob_hook"] = bool(self.knob_hook_var.get())
                import knob_hook
                if self.cfg["knob_hook"] and not self._knob_installed:
                    self._knob_installed = knob_hook.install(
                        lambda: self._on_knob_press())
                elif not self.cfg["knob_hook"] and self._knob_installed:
                    knob_hook.uninstall()
                    self._knob_installed = False
        except Exception:
            pass
        try:
            if hasattr(self, "hotkey_var"):
                self.cfg["hotkey_enabled"] = bool(self.hotkey_var.get())
                import hotkey
                if self.cfg["hotkey_enabled"]:
                    self._setup_hotkeys()
                else:
                    hotkey.uninstall()
        except Exception:
            pass""")

P.write_text(t, encoding="utf-8")
print("home page patched, length:", len(t))
