"""Clock Zone Timer — Python desktop app.

Live HH:MM:SS:CC clock with timezone picker (default Asia/Kuala_Lumpur).
Flashes all digits and plays an alarm beep at x:59:59:07, plus a Test button.
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import tzdata  # noqa: F401  — IANA timezone database (needed on Windows)
except ImportError:
    tzdata = None

DEFAULT_TZ = "Asia/Kuala_Lumpur"

TIME_ZONES = [
    "Asia/Kuala_Lumpur",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Australia/Sydney",
    "Pacific/Auckland",
    "UTC",
]

BG = "#0f1115"
PANEL = "#171a21"
DIGIT = "#e8e8e8"
ACCENT = "#ff2d6b"
FLASH = "#ffffff"
FLASH_GLOW = "#7fdfff"
CONTROL_BG = "#222631"
CONTROL_BORDER = "#343b49"

TICK_MS = 10
FLASH_STEPS = 8
FLASH_STEP_MS = 120
BEEP_FREQ = 1000
BEEP_MS = 140
BEEP_GAP_MS = 40


def pad2(n: int) -> str:
    return f"{n:02d}"


def get_time_parts(time_zone: str) -> dict:
    now = datetime.now(ZoneInfo(time_zone))
    hour24 = now.hour
    minute = now.minute
    second = now.second
    centis = now.microsecond // 10_000  # 0–99
    is_pm = hour24 >= 12
    hour12 = hour24 % 12 or 12
    return {
        "hour12": hour12,
        "hour24": hour24,
        "minute": minute,
        "second": second,
        "centis": centis,
        "is_pm": is_pm,
    }


def play_beep_pattern() -> None:
    """Three short 1 kHz alarm tones. Windows uses winsound; others use a bell fallback."""
    try:
        if sys.platform == "win32":
            import winsound

            for i in range(3):
                winsound.Beep(BEEP_FREQ, BEEP_MS)
                if i < 2:
                    threading.Event().wait(BEEP_GAP_MS / 1000)
        else:
            print("\a", end="", flush=True)
    except Exception:
        print("\a", end="", flush=True)


class ClockZoneTimer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Clock Zone Timer")
        self.configure(bg=BG)
        self.minsize(640, 360)
        self.resizable(True, True)

        self.sound_enabled = False
        self.alarm_fired = False
        self._flashing = False
        self._flash_after_id: str | None = None

        self._build_styles()
        self._build_ui()
        self._tick()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Root.TFrame", background=BG)
        style.configure(
            "Title.TLabel",
            background=PANEL,
            foreground=DIGIT,
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "Hint.TLabel",
            background=PANEL,
            foreground="#8a8f99",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Tz.TLabel",
            background=PANEL,
            foreground="#b8bcc6",
            font=("Segoe UI", 11),
        )
        style.configure(
            "Ctrl.TLabel",
            background=PANEL,
            foreground="#c8ccd6",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Ctrl.TCombobox",
            fieldbackground=CONTROL_BG,
            background=CONTROL_BG,
            foreground=DIGIT,
            arrowcolor=DIGIT,
        )
        style.map(
            "Ctrl.TCombobox",
            fieldbackground=[("readonly", CONTROL_BG)],
            foreground=[("readonly", DIGIT)],
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, style="Root.TFrame", padding=28)
        outer.pack(fill=tk.BOTH, expand=True)

        panel = tk.Frame(outer, bg=PANEL, padx=40, pady=32, highlightthickness=0)
        panel.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            panel,
            text="Exact time clock for your time zone",
            bg=PANEL,
            fg=DIGIT,
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(0, 20))

        controls = tk.Frame(panel, bg=PANEL)
        controls.pack(pady=(0, 24))

        tk.Label(
            controls,
            text="Time zone:",
            bg=PANEL,
            fg="#c8ccd6",
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.tz_var = tk.StringVar(value=DEFAULT_TZ)
        self.tz_combo = ttk.Combobox(
            controls,
            textvariable=self.tz_var,
            values=TIME_ZONES,
            state="readonly",
            width=24,
            style="Ctrl.TCombobox",
            font=("Segoe UI", 10),
        )
        self.tz_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.tz_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_tz_label())

        self.sound_btn = tk.Button(
            controls,
            text="Enable sound",
            command=self._enable_sound,
            bg=CONTROL_BG,
            fg=DIGIT,
            activebackground="#2c3344",
            activeforeground=DIGIT,
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground=CONTROL_BORDER,
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 10),
        )
        self.sound_btn.pack(side=tk.LEFT, padx=4)

        self.test_btn = tk.Button(
            controls,
            text="Test flash + beep",
            command=self._test_alarm,
            bg=CONTROL_BG,
            fg=DIGIT,
            activebackground="#2c3344",
            activeforeground=DIGIT,
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground=CONTROL_BORDER,
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 10),
        )
        self.test_btn.pack(side=tk.LEFT, padx=4)

        clock = tk.Frame(panel, bg=PANEL)
        clock.pack(pady=8)

        digit_font = ("Courier New", 56, "bold")
        colon_font = ("Courier New", 56, "bold")
        ampm_font = ("Courier New", 18, "bold")

        self.hh = self._digit_label(clock, digit_font)
        self._colon(clock, colon_font)
        self.mm = self._digit_label(clock, digit_font)
        self._colon(clock, colon_font)
        self.ss = self._digit_label(clock, digit_font)
        self._colon(clock, colon_font)
        self.cc = self._digit_label(clock, digit_font)
        self.ampm = tk.Label(
            clock,
            text="AM",
            bg=PANEL,
            fg=DIGIT,
            font=ampm_font,
            padx=8,
        )
        self.ampm.pack(side=tk.LEFT, anchor="n", pady=(8, 0))

        self.flash_labels = [self.hh, self.mm, self.ss, self.cc, self.ampm]
        self.colon_labels = [w for w in clock.winfo_children() if getattr(w, "_is_colon", False)]
        self.flash_labels.extend(self.colon_labels)

        self.tz_label = tk.Label(
            panel,
            text=DEFAULT_TZ.replace("_", " "),
            bg=PANEL,
            fg="#b8bcc6",
            font=("Segoe UI", 11),
        )
        self.tz_label.pack(pady=(16, 4))

        tk.Label(
            panel,
            text="Alarm fires every hour at x:59:59:07.  Use Test flash + beep to preview it now.",
            bg=PANEL,
            fg="#7a7f89",
            font=("Segoe UI", 9),
            wraplength=620,
        ).pack()

        self._bind_hover(self.sound_btn)
        self._bind_hover(self.test_btn)

    def _digit_label(self, parent: tk.Frame, font: tuple) -> tk.Label:
        lbl = tk.Label(
            parent,
            text="00",
            bg=PANEL,
            fg=DIGIT,
            font=font,
            width=2,
        )
        lbl.pack(side=tk.LEFT)
        return lbl

    def _colon(self, parent: tk.Frame, font: tuple) -> tk.Label:
        lbl = tk.Label(parent, text=":", bg=PANEL, fg=DIGIT, font=font)
        lbl.pack(side=tk.LEFT)
        lbl._is_colon = True  # type: ignore[attr-defined]
        lbl.configure(fg="#9aa0ab")
        return lbl

    def _bind_hover(self, btn: tk.Button) -> None:
        def on_enter(_e: tk.Event) -> None:
            btn.configure(highlightbackground=ACCENT)

        def on_leave(_e: tk.Event) -> None:
            btn.configure(highlightbackground=CONTROL_BORDER)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def _update_tz_label(self) -> None:
        self.tz_label.configure(text=self.tz_var.get().replace("_", " "))

    def _enable_sound(self) -> None:
        self.sound_enabled = True
        self.sound_btn.configure(text="Sound on", state=tk.DISABLED)

    def _test_alarm(self) -> None:
        if not self.sound_enabled:
            self._enable_sound()
        self.trigger_alarm()

    def trigger_alarm(self) -> None:
        self.flash()
        if self.sound_enabled:
            threading.Thread(target=play_beep_pattern, daemon=True).start()

    def flash(self) -> None:
        if self._flash_after_id is not None:
            self.after_cancel(self._flash_after_id)
            self._flash_after_id = None
        self._restore_digit_colors()
        self._flashing = True
        self._flash_step(0)

    def _flash_step(self, step: int) -> None:
        if step >= FLASH_STEPS:
            self._flashing = False
            self._restore_digit_colors()
            self._flash_after_id = None
            return
        on = step % 2 == 0
        color = FLASH if on else DIGIT
        glow_bg = FLASH_GLOW if on else PANEL
        for lbl in self.flash_labels:
            if getattr(lbl, "_is_colon", False) and not on:
                lbl.configure(fg="#9aa0ab", bg=PANEL)
            else:
                lbl.configure(fg=color, bg=glow_bg if on else PANEL)
        self._flash_after_id = self.after(FLASH_STEP_MS, lambda: self._flash_step(step + 1))

    def _restore_digit_colors(self) -> None:
        for lbl in self.flash_labels:
            if getattr(lbl, "_is_colon", False):
                lbl.configure(fg="#9aa0ab", bg=PANEL)
            else:
                lbl.configure(fg=DIGIT, bg=PANEL)

    def _tick(self) -> None:
        tz = self.tz_var.get() or DEFAULT_TZ
        try:
            t = get_time_parts(tz)
        except ZoneInfoNotFoundError:
            t = get_time_parts(DEFAULT_TZ)
            self.tz_var.set(DEFAULT_TZ)

        self.hh.configure(text=pad2(t["hour12"]))
        self.mm.configure(text=pad2(t["minute"]))
        self.ss.configure(text=pad2(t["second"]))
        self.cc.configure(text=pad2(t["centis"]))
        self.ampm.configure(text="PM" if t["is_pm"] else "AM")
        self._update_tz_label()

        in_final_second = t["minute"] == 59 and t["second"] == 59
        if in_final_second and t["centis"] >= 7 and not self.alarm_fired:
            self.alarm_fired = True
            self.trigger_alarm()
        if not in_final_second:
            self.alarm_fired = False

        self.after(TICK_MS, self._tick)


def main() -> None:
    try:
        ZoneInfo(DEFAULT_TZ)
    except ZoneInfoNotFoundError:
        print(
            "Timezone data is missing. Install it with:\n"
            "  python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    app = ClockZoneTimer()
    app.mainloop()


if __name__ == "__main__":
    main()
