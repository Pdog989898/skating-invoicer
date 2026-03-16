import json
import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from app.database import Database
from app.services.finance_service import FinanceService
from app.services.invoice_service import InvoiceService
from app.services.update_service import UpdateService
from app.ui.finance_tab import FinanceTab
from app.ui.invoice_tab import InvoiceTab
from app.ui.lessons_tab import LessonsTab

LOG_FILE = "skating_invoicer.log"
SETTINGS_FILE = Path("update_settings.json")


class SkatingInvoicerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Skating Invoicer Pro")
        self.geometry("1200x760")
        self.option_add("*Font", "SegoeUI 10")

        self._configure_logging()
        self.db = Database("skating.db")
        self.db.backup_on_startup()
        self.db.init_schema()

        self.finance_service = FinanceService(self.db)
        self.invoice_service = InvoiceService(self.db)
        self.update_service = UpdateService("version.txt")

        self.selected_skater = None
        self.update_settings = self._load_settings()
        self._build_layout()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_logging(self):
        logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    def _build_layout(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        left = ttk.Frame(root, width=280)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Skaters", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.skater_var = tk.StringVar()
        self.skater_combo = ttk.Combobox(left, state="readonly", textvariable=self.skater_var)
        self.skater_combo.pack(fill="x", pady=4)
        self.skater_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_skater_selected())

        ttk.Button(left, text="Add Skater", command=self.add_skater).pack(fill="x", pady=4)
        ttk.Button(left, text="Edit Selected Skater", command=self.edit_skater).pack(fill="x", pady=4)
        ttk.Button(left, text="Manage Lesson Types", command=self.manage_lesson_types).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=12)
        ttk.Label(left, text="Updater", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.update_url_var = tk.StringVar(value=self.update_settings.get("version_json_url", ""))
        ttk.Entry(left, textvariable=self.update_url_var).pack(fill="x", pady=4)
        ttk.Button(left, text="Check for Updates", command=self.check_updates).pack(fill="x", pady=4)

        ttk.Separator(left).pack(fill="x", pady=12)
        ttk.Button(left, text="Admin Panel", command=self.admin_login).pack(fill="x")

        content = ttk.Frame(root)
        content.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill="both", expand=True)

        self.lessons_tab = LessonsTab(self.notebook, self)
        self.invoice_tab = InvoiceTab(self.notebook, self)
        self.finance_tab = FinanceTab(self.notebook, self)
        self.notebook.add(self.lessons_tab, text="Lessons")
        self.notebook.add(self.invoice_tab, text="Invoices")
        self.notebook.add(self.finance_tab, text="Finance")

    def _load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_settings(self):
        SETTINGS_FILE.write_text(json.dumps({"version_json_url": self.update_url_var.get()}, indent=2), encoding="utf-8")

    def refresh_all(self):
        self.skaters = self.db.fetchall("SELECT id, name, email FROM skaters ORDER BY name")
        self.lesson_types = self.db.fetchall("SELECT id, name, rate FROM lesson_types ORDER BY name")
        self.skater_combo["values"] = [s["name"] for s in self.skaters]
        self.lessons_tab.set_lesson_types(self.lesson_types)
        self.lessons_tab.set_selected_skater(self.selected_skater)
        self.refresh_finance()

    def refresh_finance(self):
        self.finance_tab.refresh()

    def _on_skater_selected(self):
        idx = self.skater_combo.current()
        self.selected_skater = dict(self.skaters[idx]) if idx >= 0 else None
        self.lessons_tab.set_selected_skater(self.selected_skater)

    def add_skater(self):
        name = simpledialog.askstring("Add skater", "Name", parent=self)
        email = simpledialog.askstring("Add skater", "Email", parent=self)
        if name and email:
            self.db.execute("INSERT INTO skaters(name, email) VALUES(?, ?)", (name.strip(), email.strip()))
            self.refresh_all()

    def edit_skater(self):
        if not self.selected_skater:
            messagebox.showinfo("Skater", "Select a skater first")
            return
        name = simpledialog.askstring("Edit skater", "Name", initialvalue=self.selected_skater["name"], parent=self)
        email = simpledialog.askstring("Edit skater", "Email", initialvalue=self.selected_skater["email"], parent=self)
        if name and email:
            self.db.execute("UPDATE skaters SET name=?, email=? WHERE id=?", (name.strip(), email.strip(), self.selected_skater["id"]))
            self.selected_skater = {**self.selected_skater, "name": name.strip(), "email": email.strip()}
            self.refresh_all()

    def manage_lesson_types(self):
        dialog = tk.Toplevel(self)
        dialog.title("Lesson Types")
        listbox = tk.Listbox(dialog)
        listbox.pack(fill="both", expand=True, padx=8, pady=8)
        rows = self.db.fetchall("SELECT id, name, rate FROM lesson_types ORDER BY name")
        for row in rows:
            listbox.insert("end", f"{row['name']} | ${float(row['rate']):.2f}")

        def add_new():
            name = simpledialog.askstring("Lesson type", "Name", parent=dialog)
            rate = simpledialog.askfloat("Lesson type", "Rate", parent=dialog)
            if name and rate is not None:
                self.db.execute("INSERT INTO lesson_types(name, rate) VALUES(?, ?)", (name.strip(), rate))
                dialog.destroy()
                self.refresh_all()

        ttk.Button(dialog, text="Add Lesson Type", command=add_new).pack(fill="x", padx=8, pady=(0, 8))

    def check_updates(self):
        self._save_settings()
        if not self.update_url_var.get().strip():
            messagebox.showinfo("Updater", "Enter a version.json URL first.")
            return
        try:
            result = self.update_service.check(self.update_url_var.get().strip())
            if result["has_update"]:
                if messagebox.askyesno(
                    "Update Available",
                    f"Local {result['local']} -> Remote {result['remote']}\nDownload and restart now?",
                ):
                    messagebox.showinfo("Download", f"Download latest build:\n{result['download_url']}")
            else:
                messagebox.showinfo("Up to date", f"Current version {result['local']} is up to date.")
        except Exception as exc:
            self.show_error("Update check failed", exc)

    def admin_login(self):
        username = simpledialog.askstring("Admin Login", "Username", parent=self)
        if username is None:
            return
        password = simpledialog.askstring("Admin Login", "Password", parent=self, show="*")
        if password is None:
            return
        if self.db.verify_admin(username, password):
            messagebox.showinfo("Admin", "Login successful.")
        else:
            messagebox.showerror("Admin", "Invalid username or password")

    def show_error(self, title: str, exc: Exception):
        logging.exception(title)
        messagebox.showerror(title, str(exc))

    def on_close(self):
        self.db.close()
        self.destroy()


def run():
    app = SkatingInvoicerApp()
    app.mainloop()


if __name__ == "__main__":
    run()
