from __future__ import annotations

from dataclasses import dataclass

from app.database import Database


@dataclass
class FinanceSummary:
    expected: float
    collected: float
    outstanding: float


class FinanceService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def dashboard_summary(self) -> FinanceSummary:
        expected = self._scalar("SELECT COALESCE(SUM(amount), 0) FROM lessons")
        collected = self._scalar("SELECT COALESCE(SUM(amount), 0) FROM lessons WHERE paid=1")
        return FinanceSummary(expected=expected, collected=collected, outstanding=expected - collected)

    def monthly_breakdown(self):
        rows = self.db.fetchall(
            """
            SELECT substr(date, 1, 7) AS month,
                   COALESCE(SUM(amount), 0) AS expected,
                   COALESCE(SUM(CASE WHEN paid=1 THEN amount ELSE 0 END), 0) AS collected
            FROM lessons
            GROUP BY substr(date, 1, 7)
            ORDER BY month DESC
            """
        )
        return [
            {
                "month": row["month"],
                "expected": row["expected"],
                "collected": row["collected"],
                "outstanding": row["expected"] - row["collected"],
            }
            for row in rows
        ]

    def mark_lessons_paid(self, lesson_ids: list[int], paid: bool = True) -> None:
        if not lesson_ids:
            return
        placeholders = ",".join("?" for _ in lesson_ids)
        self.db.execute(
            f"UPDATE lessons SET paid=? WHERE id IN ({placeholders})",
            [1 if paid else 0, *lesson_ids],
        )

    def _scalar(self, query: str) -> float:
        row = self.db.fetchone(query)
        return float(row[0] if row else 0.0)
