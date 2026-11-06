#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix home page truncation: banner pack order + settings card two rows."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "Neos75Lyrics-" / "src" / "Neos75Lyrics.py"
t = p.read_text(encoding="utf-8")

# 1) banner: pack right controls FIRST so expanding text can't push them out
old1 = '''        top_row = tk.Frame(statcard.body, bg=CARD)
        top_row.pack(fill="x")
        lft = tk.Frame(top_row, bg=CARD)
        lft.pack(side="left", fill="both", expand=True)'''
new1 = '''        top_row = tk.Frame(statcard.body, bg=CARD)
        top_row.pack(fill="x")
        ctl = tk.Frame(top_row, bg=CARD)
        ctl.pack(side="right", padx=(12, 0))     # right controls claim space first
        lft = tk.Frame(top_row, bg=CARD)
        lft.pack(side="left", fill="both", expand=True)'''
assert old1 in t, "banner anchor 1 missing"
t = t.replace(old1, new1, 1)

old2 = '''        self.home_sub.pack(fill="x", pady=(2, 0))
        ctl = tk.Frame(top_row, bg=CARD)
        ctl.pack(side="right", padx=(12, 0))
        self.sync_dot = tk.Label(ctl, text="● 未同步", bg=CARD, fg=MUTED,'''
new2 = '''        self.home_sub.pack(fill="x", pady=(2, 0))
        self.sync_dot = tk.Label(ctl, text="● 未同步", bg=CARD, fg=MUTED,'''
assert old2 in t, "banner anchor 2 missing"
t = t.replace(old2, new2, 1)

old3 = '''        self.sync_start = pill(brow, "开始", self.start, "primary", width=6, size=10, accent=self.accent)
        self.sync_start.pack(side="left")
        self.sync_stop = pill(brow, "停止", self.stop, "danger", width=6, size=10)
        self.sync_stop.pack(side="left", padx=(8, 0))'''
new3 = '''        self.sync_start = pill(brow, "开始", self.start, "primary", width=5, size=9, accent=self.accent)
        self.sync_start.pack(side="left")
        self.sync_stop = pill(brow, "停止", self.stop, "danger", width=5, size=9)
        self.sync_stop.pack(side="left", padx=(6, 0))'''
assert old3 in t, "banner anchor 3 missing"
t = t.replace(old3, new3, 1)

# 2) settings card: split the overflowing single row into two rows
old4 = '''        row0 = card2.body
        tk.Label(row0, text="待机轮播", bg=CARD, fg=FG, font=(FONT, 10, "bold")).pack(side="left")
        self.dash_mode_var = tk.StringVar(value=self.cfg.get("dash_mode", "rotate"))
        for val, label in (("rotate", "轮播"), ("single", "单页")):
            rb = tk.Radiobutton(row0, text=label, value=val, variable=self.dash_mode_var,
                                command=self.save_cfg, bg=CARD, fg=FG,
                                selectcolor=CARD_HI, activebackground=CARD,
                                activeforeground=FG, font=(FONT, 9))
            rb.pack(side="left", padx=(14, 0))
        tk.Label(row0, text="单页", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(14, 4))'''
new4 = '''        row0 = card2.body
        # row A: mode selection
        rowA = tk.Frame(row0, bg=CARD)
        rowA.pack(fill="x")
        tk.Label(rowA, text="待机轮播", bg=CARD, fg=FG, font=(FONT, 10, "bold")).pack(side="left")
        self.dash_mode_var = tk.StringVar(value=self.cfg.get("dash_mode", "rotate"))
        for val, label in (("rotate", "轮播"), ("single", "单页")):
            rb = tk.Radiobutton(rowA, text=label, value=val, variable=self.dash_mode_var,
                                command=self.save_cfg, bg=CARD, fg=FG,
                                selectcolor=CARD_HI, activebackground=CARD,
                                activeforeground=FG, font=(FONT, 9))
            rb.pack(side="left", padx=(14, 0))
        tk.Label(rowA, text="单页显示", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(18, 4))'''
assert old4 in t, "settings anchor 1 missing"
t = t.replace(old4, new4, 1)

old5 = '''        combo = tk.OptionMenu(row0, self.dash_single_var, "ZCode Agent", "网络流量", "大模型用量", "信息屏",
                              command=lambda _v: self.save_cfg())
        combo.configure(bg=CARD_HI, fg=FG, activebackground="#1E2636",
                        highlightthickness=1, highlightbackground=BORDER,
                        font=(FONT, 9), direction="below", relief="flat",
                        padx=10, pady=2, cursor="hand2")
        combo["menu"].configure(bg=CARD_HI, fg=FG, font=(FONT, 9), bd=0)
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
        t_auto = Toggle(row1, "开机自启", self.autostart_var, accent=self.accent)
        t_auto.oncommand(self.toggle_autostart)
        t_auto.pack(side="left", padx=(16, 0))
        self._autostart_toggles.append(t_auto)
        tk.Label(row1, text="每页停留(秒)", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(16, 4))
        self.dash_dwell_var = tk.StringVar(value=str(self.cfg.get("dash_dwell", 8)))
        spin = tk.Spinbox(row1, from_=4, to=60, increment=1, textvariable=self.dash_dwell_var,
                          width=4, bg=CARD_HI, fg=FG, buttonbackground=CARD_HI,
                          insertbackground=FG, relief="flat", highlightthickness=1,
                          highlightbackground=BORDER, font=(FONT, 9))
        spin.pack(side="left")
        spin.configure(command=self.save_cfg)
        tk.Label(row0, text="屏幕旋钮「按下」= 锁定/解锁；Ctrl+Shift+→/← 切页并锁定、Ctrl+Shift+↓ 锁定/解锁",
                 bg=CARD, fg=DIM, font=(FONT, 8), anchor="w").pack(fill="x", pady=(6, 0))'''
new5 = '''        combo = tk.OptionMenu(rowA, self.dash_single_var, "ZCode Agent", "网络流量", "大模型用量", "信息屏",
                              command=lambda _v: self.save_cfg())
        combo.configure(bg=CARD_HI, fg=FG, activebackground="#1E2636",
                        highlightthickness=1, highlightbackground=BORDER,
                        font=(FONT, 9), direction="below", relief="flat",
                        padx=10, pady=2, cursor="hand2")
        combo["menu"].configure(bg=CARD_HI, fg=FG, font=(FONT, 9), bd=0)
        combo.pack(side="left")
        # row B: switches + dwell
        rowB = tk.Frame(row0, bg=CARD)
        rowB.pack(fill="x", pady=(8, 0))
        self.knob_hook_var = tk.BooleanVar(value=bool(self.cfg.get("knob_hook", True)))
        tkb = Toggle(rowB, "旋钮锁定", self.knob_hook_var, accent=self.accent)
        tkb.oncommand(self.save_cfg)
        tkb.pack(side="left")
        self.hotkey_var = tk.BooleanVar(value=bool(self.cfg.get("hotkey_enabled", True)))
        thk = Toggle(rowB, "切页热键", self.hotkey_var, accent=self.accent)
        thk.oncommand(self.save_cfg)
        thk.pack(side="left", padx=(10, 0))
        self.zcode_boost_var = tk.BooleanVar(value=bool(self.cfg.get("zcode_boost", True)))
        tb = Toggle(rowB, "ZCode 优先", self.zcode_boost_var, accent=self.accent)
        tb.oncommand(self.save_cfg)
        tb.pack(side="left", padx=(10, 0))
        t_auto = Toggle(rowB, "开机自启", self.autostart_var, accent=self.accent)
        t_auto.oncommand(self.toggle_autostart)
        t_auto.pack(side="left", padx=(10, 0))
        self._autostart_toggles.append(t_auto)
        tk.Label(rowB, text="每页停留(秒)", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(14, 4))
        self.dash_dwell_var = tk.StringVar(value=str(self.cfg.get("dash_dwell", 8)))
        spin = tk.Spinbox(rowB, from_=4, to=60, increment=1, textvariable=self.dash_dwell_var,
                          width=4, bg=CARD_HI, fg=FG, buttonbackground=CARD_HI,
                          insertbackground=FG, relief="flat", highlightthickness=1,
                          highlightbackground=BORDER, font=(FONT, 9))
        spin.pack(side="left")
        spin.configure(command=self.save_cfg)'''
assert old5 in t, "settings anchor 2 missing"
t = t.replace(old5, new5, 1)

p.write_text(t, encoding="utf-8")
print("layout fixed OK")
