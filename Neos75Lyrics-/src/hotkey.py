#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Global hotkeys via RegisterHotKey — the safe way to switch pages system-wide.

Unlike a low-level hook, a registered hotkey can never delay other keyboard
input: Windows fires WM_HOTKEY only for the exact registered combinations and
unregistered combos behave normally. Conflicts (another app already owns the
combo) are detected at registration and reported.

Defaults (Ctrl+Alt+arrows are usually owned by the GPU driver's rotation
hotkeys, hence Ctrl+Shift):
  Ctrl+Shift+Right  next page (and lock)
  Ctrl+Shift+Left   previous page (and lock)
  Ctrl+Shift+Down   lock / unlock toggle
"""
import ctypes
import ctypes.wintypes as wt
import threading

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
MOD_ALT = 0x1
MOD_CONTROL = 0x2
MOD_SHIFT = 0x4
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_DOWN = 0x28

HOTKEYS = {
    1: (MOD_CONTROL | MOD_SHIFT, VK_RIGHT, "Ctrl+Shift+Right", "next"),
    2: (MOD_CONTROL | MOD_SHIFT, VK_LEFT, "Ctrl+Shift+Left", "prev"),
    3: (MOD_CONTROL | MOD_SHIFT, VK_DOWN, "Ctrl+Shift+Down", "toggle"),
}

# navigation mode: bare W/A/S/D registered only while nav mode is active
# (the Neos75 Fn+arrows send plain WASD, so this makes the knob's nav mode
#  steerable with the exact same keys). Registered ids 10..13.
NAV_KEYS = {
    10: (VK_W := 0x57, "nav_prev"),    # W -> previous
    11: (0x41, "nav_prev"),            # A -> previous
    12: (0x53, "nav_next"),            # S -> next
    13: (0x44, "nav_next"),            # D -> next
}

_state = {"installed": False, "registered": {}}
_lock = threading.Lock()


def install(callback):
    """Register all hotkeys; callback(action, combo_name) fires per press.

    Returns {combo_name: registered_bool}. callback runs on the listener thread.
    """
    with _lock:
        if _state["installed"]:
            return dict(_state["registered"])
        _state["installed"] = True

        def worker():
            results = {}
            for kid, (mods, vk, combo, action) in HOTKEYS.items():
                ok = user32.RegisterHotKey(None, kid, mods, vk)
                results[combo] = bool(ok)
            _state["registered"] = results
            msg = wt.MSG()
            while _state["installed"]:
                r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    info = HOTKEYS.get(msg.wParam)
                    nav = NAV_KEYS.get(msg.wParam)
                    if info and _state.get("callback"):
                        try:
                            _state["callback"](info[3], info[2])
                        except Exception:
                            pass
                    elif nav and _state.get("callback"):
                        try:
                            _state["callback"](nav[1], "nav")
                        except Exception:
                            pass
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        _state["callback"] = callback
        t = threading.Thread(target=worker, daemon=True, name="hotkeys")
        t.start()
        _state["thread"] = t
        # registration happens on the listener thread; give it a moment
        import time
        for _ in range(20):
            if len(_state["registered"]) == len(HOTKEYS):
                break
            time.sleep(0.05)
        return dict(_state["registered"])


def set_nav_mode(on):
    """Register/unregister the bare WASD keys for knob navigation mode."""
    with _lock:
        results = {}
        for kid, (vk, action) in NAV_KEYS.items():
            if on:
                results[action] = bool(user32.RegisterHotKey(None, kid, 0, vk))
            else:
                user32.UnregisterHotKey(None, kid)
        return results


def uninstall():
    with _lock:
        for kid in NAV_KEYS:
            user32.UnregisterHotKey(None, kid)
        if not _state["installed"]:
            return
        _state["installed"] = False
        for kid, (_mods, _vk, combo, _action) in HOTKEYS.items():
            if _state["registered"].get(combo):
                user32.UnregisterHotKey(None, kid)
        _state["registered"] = {}
        _state["callback"] = None


if __name__ == "__main__":
    acts = []
    print("registered:", install(lambda action, combo: (acts.append(action),
                                                        print("hotkey:", combo, "->", action, flush=True))))
    print("try the combos within 20s")
    deadline = __import__("time").time() + 20
    while __import__("time").time() < deadline:
        __import__("time").sleep(0.5)
    uninstall()
    print("captured:", acts)
