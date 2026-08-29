from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SalaryExtraction:
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    period: str | None
    original_text: str | None
    unknown: bool


SALARY_NUMBER = r"\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s?k?"
CURRENCY_PATTERN = (
    r"(?:\b(?:eur|euro|euros|usd|dollars?|gbp|pounds?|pln|czk|sek|dkk|nok|"
    r"chf|ils|rsd|huf)\b|"
    r"us\$|\$|\u20ac|\u00a3|z\u0142|k\u010d|kc)"
)
RANGE_RE = re.compile(
    rf"(?P<prefix>{CURRENCY_PATTERN})?\s*"
    rf"(?P<min>{SALARY_NUMBER})\s*(?P<suffix1>{CURRENCY_PATTERN})?\s*"
    rf"(?:-|\u2013|\u2014|to|a|hasta)\s*"
    rf"(?P<prefix2>{CURRENCY_PATTERN})?\s*(?P<max>{SALARY_NUMBER})\s*"
    rf"(?P<suffix>{CURRENCY_PATTERN})?",
    re.IGNORECASE,
)
SINGLE_RE = re.compile(
    rf"(?P<prefix>{CURRENCY_PATTERN})?\s*(?P<amount>{SALARY_NUMBER})\s*"
    rf"(?P<suffix>{CURRENCY_PATTERN})?",
    re.IGNORECASE,
)


def extract_salary(text: str) -> SalaryExtraction:
    normalized = text.replace("\xa0", " ")
    for match in RANGE_RE.finditer(normalized):
        original = match.group(0)
        if not _looks_like_salary(normalized, match.start(), match.end(), original):
            continue
        salary_min = _parse_amount(match.group("min"))
        salary_max = _parse_amount(match.group("max"))
        if salary_min is None or salary_max is None:
            continue
        salary_min, salary_max = _harmonize_range_suffixes(
            salary_min,
            salary_max,
            match.group("min"),
            match.group("max"),
        )
        period = _period_from_context(normalized, match.start(), match.end())
        currency = _currency_from_text(original) or _currency_from_text(
            _salary_context(normalized, match.start(), match.end())
        )
        if not _amounts_are_plausible(
            salary_min,
            salary_max,
            period,
            currency,
            f"{match.group('min')} {match.group('max')}",
        ):
            continue
        return _build_salary(
            min(salary_min, salary_max),
            max(salary_min, salary_max),
            period,
            original,
            currency,
        )

    for match in SINGLE_RE.finditer(normalized):
        original = match.group(0)
        if not _looks_like_salary(normalized, match.start(), match.end(), original):
            continue
        amount = _parse_amount(match.group("amount"))
        if amount is None:
            continue
        period = _period_from_context(normalized, match.start(), match.end())
        currency = _currency_from_text(original) or _currency_from_text(
            _salary_context(normalized, match.start(), match.end())
        )
        if not _amounts_are_plausible(amount, amount, period, currency, original):
            continue
        return _build_salary(amount, amount, period, original, currency)

    return SalaryExtraction(None, None, None, None, None, True)


def _build_salary(
    amount_min: int, amount_max: int, period: str, original: str, currency: str | None
) -> SalaryExtraction:
    annual_min = _to_annual(amount_min, period)
    annual_max = _to_annual(amount_max, period)
    return SalaryExtraction(
        salary_min=annual_min,
        salary_max=annual_max,
        currency=currency or "EUR",
        period=period,
        original_text=" ".join(original.split()),
        unknown=False,
    )


def _looks_like_salary(text: str, start: int, end: int, matched: str) -> bool:
    if _looks_like_identifier_or_percentage_fragment(text, start, end, matched):
        return False
    context = _salary_context(text, start, end).lower()
    matched_lower = matched.lower()
    has_currency = bool(re.search(CURRENCY_PATTERN, matched_lower, re.IGNORECASE))
    has_currency_context = bool(re.search(CURRENCY_PATTERN, context, re.IGNORECASE))
    has_salary_word = any(
        word in context
        for word in (
            "salary",
            "salario",
            "remuneration",
            "compensation",
            "gross",
            "bruto",
            "brutos",
        )
    )
    return has_currency or has_currency_context or has_salary_word


def _looks_like_identifier_or_percentage_fragment(
    text: str, start: int, end: int, matched: str
) -> bool:
    trimmed_start = start + len(matched) - len(matched.lstrip())
    trimmed_end = start + len(matched.rstrip())
    previous_character = text[trimmed_start - 1] if trimmed_start > 0 else ""
    next_character = text[trimmed_end] if trimmed_end < len(text) else ""
    if next_character.lower() == "k":
        return False
    if previous_character.isalpha() or next_character.isalpha():
        return True
    return next_character == "%"


def _currency_from_text(text: str) -> str | None:
    lower = text.lower()
    if re.search(r"(?:\busd\b|us\$|\bdollars?\b|\$)", lower):
        return "USD"
    if re.search(r"(?:\bgbp\b|\bpounds?\b|\u00a3)", lower):
        return "GBP"
    if re.search(r"(?:\bpln\b|z\u0142)", lower):
        return "PLN"
    if re.search(r"(?:\bczk\b|k\u010d|kc)", lower):
        return "CZK"
    if re.search(r"\bsek\b", lower):
        return "SEK"
    if re.search(r"\bdkk\b", lower):
        return "DKK"
    if re.search(r"\bnok\b", lower):
        return "NOK"
    if re.search(r"\bchf\b", lower):
        return "CHF"
    if re.search(r"\bils\b", lower):
        return "ILS"
    if re.search(r"\brsd\b", lower):
        return "RSD"
    if re.search(r"\bhuf\b", lower):
        return "HUF"
    if re.search(r"(?:\beur\b|\beuro\b|\beuros\b|\u20ac)", lower):
        return "EUR"
    return None


def _parse_amount(raw: str) -> int | None:
    text = raw.strip().lower().replace(" ", "")
    has_k_suffix = text.endswith("k")
    text = text.removesuffix("k")
    cleaned = re.sub(r"[^\d,.]", "", text)
    if not cleaned:
        return None
    if "." in cleaned and "," in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        cleaned = _normalize_single_separator(cleaned, ".")
    elif "," in cleaned:
        cleaned = _normalize_single_separator(cleaned, ",")
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    if has_k_suffix and amount < 1000:
        amount *= 1000
    return int(round(amount))


def _harmonize_range_suffixes(
    salary_min: int, salary_max: int, raw_min: str, raw_max: str
) -> tuple[int, int]:
    min_has_k = raw_min.strip().lower().endswith("k")
    max_has_k = raw_max.strip().lower().endswith("k")
    if max_has_k and not min_has_k and salary_min < 1000 <= salary_max:
        salary_min *= 1000
    if min_has_k and not max_has_k and salary_max < 1000 <= salary_min:
        salary_max *= 1000
    return salary_min, salary_max


def _normalize_single_separator(value: str, separator: str) -> str:
    parts = value.split(separator)
    if len(parts[-1]) == 3 and len(parts) > 1:
        return "".join(parts)
    return value.replace(separator, ".")


def _salary_context(text: str, start: int, end: int) -> str:
    return text[max(0, start - 80) : min(len(text), end + 80)]


def _amounts_are_plausible(
    amount_min: int,
    amount_max: int,
    period: str,
    currency: str | None,
    raw: str,
) -> bool:
    values = (amount_min, amount_max)
    if all(1900 <= value <= 2100 for value in values):
        return False
    minimum_by_period = {
        "hourly": 8,
        "daily": 50,
        "monthly": 500,
        "annual": 10000,
    }
    minimum = minimum_by_period.get(period, 10000)
    if max(values) < minimum and "k" not in raw.lower():
        return False
    if "k" in raw.lower():
        return True
    return currency is not None or max(values) >= minimum


def _period_from_context(text: str, start: int, end: int) -> str:
    context = _salary_context(text, start, end).lower()
    if re.search(r"\bmonths?\b|\bmonthly\b|/mes\b|\bmes\b|\bmensual\b", context):
        return "monthly"
    if re.search(r"\bhours?\b|\bhourly\b|(?<![a-z0-9])/h(?:\b|$)|/hora\b|\bhora\b", context):
        return "hourly"
    if re.search(r"\bdays?\b|\bdaily\b|/dia\b|/day\b|\bdia\b", context):
        return "daily"
    return "annual"


def _to_annual(amount: int, period: str) -> int:
    if period == "monthly":
        return amount * 12
    if period == "daily":
        return amount * 220
    if period == "hourly":
        return amount * 2080
    return amount
