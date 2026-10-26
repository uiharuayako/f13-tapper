"""F13 Tapper: a small Windows desktop app with explicit start and stop."""

import argparse
import ctypes
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from f13_core import INPUT, VERSION, TapController, WindowsKeyboard, validate_frequency


class F13App:
    def __init__(self, root):
        self.root = root
        self.controller = TapController()
        self._closing = False
        self._stop_requested = False
        self._shown_error = ""
        root.title(f"F13 Tapper · v{VERSION}")
        root.geometry("540x690")
        root.minsize(540, 690)
        root.configure(bg="#f1f5f9")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.frequency = tk.StringVar(value="10")
        self.dry_run = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="已停止")
        self.detail = tk.StringVar(value="设置频率后，点击开始。")
        self.count = tk.StringVar(value="0")
        self.elapsed = tk.StringVar(value="0.0 秒")
        self._build()
        # Honor actual font/DPI measurements so the footer cannot be clipped.
        root.update_idletasks()
        minimum_width = max(540, root.winfo_reqwidth())
        minimum_height = max(690, root.winfo_reqheight())
        root.minsize(minimum_width, minimum_height)
        root.geometry(f"{minimum_width}x{minimum_height}")
        self.root.after(100, self._refresh)

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#ffffff", foreground="#172033", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background="#f1f5f9", font=("Microsoft YaHei UI", 23, "bold"))
        style.configure("Subtitle.TLabel", background="#f1f5f9", foreground="#64748b", font=("Microsoft YaHei UI", 10))
        style.configure("Caption.TLabel", foreground="#64748b", font=("Microsoft YaHei UI", 9))
        style.configure("Number.TLabel", font=("Segoe UI", 23, "bold"))
        style.configure("Status.TLabel", foreground="#2563eb", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("TCheckbutton", background="#ffffff", font=("Microsoft YaHei UI", 10))
        style.map("TCheckbutton", background=[("active", "#ffffff")])
        style.configure("TButton", font=("Microsoft YaHei UI", 11), padding=(18, 12))
        style.configure("Start.TButton", background="#2563eb", foreground="#ffffff", borderwidth=0)
        style.map("Start.TButton", background=[("disabled", "#cbd5e1"), ("active", "#1d4ed8")], foreground=[("disabled", "#f8fafc")])
        style.configure("Stop.TButton", background="#e2e8f0", foreground="#334155", borderwidth=0)
        style.map("Stop.TButton", background=[("active", "#cbd5e1")], foreground=[("disabled", "#94a3b8")])
        style.configure("TSpinbox", padding=9, font=("Segoe UI", 14))

        outer = ttk.Frame(self.root, padding=26)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="F13 Tapper", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="按你的节奏，重复发送 F13。", style="Subtitle.TLabel").pack(anchor="w", pady=(4, 22))

        settings = ttk.Frame(outer, style="Card.TFrame", padding=22)
        settings.pack(fill="x")
        ttk.Label(settings, text="发送频率").pack(anchor="w")
        row = ttk.Frame(settings, style="Card.TFrame")
        row.pack(fill="x", pady=(9, 6))
        self.frequency_entry = ttk.Spinbox(
            row, from_=0.1, to=100.0, increment=1.0,
            textvariable=self.frequency, width=10,
        )
        self.frequency_entry.pack(side="left")
        ttk.Label(row, text="次 / 秒").pack(side="left", padx=(12, 0))
        ttk.Label(settings, text="支持 0.1–100 次 / 秒；默认 10 次。", style="Caption.TLabel").pack(anchor="w", pady=(0, 15))
        self.test_check = ttk.Checkbutton(settings, text="测试模式（只计数，不发送按键）", variable=self.dry_run)
        self.test_check.pack(anchor="w")
        buttons = ttk.Frame(settings, style="Card.TFrame")
        buttons.pack(fill="x", pady=(20, 0))
        buttons.columnconfigure((0, 1), weight=1)
        self.start_button = ttk.Button(buttons, text="开始", style="Start.TButton", command=self.start)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.stop_button = ttk.Button(buttons, text="停止", style="Stop.TButton", command=self.stop, state="disabled")
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        status_card = ttk.Frame(outer, style="Card.TFrame", padding=22)
        status_card.pack(fill="x", pady=(14, 0))
        ttk.Label(status_card, textvariable=self.status, style="Status.TLabel").pack(anchor="w")
        ttk.Label(status_card, textvariable=self.detail, style="Caption.TLabel", wraplength=420).pack(anchor="w", pady=(5, 17))
        stats = ttk.Frame(status_card, style="Card.TFrame")
        stats.pack(fill="x")
        for column, (label, value) in enumerate((("本次次数", self.count), ("运行时长", self.elapsed))):
            cell = ttk.Frame(stats, style="Card.TFrame")
            cell.grid(row=0, column=column, sticky="w", padx=(0, 60))
            ttk.Label(cell, text=label, style="Caption.TLabel").pack(anchor="w")
            ttk.Label(cell, textvariable=value, style="Number.TLabel").pack(anchor="w", pady=(3, 0))
        ttk.Label(
            outer, text="按住 Ctrl / Shift / Alt / Win 时会暂停发送。\nF13 可能触发软件快捷键，或影响系统空闲计时。",
            style="Subtitle.TLabel", wraplength=480, justify="left",
        ).pack(anchor="w", pady=(19, 0))

    def start(self):
        try:
            frequency = validate_frequency(self.frequency.get())
            self.controller.start(frequency, dry_run=self.dry_run.get())
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("无法开始", str(exc), parent=self.root)
            return False
        self._shown_error = ""
        self._stop_requested = False
        self._refresh_controls(True)
        self._update_status()
        return True

    def stop(self):
        self._stop_requested = True
        self.controller.stop(timeout=0)
        self.stop_button.configure(state="disabled")
        self._update_status()

    def _refresh_controls(self, running):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running and not self._stop_requested else "disabled")
        self.frequency_entry.configure(state="disabled" if running else "normal")
        self.test_check.configure(state="disabled" if running else "normal")

    def _update_status(self):
        snap = self.controller.snapshot()
        self.count.set(f"{snap.taps:,}")
        self.elapsed.set(f"{snap.elapsed:.1f} 秒")
        self._refresh_controls(snap.running)
        if snap.error:
            self.status.set("发送已停止")
            self.detail.set(snap.error)
        elif self._stop_requested and snap.running:
            self.status.set("正在停止…")
            self.detail.set("等待当前按键操作结束。")
        elif snap.running and snap.paused:
            self.status.set("已暂停 · 修饰键按住中")
            self.detail.set("松开 Ctrl / Shift / Alt / Win 后会自动继续。")
        elif snap.running:
            self.status.set("测试运行中" if snap.dry_run else "正在发送 F13")
            prefix = "只计数，不发送按键" if snap.dry_run else "每次包含按下和松开"
            self.detail.set(f"{snap.frequency:g} 次 / 秒 · {prefix}")
        else:
            self.status.set("已停止")
            self.detail.set("可修改频率，再次开始。" if snap.elapsed else "设置频率后，点击开始。")
        return snap

    def _refresh(self):
        if self._closing:
            return
        self._update_status()
        self.root.after(100, self._refresh)

    def close(self):
        self._closing = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        if self.controller.stop(timeout=0):
            self.root.destroy()
        else:
            self.status.set("正在停止并退出…")
            self.root.after(20, self.close)


def smoke_test(root, app, report_path):
    """Exercise actual widgets/worker with input explicitly disabled."""
    root.withdraw()
    report = {"version": VERSION, "dry_run": True, "checks": {}}

    def fail(exc):
        app.controller.stop()
        report["ok"] = False
        report["error"] = str(exc)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        root.destroy()

    def finish():
        try:
            app.stop()
            assert app.controller.stop(), "second stop did not complete"
            snap = app._update_status()
            assert not snap.running and snap.taps >= 2
            report["second_run"] = asdict(snap)
            report["checks"]["restart_with_new_frequency"] = snap.frequency == 20
            report["checks"]["controls_restored"] = str(app.start_button["state"]) == "normal" and str(app.frequency_entry["state"]) == "normal"
            assert all(report["checks"].values())
            report["ok"] = True
            Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            app.close()
        except Exception as exc:
            fail(exc)

    def restart():
        try:
            assert app.controller.snapshot().taps == report["first_run"]["taps"], "count changed after stop"
            report["checks"]["no_taps_after_stop"] = True
            app.frequency.set("20")
            assert app.start()
            root.after(350, finish)
        except Exception as exc:
            fail(exc)

    def first_stop():
        try:
            app.stop()
            assert app.controller.stop(), "first stop did not complete"
            snap = app._update_status()
            assert not snap.running and snap.taps >= 3
            report["first_run"] = asdict(snap)
            root.after(200, restart)
        except Exception as exc:
            fail(exc)

    try:
        keyboard = WindowsKeyboard()
        report["input_struct_bytes"] = ctypes.sizeof(INPUT)
        report["checks"]["win32_abi"] = ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        report["checks"]["f13_pair"] = [(event.type, event.ki.wVk, event.ki.dwFlags) for event in keyboard.events] == [(1, 124, 0), (1, 124, 2)]
        report["checks"]["initially_stopped"] = not app.controller.snapshot().running
        app.dry_run.set(True)
        app.frequency.set("10")
        assert app.start()
        report["checks"]["controls_disabled_while_running"] = str(app.start_button["state"]) == "disabled" and str(app.frequency_entry["state"]) == "disabled"
        root.after(550, first_stop)
    except Exception as exc:
        fail(exc)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", metavar="JSON_PATH", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This application requires Windows.")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    if args.smoke_test:
        root.withdraw()
    app = F13App(root)
    report = smoke_test(root, app, args.smoke_test) if args.smoke_test else None
    root.mainloop()
    return 0 if report is None or report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
