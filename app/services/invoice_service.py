import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.database import Database


class InvoiceService:
    def __init__(self, db: Database, invoice_dir: str = "invoices") -> None:
        self.db = db
        self.invoice_dir = Path(invoice_dir)
        self.invoice_dir.mkdir(exist_ok=True)

    def lessons_for_month(self, skater_id: int, year: int, month: int):
        return self.db.fetchall(
            """
            SELECT l.id, l.date, l.amount, l.paid, lt.name AS lesson_type
            FROM lessons l
            JOIN lesson_types lt ON lt.id = l.lesson_type_id
            WHERE l.skater_id=?
              AND strftime('%Y', l.date)=?
              AND strftime('%m', l.date)=?
            ORDER BY l.date
            """,
            (skater_id, str(year), f"{month:02d}"),
        )

    def create_invoice(
        self,
        skater: dict,
        from_name: str,
        from_email: str,
        year: int,
        month: int,
        mark_paid: bool = False,
    ) -> Path:
        lessons = self.lessons_for_month(skater["id"], year, month)
        total = sum(float(row["amount"]) for row in lessons)
        filename = self._sanitize_filename(f"{skater['name']}_{year}_{month:02d}.pdf")
        out_path = self.invoice_dir / filename

        c = canvas.Canvas(str(out_path), pagesize=A4)
        w, h = A4
        margin = 20 * mm

        c.setFillColor(colors.HexColor("#1E3A8A"))
        c.rect(0, h - 40 * mm, w, 40 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(margin, h - 24 * mm, "INVOICE")

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 11)
        c.drawString(margin, h - 50 * mm, f"From: {from_name}")
        c.drawString(margin, h - 56 * mm, from_email)
        c.drawString(margin, h - 66 * mm, f"To: {skater['name']} ({skater['email']})")
        c.drawString(margin, h - 76 * mm, f"Billing month: {datetime(year, month, 1):%B %Y}")

        y = h - 90 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, y, "Date")
        c.drawString(margin + 45 * mm, y, "Lesson Type")
        c.drawRightString(w - margin - 25 * mm, y, "Paid")
        c.drawRightString(w - margin, y, "Amount")
        y -= 4
        c.line(margin, y, w - margin, y)
        y -= 6

        c.setFont("Helvetica", 10)
        for row in lessons:
            if y < 30 * mm:
                c.showPage()
                y = h - margin
            date_str = datetime.fromisoformat(row["date"]).strftime("%Y-%m-%d")
            c.drawString(margin, y, date_str)
            c.drawString(margin + 45 * mm, y, row["lesson_type"])
            c.drawRightString(w - margin - 25 * mm, y, "Yes" if row["paid"] else "No")
            c.drawRightString(w - margin, y, f"${float(row['amount']):.2f}")
            y -= 6 * mm

        c.line(margin, y + 2, w - margin, y + 2)
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(w - margin, y - 5 * mm, f"Total: ${total:.2f}")
        c.save()

        if mark_paid and lessons:
            placeholders = ",".join("?" for _ in lessons)
            self.db.execute(
                f"UPDATE lessons SET paid=1 WHERE id IN ({placeholders})",
                [row["id"] for row in lessons],
            )

        return out_path

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
