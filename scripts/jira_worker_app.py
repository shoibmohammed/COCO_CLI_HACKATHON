#!/usr/bin/env python3
"""
scripts/jira_worker_app.py
MFG Predictive Maintenance — Local Integration Setup & Worker Control.

Two credential models:
- JIRA: Preconfigured for live demo (loaded from private local config)
- SNOWFLAKE: Entered by the user in the UI
- Security: API tokens and credentials are never displayed in logs or UI.

Usage:
    python scripts/jira_worker_app.py
"""

import os
import sys
import subprocess
import signal
import time
import platform
import webbrowser
import json
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    tk = None
    ttk = None
    messagebox = None
    scrolledtext = None

# ---------------------------------------------------------------------------
# PATHS — derived from script location, never CWD
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKER_DIR = PROJECT_ROOT / "local_jira_worker"
WORKER_SCRIPT = WORKER_DIR / "worker.py"
ENV_FILE = WORKER_DIR / ".env"
JIRA_DEMO_CONFIG = WORKER_DIR / ".jira_demo.json"  # Private, never committed
IS_WINDOWS = platform.system() == "Windows"
VENV_DIR = WORKER_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe" if IS_WINDOWS else VENV_DIR / "bin" / "python"

sys.path.insert(0, str(WORKER_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# Snowflake connector (optional)
try:
    import snowflake.connector
    SF_AVAILABLE = True
except ImportError:
    SF_AVAILABLE = False

def load_env(env_path=None):
    """Loads environment key-value pairs from .env file."""
    path = Path(env_path) if env_path else ENV_FILE
    env_dict = {}
    if path.exists():
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_dict[k.strip()] = v.strip()
    return env_dict


# ---------------------------------------------------------------------------
# JIRA DEMO CONFIG — loaded from private local file (never in repo)
# ---------------------------------------------------------------------------
def load_jira_demo_config():
    """Load preconfigured Jira credentials from private local file."""
    if JIRA_DEMO_CONFIG.exists():
        try:
            with open(JIRA_DEMO_CONFIG) as f:
                cfg = json.load(f)
            if cfg.get("base_url") and cfg.get("email") and cfg.get("token"):
                return cfg
        except Exception:
            pass
    # Also check env vars (for CI or pre-set environments)
    if os.environ.get("JIRA_BASE_URL") and os.environ.get("JIRA_API_TOKEN"):
        return {
            "base_url": os.environ["JIRA_BASE_URL"],
            "email": os.environ.get("JIRA_USER_EMAIL", ""),
            "token": os.environ["JIRA_API_TOKEN"],
            "project_key": os.environ.get("JIRA_PROJECT_KEY", "KAN"),
        }
    return None


# ---------------------------------------------------------------------------
# WORKER MANAGER
# ---------------------------------------------------------------------------
class WorkerManager:
    def __init__(self):
        self._process = None
        self._pid_file = WORKER_DIR / ".worker.pid"

    @property
    def is_running(self):
        if self._process and self._process.poll() is None:
            return True
        pid = self._read_pid()
        if pid:
            return self._is_pid_alive(pid)
        return False

    def start(self):
        if self.is_running:
            return False, "Worker already running."
        if not WORKER_SCRIPT.exists():
            return False, f"worker.py not found at {WORKER_SCRIPT}"
        python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
        env = os.environ.copy()
        try:
            kwargs = {"cwd": str(WORKER_DIR), "env": env,
                      "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
            if IS_WINDOWS:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            self._process = subprocess.Popen([python_exe, str(WORKER_SCRIPT)], **kwargs)
            self._write_pid(self._process.pid)
            return True, f"Worker started (PID: {self._process.pid})"
        except Exception as e:
            return False, f"Start failed: {str(e)[:200]}"

    def stop(self):
        if self._process and self._process.poll() is None:
            try:
                if IS_WINDOWS:
                    self._process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=10)
            except (subprocess.TimeoutExpired, Exception):
                self._process.kill()
            self._remove_pid()
            return True, "Worker stopped."
        pid = self._read_pid()
        if pid and self._is_pid_alive(pid):
            try:
                if IS_WINDOWS:
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
                else:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
            self._remove_pid()
            return True, "Worker stopped."
        self._remove_pid()
        return False, "Worker not running."

    def _write_pid(self, pid):
        try: self._pid_file.write_text(str(pid))
        except Exception: pass

    def _read_pid(self):
        try:
            if self._pid_file.exists(): return int(self._pid_file.read_text().strip())
        except Exception: pass
        return 0

    def _remove_pid(self):
        try: self._pid_file.unlink(missing_ok=True)
        except Exception: pass

    def _is_pid_alive(self, pid):
        try:
            if IS_WINDOWS:
                r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                return str(pid) in r.stdout
            else:
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False


# ---------------------------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------------------------
class IntegrationSetupApp:
    def __init__(self):
        self.worker = WorkerManager()
        self.jira_connected = False
        self.sf_connected = False
        self.sf_conn = None
        self.jira_cfg = None

        self.root = tk.Tk()
        self.root.title("MFG Predictive Maintenance — Integration Setup")
        self.root.geometry("560x740")
        self.root.configure(bg="#0B0F19")
        self._build_ui()

    def _build_ui(self):
        # Title
        tk.Label(self.root, text="MFG PREDICTIVE MAINTENANCE",
                 font=("Segoe UI", 10), bg="#0B0F19", fg="#94A3B8").pack(pady=(12, 0))
        tk.Label(self.root, text="INTEGRATION SETUP",
                 font=("Segoe UI", 14, "bold"), bg="#0B0F19", fg="#F8FAFC").pack(pady=(0, 10))

        # === JIRA SECTION ===
        jira_frame = tk.LabelFrame(self.root, text="🎫 JIRA CLOUD", bg="#1E293B",
                                   fg="#F8FAFC", font=("Segoe UI", 9, "bold"), padx=12, pady=8)
        jira_frame.pack(fill="x", padx=15, pady=(0, 8))

        self.jira_status_lbl = tk.Label(jira_frame, text="Status: 🔴 NOT CONNECTED",
                                        font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#EF4444")
        self.jira_status_lbl.pack(anchor="w")
        self.jira_detail_lbl = tk.Label(jira_frame, text="Project: KAN",
                                        font=("Segoe UI", 8), bg="#1E293B", fg="#64748B")
        self.jira_detail_lbl.pack(anchor="w")

        tk.Button(jira_frame, text="🔗 START JIRA CONNECTION", command=self._connect_jira,
                  bg="#38BDF8", fg="white", font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(8, 0))

        # === SNOWFLAKE SECTION ===
        sf_frame = tk.LabelFrame(self.root, text="❄ SNOWFLAKE", bg="#1E293B",
                                 fg="#F8FAFC", font=("Segoe UI", 9, "bold"), padx=12, pady=8)
        sf_frame.pack(fill="x", padx=15, pady=(0, 8))

        self.sf_status_lbl = tk.Label(sf_frame, text="Status: 🔴 NOT CONNECTED",
                                      font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#EF4444")
        self.sf_status_lbl.pack(anchor="w")

        self.sf_entries = {}
        sf_fields = [
            ("Account", "SNOWFLAKE_ACCOUNT", "", False),
            ("Username", "SNOWFLAKE_USER", "", False),
            ("Password", "SNOWFLAKE_PASSWORD", "", True),
            ("Role", "SNOWFLAKE_ROLE", "ACCOUNTADMIN", False),
            ("Warehouse", "SNOWFLAKE_WAREHOUSE", "PM_OEE_WH", False),
            ("Database", "SNOWFLAKE_DATABASE", "PM_OEE_DB", False),
            ("Schema", "SNOWFLAKE_SCHEMA", "CORE", False),
        ]
        for label, key, default, secret in sf_fields:
            row = tk.Frame(sf_frame, bg="#1E293B")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, font=("Segoe UI", 8), bg="#1E293B",
                     fg="#CBD5E1", width=12, anchor="w").pack(side="left")
            entry = tk.Entry(row, font=("Consolas", 9), bg="#0F172A", fg="#F8FAFC",
                             insertbackground="#F8FAFC", width=38)
            if secret:
                entry.config(show="•")
            if default:
                entry.insert(0, default)
            entry.pack(side="left", padx=4)
            self.sf_entries[key] = entry

        btn_row = tk.Frame(sf_frame, bg="#1E293B")
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="🔗 TEST SNOWFLAKE CONNECTION", command=self._test_snowflake,
                  bg="#38BDF8", fg="white", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(btn_row, text="💾 SAVE", command=self._save_snowflake,
                  bg="#64748B", fg="white", font=("Segoe UI", 9)).pack(side="left", padx=5)

        # === WORKER SECTION ===
        worker_frame = tk.LabelFrame(self.root, text="⚙ WORKER", bg="#1E293B",
                                     fg="#F8FAFC", font=("Segoe UI", 9, "bold"), padx=12, pady=8)
        worker_frame.pack(fill="x", padx=15, pady=(0, 8))

        self.worker_status_lbl = tk.Label(worker_frame, text="Status: 🔴 NOT STARTED",
                                          font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#EF4444")
        self.worker_status_lbl.pack(anchor="w")
        self.heartbeat_lbl = tk.Label(worker_frame, text="",
                                      font=("Segoe UI", 8), bg="#1E293B", fg="#64748B")
        self.heartbeat_lbl.pack(anchor="w")

        wbtn_row = tk.Frame(worker_frame, bg="#1E293B")
        wbtn_row.pack(fill="x", pady=(8, 0))
        self.start_btn = tk.Button(wbtn_row, text="▶ START WORKER", command=self._start_worker,
                                   bg="#22C55E", fg="white", font=("Segoe UI", 9, "bold"), state="disabled")
        self.start_btn.pack(side="left")
        tk.Button(wbtn_row, text="⏹ STOP", command=self._stop_worker,
                  bg="#EF4444", fg="white", font=("Segoe UI", 9)).pack(side="left", padx=5)

        # === ENVIRONMENT STATUS ===
        env_frame = tk.Frame(self.root, bg="#0B0F19")
        env_frame.pack(fill="x", padx=15, pady=(5, 0))

        self.env_lbl = tk.Label(env_frame, text="Environment: 🔴 NOT READY",
                                font=("Segoe UI", 10, "bold"), bg="#0B0F19", fg="#EF4444")
        self.env_lbl.pack(anchor="w")

        self.open_btn = tk.Button(env_frame, text="🌐 OPEN STREAMLIT", command=self._open_streamlit,
                                  bg="#8B5CF6", fg="white", font=("Segoe UI", 10, "bold"), state="disabled")
        self.open_btn.pack(fill="x", pady=(8, 0))

        # === LOG ===
        log_frame = tk.LabelFrame(self.root, text="Log", bg="#1E293B",
                                  fg="#F8FAFC", font=("Segoe UI", 8))
        log_frame.pack(fill="both", expand=True, padx=15, pady=(8, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, font=("Consolas", 8),
                                                  bg="#0F172A", fg="#CBD5E1", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Load existing config if available
        self._load_existing_config()
        self._log(f"Project: {PROJECT_ROOT}")

    # ===================================================================
    # HELPERS
    # ===================================================================
    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _update_env_status(self):
        if self.jira_connected and self.sf_connected:
            self.env_lbl.config(text="Environment: 🟢 READY", fg="#22C55E")
            self.start_btn.config(state="normal")
            # Check worker
            if self.worker.is_running:
                self.worker_status_lbl.config(text="Status: 🟢 ONLINE", fg="#22C55E")
                self.open_btn.config(state="normal")
        elif self.jira_connected or self.sf_connected:
            self.env_lbl.config(text="Environment: 🟡 PARTIAL", fg="#F59E0B")
        else:
            self.env_lbl.config(text="Environment: 🔴 NOT READY", fg="#EF4444")

    def _load_existing_config(self):
        """Load saved Snowflake config if .env exists."""
        if ENV_FILE.exists():
            try:
                with open(ENV_FILE) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, _, val = line.partition("=")
                            key = key.replace("export ", "").strip()
                            val = val.strip().strip("'\"")
                            os.environ[key] = val
                            if key in self.sf_entries and key != "SNOWFLAKE_PASSWORD":
                                self.sf_entries[key].delete(0, "end")
                                self.sf_entries[key].insert(0, val)
                            elif key == "SNOWFLAKE_PASSWORD" and val:
                                self.sf_entries[key].delete(0, "end")
                                self.sf_entries[key].insert(0, val)
                self._log("Loaded saved configuration")
            except Exception:
                pass

    # ===================================================================
    # JIRA CONNECTION (Preconfigured)
    # ===================================================================
    def _connect_jira(self):
        self._log("Loading Jira demo configuration...")
        self.jira_cfg = load_jira_demo_config()

        if not self.jira_cfg:
            self.jira_status_lbl.config(text="Status: 🔴 DEMO CONFIG MISSING", fg="#EF4444")
            self.jira_detail_lbl.config(text="Create local_jira_worker/.jira_demo.json with credentials")
            self._log("Jira demo config not found.")
            self._log(f"Expected at: {JIRA_DEMO_CONFIG}")
            self._log('Format: {"base_url":"https://x.atlassian.net","email":"...","token":"...","project_key":"KAN"}')
            messagebox.showwarning("Jira Config Missing",
                f"Preconfigured Jira credentials not found.\n\n"
                f"Create: {JIRA_DEMO_CONFIG}\n\n"
                f'Format:\n{{"base_url":"...","email":"...","token":"...","project_key":"KAN"}}')
            return

        # Test connection
        self._log("Testing Jira authentication...")
        try:
            import requests
            from base64 import b64encode
            url = self.jira_cfg["base_url"].rstrip("/")
            auth = b64encode(f"{self.jira_cfg['email']}:{self.jira_cfg['token']}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}

            resp = requests.get(f"{url}/rest/api/2/myself", headers=headers, timeout=10)
            if resp.status_code != 200:
                self.jira_status_lbl.config(text=f"Status: 🔴 AUTH FAILED (HTTP {resp.status_code})", fg="#EF4444")
                self._log(f"Jira: HTTP {resp.status_code}")
                return

            user_name = resp.json().get("displayName", "")
            project_key = self.jira_cfg.get("project_key", "KAN")

            # Test project access
            resp2 = requests.get(f"{url}/rest/api/2/project/{project_key}", headers=headers, timeout=10)
            project_ok = resp2.status_code == 200

            self.jira_connected = True
            self.jira_status_lbl.config(text="Status: 🟢 CONNECTED", fg="#22C55E")
            self.jira_detail_lbl.config(
                text=f"Project: {project_key} · User: {user_name} · Create Issues: {'✅' if project_ok else '❌'}")
            self._log(f"Jira: Connected as {user_name} · Project {project_key}: {'✅' if project_ok else '❌'}")

            # Apply to env for worker
            os.environ["JIRA_BASE_URL"] = self.jira_cfg["base_url"]
            os.environ["JIRA_USER_EMAIL"] = self.jira_cfg["email"]
            os.environ["JIRA_API_TOKEN"] = self.jira_cfg["token"]
            os.environ["JIRA_PROJECT_KEY"] = project_key

            self._update_env_status()

        except Exception as e:
            self.jira_status_lbl.config(text="Status: 🔴 CONNECTION FAILED", fg="#EF4444")
            self._log(f"Jira error: {str(e)[:150]}")

    # ===================================================================
    # SNOWFLAKE CONNECTION (User-entered)
    # ===================================================================
    def _get_sf_values(self):
        return {k: e.get().strip() for k, e in self.sf_entries.items()}

    def _test_snowflake(self):
        if not SF_AVAILABLE:
            self._log("snowflake-connector-python not installed. pip install snowflake-connector-python")
            messagebox.showerror("Missing Package", "Install: pip install snowflake-connector-python")
            return

        vals = self._get_sf_values()
        if not vals.get("SNOWFLAKE_ACCOUNT") or not vals.get("SNOWFLAKE_USER") or not vals.get("SNOWFLAKE_PASSWORD"):
            self._log("Fill in Account, Username, and Password")
            return

        self._log("Testing Snowflake connection...")
        try:
            conn = snowflake.connector.connect(
                account=vals["SNOWFLAKE_ACCOUNT"],
                user=vals["SNOWFLAKE_USER"],
                password=vals["SNOWFLAKE_PASSWORD"],
                role=vals.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
                warehouse=vals.get("SNOWFLAKE_WAREHOUSE", "PM_OEE_WH"),
                database=vals.get("SNOWFLAKE_DATABASE", "PM_OEE_DB"),
                schema=vals.get("SNOWFLAKE_SCHEMA", "CORE"),
            )
            self.sf_conn = conn
            self._log("Snowflake: Authenticated ✅")

            # Verify tables
            tables = ["WORK_ORDERS", "JIRA_INTEGRATION_QUEUE", "JIRA_WORKER_HEARTBEAT", "JIRA_TICKET_AUDIT"]
            from config import table
            for tbl in tables:
                try:
                    full_tbl = table(tbl)
                    cur = conn.cursor()
                    cur.execute(f"SELECT 1 FROM {full_tbl} LIMIT 1")
                    cur.close()
                    self._log(f"  Table {tbl}: ✅")
                except Exception:
                    self._log(f"  Table {tbl}: ❌")

            self.sf_connected = True
            self.sf_status_lbl.config(text="Status: 🟢 CONNECTED", fg="#22C55E")

            # Apply to env
            for k, v in vals.items():
                os.environ[k] = v

            self._update_env_status()

        except Exception as e:
            self.sf_status_lbl.config(text="Status: 🔴 FAILED", fg="#EF4444")
            self._log(f"Snowflake: {str(e)[:150]}")

    def _save_snowflake(self):
        vals = self._get_sf_values()
        try:
            WORKER_DIR.mkdir(parents=True, exist_ok=True)
            lines = ["# Auto-generated — DO NOT COMMIT\n"]
            for k, v in vals.items():
                lines.append(f"{k}={v}\n")
            # Add Jira from env if available
            for jk in ["JIRA_BASE_URL", "JIRA_USER_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"]:
                jv = os.environ.get(jk, "")
                if jv:
                    lines.append(f"{jk}={jv}\n")
            lines.append("WORKER_POLL_INTERVAL=10\n")
            lines.append("WORKER_MAX_RETRIES=3\n")
            lines.append("WORKER_BATCH_SIZE=5\n")
            with open(ENV_FILE, "w") as f:
                f.writelines(lines)
            self._log(f"Configuration saved to {ENV_FILE}")
        except Exception as e:
            self._log(f"Save error: {str(e)[:100]}")

    # ===================================================================
    # WORKER
    # ===================================================================
    def _start_worker(self):
        if not self.jira_connected or not self.sf_connected:
            self._log("Connect Jira and Snowflake first.")
            return
        self._save_snowflake()  # Ensure .env is up to date
        self._log("Starting worker...")
        ok, msg = self.worker.start()
        self._log(msg)
        if ok:
            self.worker_status_lbl.config(text="Status: 🟡 STARTING...", fg="#F59E0B")
            self.root.after(5000, self._check_heartbeat)

    def _stop_worker(self):
        ok, msg = self.worker.stop()
        self._log(msg)
        self.worker_status_lbl.config(text="Status: 🔴 STOPPED", fg="#EF4444")
        self.open_btn.config(state="disabled")

    def _check_heartbeat(self):
        if not self.sf_conn:
            return
        try:
            cur = self.sf_conn.cursor(snowflake.connector.DictCursor)
            cur.execute("""
                SELECT STATUS, DATEDIFF('second', LAST_HEARTBEAT, CURRENT_TIMESTAMP()) AS AGE
                FROM PM_OEE_DB.CORE.JIRA_WORKER_HEARTBEAT
                WHERE WORKER_ID = 'LOCAL_JIRA_WORKER_01' LIMIT 1
            """)
            rows = cur.fetchall()
            cur.close()
            if rows and rows[0]["STATUS"] == "ONLINE" and rows[0]["AGE"] <= 300:
                self.worker_status_lbl.config(text="Status: 🟢 ONLINE", fg="#22C55E")
                self.heartbeat_lbl.config(text=f"Heartbeat: {rows[0]['AGE']}s ago")
                self.open_btn.config(state="normal")
                self._log("Worker: ONLINE ✅")
            else:
                self.worker_status_lbl.config(text="Status: 🟡 WAITING...", fg="#F59E0B")
                self.root.after(5000, self._check_heartbeat)
        except Exception:
            self.root.after(5000, self._check_heartbeat)

    # ===================================================================
    # OPEN STREAMLIT
    # ===================================================================
    def _open_streamlit(self):
        account = os.environ.get("SNOWFLAKE_ACCOUNT", "")
        url = f"https://app.snowflake.com/{account}"
        self._log(f"Opening Streamlit: {url}")
        webbrowser.open(url)

    # ===================================================================
    # RUN
    # ===================================================================
    def run(self):
        self.root.mainloop()
        if self.sf_conn:
            try: self.sf_conn.close()
            except Exception: pass


if __name__ == "__main__":
    app = IntegrationSetupApp()
    app.run()
