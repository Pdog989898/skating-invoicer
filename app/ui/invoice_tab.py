import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk


class InvoiceTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        pad = {"padx": 8, "pady": 6}
        self.columnconfigure(1, weight=1)

        self.from_name = tk.StringVar(value="Helene Carle")
        self.from_email = tk.StringVar(value="skatersis2001@gmail.com")
        self.month = tk.StringVar(value=str(date.today().month))
        self.year = tk.StringVar(value=str(date.today().year))
        self.mark_paid = tk.IntVar(value=0)

        ttk.Label(self, text="From Name").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.from_name).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(self, text="From Email").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.from_email).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Label(self, text="Month (1-12)").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.month).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Label(self, text="Year (YYYY)").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.year).grid(row=3, column=1, sticky="ew", **pad)
        ttk.Checkbutton(self, text="Mark lessons as paid after invoice", variable=self.mark_paid).grid(
            row=4, column=0, columnspan=2, sticky="w", **pad
        )
        ttk.Button(self, text="Generate Monthly Invoice", command=self.generate).grid(
            row=5, column=0, columnspan=2, sticky="ew", **pad
        )

    def generate(self):
        if not self.app.selected_skater:
            messagebox.showinfo("Skater required", "Select a skater first.")
            return
        try:
            month = int(self.month.get())
            year = int(self.year.get())
            output = self.app.invoice_service.create_invoice(
                skater=self.app.selected_skater,
                from_name=self.from_name.get(),
                from_email=self.from_email.get(),
                year=year,
                month=month,
                mark_paid=bool(self.mark_paid.get()),
            )
            self.app.lessons_tab.refresh_tree()
            self.app.refresh_finance()
            messagebox.showinfo("Invoice generated", f"Saved to {output}")
        except Exception as exc:
            self.app.show_error("Invoice generation failed", exc)
