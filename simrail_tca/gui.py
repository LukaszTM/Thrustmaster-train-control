"""Simple Tkinter GUI for the SimRail <-> Thrustmaster TCA bridge.

Start with:  python -m simrail_tca gui   (or gui.bat on Windows)

The bridge itself runs in a background thread; all joystick/pygame work
happens in that single thread. Log messages travel to the GUI through a
queue so the window stays responsive.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Tkinter is required for the GUI. On Windows reinstall Python with "
        "the 'tcl/tk and IDLE' option; on Linux install python3-tk."
    ) from exc

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

MODE_KEYBOARD = "keyboard"
MODE_XBOX = "xbox"


class BridgeThread(threading.Thread):
    """Runs one bridge session until stopped or an error occurs."""

    def __init__(self, mode: str, config_path: str, dry_run: bool,
                 verbose: bool, log) -> None:
        super().__init__(daemon=True)
        self.mode = mode
        self.config_path = config_path
        self.dry_run = dry_run
        self.verbose = verbose
        self.log = log
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            from .joystick import open_device
            if self.mode == MODE_KEYBOARD:
                from .app import run_loop
                from .config import load_profile
                from .keysender import make_sender
                profile = load_profile(self.config_path)
                device = open_device(profile.device_name_contains,
                                     profile.device_index)
                sender = make_sender(dry_run=self.dry_run, log=self.log)
                if self.dry_run:
                    self.log("Tryb testowy: klawisze sa tylko wypisywane.")
                run_loop(profile, device, sender, verbose=self.verbose,
                         stop_event=self.stop_event, log=self.log)
            else:
                from .config import load_xbox_profile
                from .xboxpad import make_pad, run_xbox_loop
                profile = load_xbox_profile(self.config_path)
                device = open_device(profile.device_name_contains,
                                     profile.device_index)
                if self.dry_run:
                    self.log("Tryb testowy: stan pada jest tylko wypisywany.")
                pad = make_pad(dry_run=self.dry_run, log=self.log)
                run_xbox_loop(profile, device, pad,
                              stop_event=self.stop_event, log=self.log)
        except Exception as exc:
            self.log(f"BLAD: {exc}")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SimRail — Thrustmaster TCA")
        self.minsize(560, 420)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.bridge: BridgeThread | None = None

        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # --- mode ---
        mode_box = ttk.LabelFrame(main, text="Tryb pracy", padding=8)
        mode_box.pack(fill="x")
        self.mode_var = tk.StringVar(value=MODE_KEYBOARD)
        ttk.Radiobutton(
            mode_box, text="Klawiatura → SimRail (zalecany)",
            variable=self.mode_var, value=MODE_KEYBOARD,
            command=self._on_mode_change,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_box, text="Wirtualny pad Xbox 360 (ViGEmBus)",
            variable=self.mode_var, value=MODE_XBOX,
            command=self._on_mode_change,
        ).pack(anchor="w")

        # --- profile ---
        profile_box = ttk.LabelFrame(main, text="Profil", padding=8)
        profile_box.pack(fill="x", pady=(8, 0))
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(
            profile_box, textvariable=self.profile_var, state="readonly")
        self.profile_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(profile_box, text="Odśwież",
                   command=self._refresh_profiles).pack(side="left", padx=(6, 0))

        # --- options ---
        options = ttk.Frame(main)
        options.pack(fill="x", pady=(8, 0))
        self.dry_run_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Tryb testowy (bez wysyłania do gry)",
                        variable=self.dry_run_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Szczegółowe logi",
                        variable=self.verbose_var).pack(anchor="w")

        # --- buttons ---
        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(8, 0))
        self.start_btn = ttk.Button(buttons, text="▶ Start", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="■ Stop", command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Urządzenia",
                   command=self.show_devices).pack(side="left", padx=(6, 0))

        self.status_var = tk.StringVar(value="Zatrzymany")
        ttk.Label(buttons, textvariable=self.status_var).pack(side="right")

        # --- log ---
        self.log_text = ScrolledText(main, height=12, state="disabled",
                                     font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))

        self._refresh_profiles()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # ---------- helpers ----------

    def log(self, message: str) -> None:
        """Thread-safe: called from the bridge thread."""
        self.log_queue.put(message)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _profiles_for_mode(self) -> list[str]:
        files = sorted(p.name for p in CONFIG_DIR.glob("*.json"))
        if self.mode_var.get() == MODE_XBOX:
            preferred = [f for f in files if "xbox" in f]
            return preferred + [f for f in files if "xbox" not in f]
        return [f for f in files if "xbox" not in f]

    def _refresh_profiles(self) -> None:
        values = self._profiles_for_mode()
        self.profile_combo["values"] = values
        if values and self.profile_var.get() not in values:
            self.profile_var.set(values[0])

    def _on_mode_change(self) -> None:
        self.profile_var.set("")
        self._refresh_profiles()

    def _set_running(self, running: bool) -> None:
        state_run = "disabled" if running else "normal"
        self.start_btn.configure(state=state_run)
        self.stop_btn.configure(state="normal" if running else "disabled")
        self.profile_combo.configure(state="disabled" if running else "readonly")
        self.status_var.set("Działa" if running else "Zatrzymany")

    # ---------- actions ----------

    def start(self) -> None:
        if self.bridge is not None and self.bridge.is_alive():
            return
        profile_name = self.profile_var.get()
        if not profile_name:
            self._append_log("Wybierz profil.")
            return
        config_path = str(CONFIG_DIR / profile_name)
        self.bridge = BridgeThread(
            mode=self.mode_var.get(),
            config_path=config_path,
            dry_run=self.dry_run_var.get(),
            verbose=self.verbose_var.get(),
            log=self.log,
        )
        self._append_log(f"--- Start ({profile_name}) ---")
        self.bridge.start()
        self._set_running(True)

    def stop(self) -> None:
        if self.bridge is not None:
            self.bridge.stop()

    def show_devices(self) -> None:
        def worker() -> None:
            try:
                from .joystick import list_devices
                devices = list_devices()
                if not devices:
                    self.log("Nie wykryto żadnego kontrolera.")
                for i, name in enumerate(devices):
                    self.log(f"[{i}] {name}")
            except Exception as exc:
                self.log(f"BLAD: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    # ---------- periodic ----------

    def _poll(self) -> None:
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        if self.bridge is not None and not self.bridge.is_alive():
            self.bridge = None
            self._set_running(False)
        self.after(100, self._poll)

    def _on_close(self) -> None:
        if self.bridge is not None:
            self.bridge.stop()
            self.bridge.join(timeout=2.0)
        self.destroy()


def main() -> int:
    app = App()
    app.mainloop()
    return 0
