import pytest

from app.database import Database
from app.services.finance_service import FinanceService


def test_finance_summary_and_breakdown(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init_schema()
    db.execute("INSERT INTO skaters(name, email) VALUES('A', 'a@x.com')")
    db.execute("INSERT INTO lesson_types(name, rate) VALUES('Private', 40)")
    db.execute("INSERT INTO lessons(skater_id, date, amount, lesson_type_id, paid) VALUES(1, '2026-01-01', 40, 1, 1)")
    db.execute("INSERT INTO lessons(skater_id, date, amount, lesson_type_id, paid) VALUES(1, '2026-01-02', 30, 1, 0)")

    service = FinanceService(db)
    summary = service.dashboard_summary()
    assert summary.expected == 70
    assert summary.collected == 40
    assert summary.outstanding == 30

    breakdown = service.monthly_breakdown()
    assert breakdown[0]["month"] == "2026-01"
    db.close()


def test_admin_verification(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init_schema()
    assert db.verify_admin("admin", "admin123")
    assert not db.verify_admin("admin", "bad")
    db.close()


def test_filename_sanitization(tmp_path):
    reportlab = pytest.importorskip("reportlab")
    assert reportlab  # silence lint
    from app.services.invoice_service import InvoiceService

    db = Database(str(tmp_path / "test.db"))
    db.init_schema()
    invoice_service = InvoiceService(db, invoice_dir=str(tmp_path / "invoices"))
    assert invoice_service._sanitize_filename("Jane Doe:2026/01.pdf") == "Jane_Doe_2026_01.pdf"
    db.close()
