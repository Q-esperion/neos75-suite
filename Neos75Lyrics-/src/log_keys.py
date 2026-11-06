#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Keyboard diagnostic listener (passive): logs every key-down with
device name, VK, scan code, E0 flag and injected flag. Pure monitoring."""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time

user32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
k32.GetModuleHandleW.restype = wt.HMODULE
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.restype = wt.ATOM
user32.RegisterRawInputDevices.argtypes = [ctypes.c_void_p, wt.UINT, wt.UINT]
user32.GetRawInputData.argtypes = [ctypes.c_void_p, wt.UINT, ctypes.c_void_p,
                                   ctypes.POINTER(wt.UINT), wt.UINT]
user32.GetRawInputData.restype = wt.UINT
user32.GetRawInputDeviceInfoW.argtypes = [ctypes.c_void_p, wt.UINT, wt.LPVOID,
                                          ctypes.POINTER(wt.UINT)]
user32.GetRawInputDeviceInfoW.restype = wt.UINT
user32.GetMessageW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.UINT]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPCWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPCWSTR, ctypes.c_int]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]

WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007

NAMES = {0xB7: "LAUNCH_APP2(calc)", 0x08: "Backspace", 0x25: "Left", 0x26: "Up",
         0x27: "Right", 0x28: "Down", 0x41: "A", 0x57: "W", 0x53: "S", 0x44: "D",
         0x20: "Space", 0x0D: "Enter", 0x1B: "Esc"}
_devs = {}
_lock = threading.Lock()


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HANDLE),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT),
                ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD),
                ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wt.USHORT), ("Flags", wt.USHORT),
                ("Reserved", wt.USHORT), ("VKey", wt.USHORT),
                ("Message", wt.ULONG), ("ExtraInformation", wt.ULONG)]


class RAWINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("keyboard", RAWKEYBOARD), ("pad", ctypes.c_ubyte * 64)]
    _fields_ = [("header", RAWINPUTHEADER), ("data", _U)]


def device_name(handle):
    key = handle or 0
    with _lock:
        if key in _devs:
            return _devs[key]
    name = f"h{key:x}"
    try:
        size = wt.UINT(0)
        user32.GetRawInputDeviceInfoW(ctypes.c_void_p(key), RIDI_DEVICENAME, None,
                                      ctypes.byref(size))
        buf = ctypes.create_unicode_buffer(size.value + 1)
        n = user32.GetRawInputDeviceInfoW(ctypes.c_void_p(key), RIDI_DEVICENAME, buf,
                                          ctypes.byref(size))
        if n > 0:
            name = (buf.value or "").replace("\\??\\", "")[-44:]
    except Exception:
        pass
    with _lock:
        _devs[key] = name
    return name


def vn(vk):
    return NAMES.get(vk, chr(vk) if 0x21 <= vk <= 0x5A else "")


def log_line(line):
    stamp = time.strftime("%H:%M:%S")
    full = f"{stamp} {line}"
    print(full, flush=True)
    # 默认写到仓库根的 workspace/keys.log，可用环境变量 NEOS75_KEYS_LOG 覆盖
    log_path = os.environ.get("NEOS75_KEYS_LOG") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "workspace", "keys.log")
    with _lock:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(full + "\n")


def calc_windows():
    hits = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _l):
        if user32.IsWindowVisible(hwnd):
            c = ctypes.create_unicode_buffer(96)
            t = ctypes.create_unicode_buffer(96)
            user32.GetClassNameW(hwnd, c, 96)
            user32.GetWindowTextW(hwnd, t, 96)
            if "计算器" in (t.value or "") or "calc" in (c.value or "").lower():
                hits.append(t.value or c.value)
                return False
        return True

    user32.EnumWindows(cb, 0)
    return hits


def wndproc(hwnd, msg, wParam, lParam):
    if msg == WM_INPUT:
        try:
            size = wt.UINT(0)
            user32.GetRawInputData(ctypes.c_void_p(lParam), RID_INPUT, None,
                                   ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
            buf = ctypes.create_string_buffer(max(1, size.value))
            n = user32.GetRawInputData(ctypes.c_void_p(lParam), RID_INPUT, buf,
                                       ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
            if n > 0:
                raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
                if raw.header.dwType == 1:
                    kb = raw.data.keyboard
                    if kb.Message in (0x0100, 0x0104):   # key down
                        injected = bool(kb.ExtraInformation & 0x10)
                        e0 = bool(kb.Flags & 0x02)
                        dev = device_name(raw.header.hDevice)
                        tag = "INJ" if injected else "   "
                        vk = kb.VKey
                        log_line(f"{tag} [{dev[-32:]}] VK=0x{vk:02X} SC=0x{kb.MakeCode:02X}"
                                 f"{' E0' if e0 else ''} {vn(vk)}")
        except Exception as exc:
            log_line(f"wm_input err: {exc}")
        return 0
    return user32.DefWindowProcW(hwnd, msg, wParam, lParam)


def main(seconds):
    def worker():
        proc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, ctypes.c_uint,
                                  wt.WPARAM, wt.LPARAM)(wndproc)
        hinst = k32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(proc, ctypes.c_void_p).value
        wc.hInstance = hinst
        wc.lpszClassName = "Neos75KeyLog2"
        if not user32.RegisterClassW(ctypes.byref(wc)):
            log_line("RegisterClassW failed")
            return
        hwnd = user32.CreateWindowExW(0, "Neos75KeyLog2", "keylog", 0, 0, 0, 0, 0,
                                      None, None, hinst, None)
        log_line(f"hwnd ok: {bool(hwnd)}")
        rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
        ok = user32.RegisterRawInputDevices(ctypes.byref(rid), 1,
                                            ctypes.sizeof(RAWINPUTDEVICE))
        log_line(f"raw input registered: {bool(ok)}")
        ok2 = user32.RegisterHotKey(None, 1, 0x2 | 0x4, 0x27)
        log_line(f"hotkey probe Ctrl+Shift+Right registered: {bool(ok2)}")
        msg = wt.MSG()
        end = time.time() + seconds
        while time.time() < end:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            if msg.message == 0x0312:
                log_line("*** WM_HOTKEY fired (Ctrl+Shift+Right) ***")
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    last_calc = None
    end = time.time() + seconds
    while time.time() < end:
        wins = tuple(calc_windows())
        if wins != last_calc:
            log_line(f"calculator windows: {wins or 'none'}")
            last_calc = wins
        time.sleep(1.0)
    log_line("diag ended")


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print(f"listening {secs}s (passive)", flush=True)
    main(secs)
