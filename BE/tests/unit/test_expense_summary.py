from BE.app.services.expenses import build_summary


def test_summary_thresholds_and_categories():
    expenses = [
        {"amount_vnd": 1200000, "category": "food"},
        {"amount_vnd": 1300000, "category": "transport"},
    ]

    summary = build_summary(3000000, expenses)

    assert summary == {
        "budget_vnd": 3000000,
        "spent_vnd": 2500000,
        "remaining_vnd": 500000,
        "by_category": {
            "food": 1200000,
            "ticket": 0,
            "transport": 1300000,
            "other": 0,
        },
        "alert": "80",
    }


def test_summary_allows_zero_budget_and_negative_remaining():
    summary = build_summary(0, [{"amount_vnd": 10, "category": "other"}])
    assert summary["remaining_vnd"] == -10
    assert summary["alert"] == "100"
