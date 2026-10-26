"""Windows F13 input and a stoppable, drift-resistant tapping worker."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
import sys
import threading
import time


VERSION = "1.0.0"
MIN_FREQUENCY = 0.1
MAX_FREQUENCY = 100.0
VK_F13 = 0x7C
MODIFIERS = (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    # The mouse member is required for the correct native union size/alignment.
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", INPUTUNION)]


class WindowsKeyboard:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("实际按键功能仅支持 Windows。")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.send_input = user32.SendInput
        self.send_input.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.send_input.restype = wintypes.UINT
        self.get_key_state = user32.GetAsyncKeyState
        self.get_key_state.argtypes = (ctypes.c_int,)
        self.get_key_state.restype = wintypes.SHORT
        down = INPUT(type=1)
        down.ki = KEYBDINPUT(wVk=VK_F13)
        up = INPUT(type=1)
        up.ki = KEYBDINPUT(wVk=VK_F13, dwFlags=0x0002)
        self.events = (INPUT * 2)(down, up)
        self.release = (INPUT * 1)(up)

    def modifier_is_down(self):
        return any(self.get_key_state(key) & 0x8000 for key in MODIFIERS)

    def tap(self):
        ctypes.set_last_error(0)
        sent = self.send_input(2, self.events, ctypes.sizeof(INPUT))
        if sent != 2:
            error = ctypes.get_last_error()
            if sent == 1:
                self.send_input(1, self.release, ctypes.sizeof(INPUT))
            raise RuntimeError(
                f"按键发送失败（{sent}/2 个事件，Windows 错误 {error}）。"
                "当前桌面或目标程序的权限可能阻止模拟输入。"
            )


def validate_frequency(value):
    try:
        frequency = float(value)
    except (TypeError, ValueError):
        raise ValueError("请输入 0.1 到 100 之间的数字。") from None
    if not math.isfinite(frequency) or not MIN_FREQUENCY <= frequency <= MAX_FREQUENCY:
        raise ValueError("频率范围为每秒 0.1 到 100 次。")
    return frequency


@dataclass(frozen=True)
class TapSnapshot:
    running: bool
    paused: bool
    taps: int
    skipped: int
    missed: int
    elapsed: float
    error: str
    dry_run: bool
    frequency: float


class TapController:
    """One worker per controller; stop(wait) guarantees no later taps on success."""

    def __init__(self, keyboard_factory=WindowsKeyboard):
        self._keyboard_factory = keyboard_factory
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._running = False
        self._paused = False
        self._taps = self._skipped = self._missed = 0
        self._started = self._ended = None
        self._error = ""
        self._dry_run = False
        self._frequency = 10.0

    def start(self, frequency=10.0, dry_run=False):
        frequency = validate_frequency(frequency)
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("任务仍在运行，请先停止。")
            self._stop.clear()
            self._running = True
            self._paused = False
            self._taps = self._skipped = self._missed = 0
            self._started = time.monotonic()
            self._ended = None
            self._error = ""
            self._frequency = frequency
            self._dry_run = bool(dry_run)
            self._thread = threading.Thread(
                target=self._run, name="F13Tapper", daemon=True,
            )
            self._thread.start()

    def stop(self, timeout=1.0):
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return thread is None or not thread.is_alive()

    def snapshot(self):
        with self._lock:
            elapsed = 0.0 if self._started is None else (
                (self._ended if self._ended is not None else time.monotonic())
                - self._started
            )
            return TapSnapshot(
                self._running, self._paused, self._taps, self._skipped,
                self._missed, elapsed, self._error, self._dry_run, self._frequency,
            )

    def _run(self):
        try:
            keyboard = None if self._dry_run else self._keyboard_factory()
            interval = 1.0 / self._frequency
            next_tick = time.monotonic()
            while not self._stop.is_set():
                if self._stop.wait(max(0.0, next_tick - time.monotonic())):
                    break
                paused = keyboard is not None and keyboard.modifier_is_down()
                if self._stop.is_set():
                    break
                if not paused and keyboard is not None:
                    keyboard.tap()
                with self._lock:
                    self._paused = paused
                    if paused:
                        self._skipped += 1
                    else:
                        self._taps += 1
                next_tick += interval
                now = time.monotonic()
                if next_tick <= now:
                    late = math.floor((now - next_tick) / interval) + 1
                    with self._lock:
                        self._missed += late
                    next_tick += late * interval
        except Exception as exc:
            with self._lock:
                self._error = str(exc) or type(exc).__name__
        finally:
            with self._lock:
                self._running = False
                self._paused = False
                self._ended = time.monotonic()
