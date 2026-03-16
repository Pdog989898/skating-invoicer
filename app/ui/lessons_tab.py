import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk


class LessonsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        pad = {"padx": 8, "pady": 6}
        self.columnconfigure(1, weight=1)
        self.rowconfigure(6, weight=1)

        ttk.Label(self, text="Selected Skater").grid(row=0, column=0, sticky="w", **pad)
        self.skater_label = ttk.Label(self, text="(none)")
        self.skater_label.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(self, text="Lesson Type").grid(row=1, column=0, sticky="w", **pad)
        self.lesson_type_var = tk.StringVar()
        self.lesson_type_combo = ttk.Combobox(self, textvariable=self.lesson_type_var, state="readonly")
        self.lesson_type_combo.grid(row=1, column=1, sticky="ew", **pad)
        self.lesson_type_combo.bind("<<ComboboxSelected>>", self._fill_amount)

        ttk.Label(self, text="Amount").grid(row=2, column=0, sticky="w", **pad)
        self.amount_entry = ttk.Entry(self)
        self.amount_entry.grid(row=2, column=1, sticky="ew", **pad)

        ttk.Label(self, text="Date (YYYY-MM-DD)").grid(row=3, column=0, sticky="w", **pad)
        self.date_entry = ttk.Entry(self)
        self.date_entry.insert(0, date.today().isoformat())
        self.date_entry.grid(row=3, column=1, sticky="ew", **pad)

        ttk.Button(self, text="Add Lesson", command=self.add_lesson).grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Button(self, text="Bulk Mark Selected as Paid", command=self.bulk_mark_paid).grid(row=5, column=0, columnspan=2, sticky="ew", **pad)

        columns = ("id", "date", "type", "amount", "paid")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for col, w in [("id", 80), ("date", 140), ("type", 220), ("amount", 120), ("paid", 100)]:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=w, anchor="center")
        self.tree.grid(row=6, column=0, columnspan=2, sticky="nsew", **pad)

        self.tree.tag_configure("paid", background="#DCFCE7")
        self.tree.tag_configure("unpaid", background="#FEE2E2")

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Mark Paid", command=lambda: self.mark_selection(True))
        self.menu.add_command(label="Mark Unpaid", command=lambda: self.mark_selection(False))
        self.menu.add_separator()
        self.menu.add_command(label="Delete Lesson", command=self.delete_selected)
        self.tree.bind("<Button-3>", self._show_menu)

        self.total_var = tk.StringVar(value="Total: $0.00 | Paid: $0.00 | Outstanding: $0.00")
        ttk.Label(self, textvariable=self.total_var, font=("Segoe UI", 10, "bold")).grid(row=7, column=0, columnspan=2, sticky="e", **pad)

    def set_lesson_types(self, lesson_types):
        self.lesson_types = lesson_types
        self.lesson_type_combo["values"] = [row["name"] for row in lesson_types]

    def set_selected_skater(self, skater):
        self.skater = skater
        self.skater_label.config(text="(none)" if not skater else f"{skater['name']} ({skater['email']})")
        self.refresh_tree()

    def _fill_amount(self, _event=None):
        selected_name = self.lesson_type_var.get()
        rate = next((row["rate"] for row in self.lesson_types if row["name"] == selected_name), None)
        if rate is not None:
            self.amount_entry.delete(0, tk.END)
            self.amount_entry.insert(0, f"{float(rate):.2f}")

    def add_lesson(self):
        if not getattr(self, "skater", None):
            messagebox.showinfo("Skater required", "Select a skater first.")
            return
        lesson_type = next((row for row in self.lesson_types if row["name"] == self.lesson_type_var.get()), None)
        if not lesson_type:
            messagebox.showerror("Lesson type", "Choose a lesson type.")
            return
        try:
            amount = float(self.amount_entry.get())
            self.app.db.execute(
                "INSERT INTO lessons(skater_id, date, amount, lesson_type_id, paid) VALUES (?, ?, ?, ?, 0)",
                (self.skater["id"], self.date_entry.get(), amount, lesson_type["id"]),
            )
            self.refresh_tree()
            self.app.refresh_finance()
        except Exception as exc:
            self.app.show_error("Failed to add lesson", exc)

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not getattr(self, "skater", None):
            self.total_var.set("Total: $0.00 | Paid: $0.00 | Outstanding: $0.00")
            return

        rows = self.app.db.fetchall(
            """
            SELECT l.id, l.date, lt.name AS lesson_type, l.amount, l.paid
            FROM lessons l JOIN lesson_types lt ON lt.id = l.lesson_type_id
            WHERE l.skater_id=? ORDER BY l.date DESC
            """,
            (self.skater["id"],),
        )
        total = paid = 0.0
        for row in rows:
            amount = float(row["amount"])
            total += amount
            if row["paid"]:
                paid += amount
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(row["id"], row["date"], row["lesson_type"], f"${amount:.2f}", "Yes" if row["paid"] else "No"),
                tags=("paid" if row["paid"] else "unpaid",),
            )
        self.total_var.set(f"Total: ${total:.2f} | Paid: ${paid:.2f} | Outstanding: ${total-paid:.2f}")

    def _show_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.menu.tk_popup(event.x_root, event.y_root)

    def mark_selection(self, paid: bool):
        ids = [int(item) for item in self.tree.selection()]
        self.app.finance_service.mark_lessons_paid(ids, paid=paid)
        self.refresh_tree()
        self.app.refresh_finance()

    def bulk_mark_paid(self):
        ids = [int(item) for item in self.tree.selection()]
        if not ids:
            messagebox.showinfo("Selection", "Select one or more lessons first.")
            return
        self.mark_selection(True)

    def delete_selected(self):
        ids = [int(item) for item in self.tree.selection()]
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self.app.db.execute(f"DELETE FROM lessons WHERE id IN ({placeholders})", ids)
        self.refresh_tree()
        self.app.refresh_finance()
