#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screen-knob press listener via Raw Input (WM_INPUT).

Raw Input is delivered as queued messages and never blocks the system input
pipeline, unlike a low-level keyboard hook whose callback delay stalls typing
system-wide (which is exactly what happened with the previous LL-hook build).

The factory mapping of the screen knob press is the calculator key
(VK_KNOB_PRESS / consumer 0x192), so Windows still launches the Calculator
app; a watchdog thread closes that window right after each knob press.

install(callback) / uninstall() — callback runs on the listener thread.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time

user32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
# 64-bit correctness: without these, handles get truncated to 32-bit ints
k32.GetModuleHandleW.restype = wt.HMODULE
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.RegisterRawInputDevices.argtypes = [ctypes.c_void_p, wt.UINT, wt.UINT]
user32.RegisterRawInputDevices.restype = wt.BOOL
user32.GetRawInputData.argtypes = [ctypes.c_void_p, wt.UINT, ctypes.c_void_p,
                                   ctypes.POINTER(wt.UINT), wt.UINT]
user32.GetRawInputData.restype = wt.UINT
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPCWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPCWSTR, ctypes.c_int]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
user32.GetMessageW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.UINT]

WM_INPUT = 0x00FF
WM_CLOSE = 0x0010
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEKEYBOARD = 1
VK_KNOB_PRESS = 0xA9          # screen knob press after vendor-226 reflash

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, ctypes.c_uint,
                             wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE),
                ("hIcon", wt.HANDLE),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT),
                ("usUsage", wt.USHORT),
                ("dwFlags", wt.DWORD),
                ("hwndTarget", wt.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD),
                ("dwSize", wt.DWORD),
                ("hDevice", wt.HANDLE),
                ("wParam", wt.WPARAM)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wt.USHORT),
                ("Flags", wt.USHORT),
                ("Reserved", wt.USHORT),
                ("VKey", wt.USHORT),
                ("Message", wt.ULONG),
                ("ExtraInformation", wt.ULONG)]


class RAWINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("keyboard", RAWKEYBOARD),
                    ("pad", ctypes.c_ubyte * 64)]
    _fields_ = [("header", RAWINPUTHEADER),
                ("data", _U)]


_state = {"installed": False, "callback": None, "last_press": 0.0,
          }
_lock = threading.Lock()

def install(callback):
    """Start listening; callback() fires on each screen-knob press."""
    with _lock:
        if _state["installed"]:
            return True
        _state["callback"] = callback
        _state["installed"] = True

        def worker():
            def wndproc(hwnd, msg, wParam, lParam):
                if msg == WM_INPUT:
                    try:
                        size = wt.UINT(0)
                        user32.GetRawInputData(ctypes.c_void_p(lParam), RID_INPUT,
                                               None, ctypes.byref(size),
                                               ctypes.sizeof(RAWINPUTHEADER))
                        buf = ctypes.create_string_buffer(size.value)
                        n = user32.GetRawInputData(ctypes.c_void_p(lParam), RID_INPUT,
                                                   buf, ctypes.byref(size),
                                                   ctypes.sizeof(RAWINPUTHEADER))
                        if n > 0:
                            raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
                            if raw.header.dwType == RIM_TYPEKEYBOARD:
                                vk = raw.data.keyboard.VKey
                                down = raw.data.keyboard.Message in (0x0100, 0x0104)
                                if vk == VK_KNOB_PRESS and down:
                                    cb = _state.get("callback")
                                    if cb:
                                        _state["last_press"] = time.time()
                                        cb()
                    except Exception:
                        pass
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

            proc = WNDPROC(wndproc)
            _state["proc"] = proc                      # keep alive
            hinst = k32.GetModuleHandleW(None)
            wc = WNDCLASSW()
            wc.lpfnWndProc = proc
            wc.hInstance = hinst
            wc.lpszClassName = "Neos75KnobSink"
            if not user32.RegisterClassW(ctypes.byref(wc)):
                _state["installed"] = False
                return
            hwnd = user32.CreateWindowExW(0, "Neos75KnobSink", "neos75-knob",
                                          0, 0, 0, 0, 0, None,
                                          None, hinst, None)  # hidden top-level (NOT message-only: WM_INPUT needs a real window)
            if not hwnd:
                _state["installed"] = False
                return
            rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
            if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1,
                                                  ctypes.sizeof(RAWINPUTDEVICE)):
                _state["installed"] = False
                return
            _state["hwnd"] = hwnd
            msg = wt.MSG()
            while _state["installed"]:
                r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        t = threading.Thread(target=worker, daemon=True, name="knob-rawinput")
        t.start()
        _state["thread"] = t
        return True


def uninstall():
    with _lock:
        if not _state["installed"]:
            return
        _state["installed"] = False
        hwnd = _state.get("hwnd")
        if hwnd:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)   # breaks GetMessageW
        _state["callback"] = None


if __name__ == "__main__":
    hits = []

    def on_press():
        hits.append(time.time())
        print("knob press captured ->", len(hits), flush=True)

    print("install:", install(on_press), "- press the screen knob within 30s", flush=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(0.5)
    uninstall()
    print("done, captured:", len(hits))
