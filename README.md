# Skating Invoicer Pro

Commercial-grade Tkinter desktop invoicing software for skating coaches.

## Project structure

```
/app
  main.py
  database.py
  /ui
    lessons_tab.py
    finance_tab.py
    invoice_tab.py
  /services
    invoice_service.py
    finance_service.py
    update_service.py
```

## Features

- Persistent SQLite connection with startup schema migrations.
- Automatic database backup on startup (`/backups`).
- Lesson-level payment tracking (`lessons.paid`).
- Modern lessons grid with `ttk.Treeview`, paid/unpaid color states, bulk paid actions.
- Finance dashboard: expected, collected, outstanding, and monthly breakdown.
- Monthly invoice generation with professional PDF layout.
- Option to mark invoiced lessons as paid.
- Filename sanitization for generated invoices.
- Secure admin login using salted password hashes in DB (no hard-coded password).
- Updater checks local `version.txt` against remote `version.json` and prompts download.
- Logging to `skating_invoicer.log`.
- Graceful error dialogs for failures.

## Run

```bash
python skating_invoicer.py
```

## Tests

```bash
python -m pytest -q
```

## Packaging (PyInstaller)

```bash
pyinstaller --onefile --noconsole skating_invoicer.py
```
