# Skating Invoicer

Skating Invoicer is a desktop application for managing skating lessons, skaters, invoices, and payments. It includes a **built-in auto-updater** that checks for the latest version hosted on GitHub.

---

## Features

- Add, edit, and manage skaters
- Add lessons with date, type, and amount
- Generate PDF invoices for any month
- Track paid/unpaid skaters
- Finance manager: see expected and collected revenue
- Auto-updater: checks GitHub for new versions and downloads updates
- Admin panel for administrative tasks

---

## Installation

### 1. Requirements

- Windows 10 or 11
- Python 3.9+ (if running from source)
- Libraries:
  - `tkinter`
  - `sqlite3` (built-in)
  - `reportlab`
  - `urllib` (built-in)
  
Install `reportlab` if needed:

```bash
pip install reportlab
