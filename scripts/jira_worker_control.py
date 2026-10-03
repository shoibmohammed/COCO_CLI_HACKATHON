#!/usr/bin/env python3
"""
scripts/jira_worker_control.py
Local Jira Worker Control Center — tkinter GUI for judge demo.
Runs on the judge's local machine to start/stop/monitor the Local Jira Worker.

Usage:
    python scripts/jira_worker_control.py

Requirements:
    - Python 3.8+ with tkinter (standard library)
    - local_jira_worker/ directory with worker.py
    - .env file with credentials (never displayed)
"""

import os
import sys
import subprocess
import signal
import time
import threading
import platform
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk = None
    ttk = None
    messagebox = None

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKER_DIR = PROJECT_ROOT / "local_jira_worker"
WORKER_SCRIPT = WORKER_DIR / "worker.py"
IS_WINDOWS = platform.system() == "Windows"

# venv paths
if IS_WINDOWS:
    VENV_DIR = WORKER_DIR / ".venv"
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_DIR = WORKER_DIR / ".venv"
    VENV_PYTHON = VENV_DIR / "bin" / "python"


class WorkerProcess:
    """Manages the Local Jira Worker subprocess."""

    def __init__(self):
        self._process = None
        self._pid_file = WORKER_DIR / ".worker.pid"

    @property
    def is_running(self) -> bool:
        if self._process and self._process.poll() is None:
            return True
        pid = self._read_pid()
        if pid:
            return self._is_pid_alive(pid)
        return False

    def start(self) -> tuple:
        """Start the worker. Returns (success, message)."""
        if self.is_running:
            return False, "Worker is already running."

        if not WORKER_SCRIPT.exists():
            return False, f"Worker script not found: {WORKER_SCRIPT}"

        python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

        env = os.environ.copy()
        env_file = WORKER_DIR / ".env"
        if env_file.exists():
            self._load_env(env_file, env)

        try:
            if IS_WINDOWS:
                self._process = subprocess.Popen(
                    [python_exe, str(WORKER_SCRIPT)],
                    cwd=str(WORKER_DIR),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self._process = subprocess.Popen(
                    [python_exe, str(WORKER_SCRIPT)],
                    cwd=str(WORKER_DIR),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )

            self._write_pid(self._process.pid)
            return True, f"Worker started (PID: {self._process.pid})"

        except Exception as e:
            return False, f"Failed to start worker: {str(e)[:200]}"

    def stop(self) -> tuple:
        """Stop the worker. Returns (success, message)."""
        if self._process and self._process.poll() is None:
            try:
                if IS_WINDOWS:
                    self._process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=10)
                self._remove_pid()
                return True, "Worker stopped."
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._remove_pid()
                return True, "Worker killed (did not stop gracefully)."
            except Exception as e:
                return False, f"Error stopping worker: {str(e)[:200]}"

        pid = self._read_pid()
        if pid and self._is_pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM if not IS_WINDOWS else signal.SIGINT)
                time.sleep(2)
                self._remove_pid()
                return True, f"Worker (PID {pid}) stopped."
            except Exception as e:
                return False, f"Could not stop PID {pid}: {str(e)[:100]}"

        self._remove_pid()
        return False, "Worker is not running."

    def _load_env(self, env_file: Path, env: dict):
        """Load .env file into environment dict (no secrets logged)."""
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        key = key.replace("export ", "").strip()
                        val = val.strip().strip("'\"")
                        env[key] = val
        except Exception:
            pass

    def _write_pid(self, pid: int):
        try:
            self._pid_file.write_text(str(pid))
        except Exception:
            pass

    def _read_pid(self) -> int:
        try:
            if self._pid_file.exists():
                return int(self._pid_file.read_text().strip())
        except Exception:
            pass
        return 0

    def _remove_pid(self):
        try:
            self._pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True
                )
                return str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False


class ControlCenterApp:
    """Tkinter GUI for the Jira Worker Control Center."""

    def __init__(self):
        self.worker = WorkerProcess()
        self.root = tk.Tk()
        self.root.title("Jira Worker Control Center")
        self.root.geometry("420x380")
        self.root.resizable(False, False)

        self._build_ui()
        self._update_status()

    def _build_ui(self):
        # Title
        title = ttk.Label(self.root, text="🎫 Local Jira Worker Control Center",
                          font=("Segoe UI", 13, "bold"))
        title.pack(pady=(15, 5))

        subtitle = ttk.Label(self.root, text="MFG Predictive Maintenance V3",
                             font=("Segoe UI", 9))
        subtitle.pack(pady=(0, 15))

        # Status frame
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.status_label = ttk.Label(status_frame, text="Checking...",
                                      font=("Segoe UI", 11, "bold"))
        self.status_label.pack(anchor="w")

        self.process_label = ttk.Label(status_frame, text="Process: Unknown",
                                       font=("Segoe UI", 9))
        self.process_label.pack(anchor="w", pady=(4, 0))

        self.heartbeat_label = ttk.Label(status_frame, text="Heartbeat: Unknown",
                                          font=("Segoe UI", 9))
        self.heartbeat_label.pack(anchor="w", pady=(2, 0))

        # Buttons frame
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.start_btn = ttk.Button(btn_frame, text="▶  START WORKER",
                                    command=self._on_start)
        self.start_btn.pack(fill="x", pady=3)

        self.stop_btn = ttk.Button(btn_frame, text="⏹  STOP WORKER",
                                   command=self._on_stop)
        self.stop_btn.pack(fill="x", pady=3)

        self.restart_btn = ttk.Button(btn_frame, text="🔄  RESTART WORKER",
                                      command=self._on_restart)
        self.restart_btn.pack(fill="x", pady=3)

        self.health_btn = ttk.Button(btn_frame, text="🔍  HEALTH CHECK",
                                     command=self._on_health)
        self.health_btn.pack(fill="x", pady=3)

        # Log area
        self.log_text = tk.Text(self.root, height=4, font=("Consolas", 8),
                                state="disabled", bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill="x", padx=20, pady=(5, 15))

    def _log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _update_status(self):
        running = self.worker.is_running
        if running:
            self.status_label.config(text="🟢 WORKER ONLINE", foreground="green")
            self.process_label.config(text="Process: RUNNING")
        else:
            self.status_label.config(text="🔴 WORKER OFFLINE", foreground="red")
            self.process_label.config(text="Process: STOPPED")

        # Schedule periodic refresh
        self.root.after(5000, self._update_status)

    def _on_start(self):
        self._log("Starting worker...")
        ok, msg = self.worker.start()
        self._log(msg)
        if ok:
            time.sleep(1)
            self._update_status()

    def _on_stop(self):
        self._log("Stopping worker...")
        ok, msg = self.worker.stop()
        self._log(msg)
        self._update_status()

    def _on_restart(self):
        self._log("Restarting worker...")
        self.worker.stop()
        time.sleep(2)
        ok, msg = self.worker.start()
        self._log(f"Restart: {msg}")
        if ok:
            time.sleep(1)
        self._update_status()

    def _on_health(self):
        running = self.worker.is_running
        lines = [
            f"Worker: {'ONLINE' if running else 'OFFLINE'}",
            f"Process: {'RUNNING' if running else 'STOPPED'}",
            f"Worker Dir: {WORKER_DIR}",
            f"Venv: {'Found' if VENV_PYTHON.exists() else 'Not found'}",
        ]
        self._log("\n".join(lines))
        messagebox.showinfo("Health Check", "\n".join(lines))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ControlCenterApp()
    app.run()
