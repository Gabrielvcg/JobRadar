from __future__ import annotations

from app.scoring.salary import extract_salary


def test_ignores_reference_identifier_near_salary_word() -> None:
    salary = extract_salary(
        "Salario competitivo en funcion de la experiencia. "
        "Referencia: 2863140c-3ca2-9ade-8a24-6629bdc202f2."
    )

    assert salary.unknown is True


def test_ignores_disability_percentage_near_salary_word() -> None:
    salary = extract_salary(
        "Salario segun experiencia. Certificado de discapacidad igual o superior al 33%."
    )

    assert salary.unknown is True


def test_extracts_annual_salary_range() -> None:
    salary = extract_salary("Salary 30,000-34,000 EUR gross per year")

    assert salary.unknown is False
    assert salary.salary_min == 30000
    assert salary.salary_max == 34000
    assert salary.currency == "EUR"
    assert salary.period == "annual"


def test_extracts_monthly_salary_as_annual() -> None:
    salary = extract_salary("Salario 2.500 EUR/mes")

    assert salary.unknown is False
    assert salary.salary_min == 30000
    assert salary.salary_max == 30000
    assert salary.period == "monthly"


def test_extracts_hourly_salary_as_annual() -> None:
    salary = extract_salary("Compensation 25 EUR/hour")

    assert salary.unknown is False
    assert salary.salary_min == 52000
    assert salary.period == "hourly"


def test_salary_unknown_when_not_explicit() -> None:
    salary = extract_salary("Competitive package and flexible benefits")

    assert salary.unknown is True
    assert salary.salary_min is None


def test_extracts_usd_salary_range() -> None:
    salary = extract_salary("Salary $30k - $100k")

    assert salary.unknown is False
    assert salary.salary_min == 30000
    assert salary.salary_max == 100000
    assert salary.currency == "USD"


def test_extracts_pln_monthly_range_with_currency_between_numbers() -> None:
    salary = extract_salary("The monthly base salary for this role is 21,000 PLN to 24,750 PLN.")

    assert salary.unknown is False
    assert salary.salary_min == 252000
    assert salary.salary_max == 297000
    assert salary.currency == "PLN"
    assert salary.period == "monthly"


def test_extracts_pln_annual_range() -> None:
    salary = extract_salary("The salary range is 222000 to 334000 PLN annually.")

    assert salary.unknown is False
    assert salary.salary_min == 222000
    assert salary.salary_max == 334000
    assert salary.currency == "PLN"
    assert salary.period == "annual"


def test_extracts_czk_annual_symbol_range() -> None:
    salary = extract_salary("Kc1,435,600 - Kc1,635,600 / year")

    assert salary.unknown is False
    assert salary.salary_min == 1435600
    assert salary.salary_max == 1635600
    assert salary.currency == "CZK"
    assert salary.period == "annual"


def test_extracts_sek_range_from_context_currency() -> None:
    salary = extract_salary("Base compensation range for this role is SEK 775,444 - SEK 930,533.")

    assert salary.unknown is False
    assert salary.salary_min == 775444
    assert salary.salary_max == 930533
    assert salary.currency == "SEK"


def test_ignores_benefit_day_count_near_salary_word() -> None:
    salary = extract_salary(
        "Strong base salary. Flexible work location. Spend up to 30 days per year working "
        "remotely."
    )

    assert salary.unknown is True


def test_ignores_year_near_paid_compensation_text() -> None:
    salary = extract_salary("Duration: 3 months. Start date: June-August 2026. Compensation: Paid.")

    assert salary.unknown is True


def test_ignores_k_suffix_when_not_salary_context() -> None:
    salary = extract_salary("We run 25k builds a day and store 100 TB of artifacts.")

    assert salary.unknown is True


def test_ignores_funding_amount_as_salary() -> None:
    salary = extract_salary("In March 2026, we closed a $25M Series A led by investors.")

    assert salary.unknown is True


def test_ignores_small_monthly_allowance_near_salary_word() -> None:
    salary = extract_salary("Competitive salary, equity and EUR 60/month phone allowance.")

    assert salary.unknown is True


def test_extracts_dotted_k_salary_without_millions() -> None:
    salary = extract_salary("Salario 25.000K - 33.000 EUR")

    assert salary.unknown is False
    assert salary.salary_min == 25000
    assert salary.salary_max == 33000


def test_does_not_treat_url_path_as_hourly_salary_period() -> None:
    salary = extract_salary("Salario: 25.000K - 33.000K. https://himalayas.app/jobs/example")

    assert salary.unknown is False
    assert salary.salary_min == 25000
    assert salary.salary_max == 33000
    assert salary.period == "annual"


def test_extracts_mixed_k_range_suffix() -> None:
    salary = extract_salary("Salary 30 - 35k EUR")

    assert salary.unknown is False
    assert salary.salary_min == 30000
    assert salary.salary_max == 35000


def test_does_not_extract_europe_as_euro_salary() -> None:
    salary = extract_salary("Remote within Europe, Switzerland, B2B Contract")

    assert salary.unknown is True


def test_does_not_extract_location_postcode_as_salary_range() -> None:
    salary = extract_salary("Kraków, 30-347, Poland")

    assert salary.unknown is True
