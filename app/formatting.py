from __future__ import annotations

import re

from app.scoring.salary import extract_salary


def salary_label(
    salary_min: int | None,
    salary_max: int | None,
    currency: str | None,
    salary_unknown: bool,
) -> str:
    if salary_unknown or salary_min is None:
        return "unknown"
    currency_label = currency or "EUR"
    if salary_max and salary_max != salary_min:
        return f"{_money(salary_min)}-{_money(salary_max)} {currency_label}"
    return f"{_money(salary_min)} {currency_label}"


def salary_original_detail(label: str, original_text: str | None) -> str | None:
    if not original_text:
        return None
    original = " ".join(original_text.split())
    if not original:
        return None
    if _comparable_salary_text(label) == _comparable_salary_text(original):
        return None
    extracted = extract_salary(original)
    if extracted.unknown and "k" in original.lower():
        extracted = extract_salary(f"Salary {original}")
    if not extracted.unknown:
        parsed_label = salary_label(
            extracted.salary_min,
            extracted.salary_max,
            extracted.currency,
            extracted.unknown,
        )
        if _comparable_salary_text(label) == _comparable_salary_text(parsed_label):
            return None
    return original


def experience_label(
    experience_min_years: float | None,
    experience_max_years: float | None,
) -> str:
    if experience_min_years is None and experience_max_years is None:
        return "not specified"
    if experience_min_years is not None and experience_max_years is not None:
        if experience_min_years != experience_max_years:
            return (
                f"{_years(experience_min_years)}-{_years(experience_max_years)} years"
            )
        return f"{_years(experience_min_years)}+ years"
    years = experience_min_years if experience_min_years is not None else experience_max_years
    return f"{_years(years)} years"


def _money(value: int) -> str:
    return f"{value:,}"


def _years(value: float | None) -> str:
    if value is None:
        return "unknown"
    years = float(value)
    if years.is_integer():
        return str(int(years))
    return f"{years:g}"


def _comparable_salary_text(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("us$", "usd").replace("$", "usd")
    normalized = normalized.replace("€", "eur").replace("£", "gbp")
    return re.sub(r"[^a-z0-9]", "", normalized)
