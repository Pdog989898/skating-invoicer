import tkinter as tk
from tkinter import ttk


class FinanceTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        pad = {"padx": 8, "pady": 6}
        top = ttk.LabelFrame(self, text="Finance Dashboard")
        top.pack(fill="x", padx=8, pady=8)

        self.expected_var = tk.StringVar(value="$0.00")
        self.collected_var = tk.StringVar(value="$0.00")
        self.outstanding_var = tk.StringVar(value="$0.00")

        ttk.Label(top, text="Expected Revenue").grid(row=0, column=0, **pad)
        ttk.Label(top, textvariable=self.expected_var, font=("Segoe UI", 11, "bold")).grid(row=0, column=1, **pad)
        ttk.Label(top, text="Collected Revenue").grid(row=1, column=0, **pad)
        ttk.Label(top, textvariable=self.collected_var, font=("Segoe UI", 11, "bold")).grid(row=1, column=1, **pad)
        ttk.Label(top, text="Outstanding Revenue").grid(row=2, column=0, **pad)
        ttk.Label(top, textvariable=self.outstanding_var, font=("Segoe UI", 11, "bold")).grid(row=2, column=1, **pad)

        breakdown = ttk.LabelFrame(self, text="Monthly Breakdown")
        breakdown.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("month", "expected", "collected", "outstanding")
        self.breakdown_tree = ttk.Treeview(breakdown, columns=cols, show="headings")
        for col in cols:
            self.breakdown_tree.heading(col, text=col.title())
            self.breakdown_tree.column(col, anchor="center")
        self.breakdown_tree.pack(fill="both", expand=True)

    def refresh(self):
        summary = self.app.finance_service.dashboard_summary()
        self.expected_var.set(f"${summary.expected:.2f}")
        self.collected_var.set(f"${summary.collected:.2f}")
        self.outstanding_var.set(f"${summary.outstanding:.2f}")

        for item in self.breakdown_tree.get_children():
            self.breakdown_tree.delete(item)
        for row in self.app.finance_service.monthly_breakdown():
            self.breakdown_tree.insert(
                "",
                "end",
                values=(row["month"], f"${row['expected']:.2f}", f"${row['collected']:.2f}", f"${row['outstanding']:.2f}"),
            )
