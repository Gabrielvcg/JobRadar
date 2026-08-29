from __future__ import annotations

from app.formatting import experience_label, salary_label, salary_original_detail


def test_salary_label_uses_grouped_numbers() -> None:
    label = salary_label(110000, 130000, "USD", False)

    assert label == "110,000-130,000 USD"


def test_salary_original_detail_skips_duplicate_range() -> None:
    label = salary_label(110000, 130000, "USD", False)

    assert salary_original_detail(label, "110000-130000 USD") is None


def test_salary_original_detail_skips_equivalent_period_context() -> None:
    label = salary_label(25000, 33000, "EUR", False)

    assert salary_original_detail(label, "25000-33000 EUR annual") is None


def test_salary_original_detail_skips_equivalent_dotted_k_range() -> None:
    label = salary_label(25000, 33000, "EUR", False)

    assert salary_original_detail(label, "25.000K - 33.000") is None


def test_salary_original_detail_skips_equivalent_mixed_k_range() -> None:
    label = salary_label(30000, 35000, "EUR", False)

    assert salary_original_detail(label, "30 - 35k") is None


def test_experience_label_highlights_required_years() -> None:
    assert experience_label(3, 5) == "3-5 years"
    assert experience_label(4, 4) == "4+ years"
    assert experience_label(None, None) == "not specified"
