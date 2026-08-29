from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.config import load_yaml_config
from app.core.profiles import get_profile, resolve_profile_key
from app.models.enums import RemoteType
from app.services.normalizer import NormalizedJob

EUR_CONVERSION_RATES = {
    "EUR": 1.0,
    "USD": 0.8785,
    "GBP": 1.1673,
    "PLN": 0.2331,
    "CZK": 0.0413,
    "SEK": 0.0910,
    "DKK": 0.1338,
    "NOK": 0.0850,
    "CHF": 1.0750,
    "ILS": 0.2650,
    "RSD": 0.0085,
    "HUF": 0.0028,
}


@dataclass(frozen=True)
class ScoreResult:
    score: int
    level: str
    positive: list[str]
    negative: list[str]


class ScoringEngine:
    def __init__(self, profile_key: str | None = None) -> None:
        self.profile_key = resolve_profile_key(profile_key)
        profile = get_profile(self.profile_key)
        self.profile_config = load_yaml_config(profile.profile_config)
        self.scoring_config = load_yaml_config(profile.scoring_config)
        self.salary_config = self.profile_config.get("profile", {}).get("salary", {})
        self.messages = self.scoring_config.get("messages", {})
        if not isinstance(self.messages, dict):
            self.messages = {}

    def score(self, job: NormalizedJob) -> ScoreResult:
        positive: list[str] = []
        negative: list[str] = []
        score = 0
        role_score = self._role_fit(job, positive)
        technology_score = self._technology_score(job, positive)
        score += role_score
        score += technology_score
        score += self._salary_score(job, positive, negative)
        score += self._experience_score(job, positive, negative)
        score += self._location_score(job, positive, negative)
        score += self._career_growth_score(job, positive)
        score += self._disability_focus_score(job, positive)
        score += self._penalties(job, role_score, technology_score, negative)
        score = max(0, min(100, score))
        return ScoreResult(
            score=score, level=self._level(score), positive=positive, negative=negative
        )

    def _role_fit(self, job: NormalizedJob, positive: list[str]) -> int:
        text = _job_text(job)
        role_config = self.scoring_config.get("role_keywords", {})
        strong = (
            _string_list(role_config.get("strong", [])) if isinstance(role_config, dict) else []
        )
        security_focus = (
            _string_list(role_config.get("security_focus", []))
            if isinstance(role_config, dict)
            else []
        )
        direct_fit = (
            _string_list(role_config.get("direct_fit", []))
            if isinstance(role_config, dict)
            else []
        )
        matches = [keyword for keyword in strong if _keyword_in_text(keyword, text)]
        direct_matches = [keyword for keyword in direct_fit if _keyword_in_text(keyword, text)]
        if direct_matches:
            positive.append(self._message("role_direct_fit", "El puesto encaja con el perfil"))
            return 25
        if {"java", "backend"}.issubset(set(matches)) or "spring" in matches:
            positive.append(
                self._message("role_java_spring", "El puesto encaja con backend Java/Spring")
            )
            return 25
        if "java" in matches and any(
            _keyword_in_text(keyword, text)
            for keyword in ("devops", "cloud", "platform", "aws", "ci/cd")
        ):
            positive.append(
                self._message(
                    "role_java_cloud",
                    "El puesto combina Java con cloud, DevOps o platform",
                )
            )
            return 22
        if any(_keyword_in_text(keyword, text) for keyword in security_focus):
            positive.append(
                self._message(
                    "role_security",
                    "El puesto encaja con AppSec, DevSecOps o seguridad cloud",
                )
            )
            return 22
        if matches:
            positive.append(
                self._message(
                    "role_signal",
                    "El puesto contiene senales de backend o desarrollo de APIs",
                )
            )
            return min(20, 8 + len(matches) * 4)
        return 0

    def _technology_score(self, job: NormalizedJob, positive: list[str]) -> int:
        if not job.technologies:
            return 0
        technologies_config = self.scoring_config.get("technologies", {})
        high = set(_mapping_keys(technologies_config, "high"))
        medium = set(_mapping_keys(technologies_config, "medium"))
        secondary = set(_mapping_keys(technologies_config, "secondary"))
        raw_score = 0
        for technology in job.technologies:
            if technology in high:
                raw_score += 4
            elif technology in medium:
                raw_score += 2
            elif technology in secondary:
                raw_score += 1
        score = min(30, raw_score)
        positive.append(f"Tecnologias relevantes detectadas: {', '.join(job.technologies[:8])}")
        return score

    def _salary_score(
        self,
        job: NormalizedJob,
        positive: list[str],
        negative: list[str],
    ) -> int:
        minimum = int(self.salary_config.get("minimum_annual_eur", 21000))
        target_min = int(self.salary_config.get("target_min_annual_eur", 27000))
        target_max = int(self.salary_config.get("target_max_annual_eur", 35000))
        if job.salary_unknown or job.salary_min is None:
            positive.append("No publica salario; se conserva como salario desconocido")
            return 8
        salary_min_eur, salary_max_eur = _salary_bounds_eur(job)
        if salary_min_eur is None:
            positive.append("Publica salario en moneda no comparable; no se penaliza")
            return 8
        if salary_max_eur is not None and salary_max_eur < minimum:
            negative.append(f"Salario explicito por debajo de {minimum} EUR")
            return 0
        if target_min <= salary_min_eur <= target_max:
            positive.append("Salario dentro del rango objetivo")
            return 20
        if salary_min_eur >= minimum:
            positive.append("Salario por encima del minimo aceptable")
            return 15
        negative.append(f"Salario explicito por debajo de {minimum} EUR")
        return 0

    def _experience_score(
        self,
        job: NormalizedJob,
        positive: list[str],
        negative: list[str],
    ) -> int:
        exp = job.experience_max_years or job.experience_min_years
        if exp is None:
            return 7
        if exp <= 1:
            positive.append("Experiencia requerida compatible con perfil junior")
            return 10
        if exp <= 3:
            negative.append(f"Solicita {exp:g} anos de experiencia")
            return 8
        if exp <= 5:
            negative.append(f"Solicita {exp:g} anos de experiencia")
            return 4
        negative.append(f"Solicita mas de 5 anos de experiencia ({exp:g})")
        return 0

    def _location_score(
        self,
        job: NormalizedJob,
        positive: list[str],
        negative: list[str],
    ) -> int:
        location = f"{job.location or ''} {job.country or ''}".lower()
        if self._matches_preferred_local_location(location):
            positive.append(
                self._message(
                    "location_preferred",
                    "Ubicacion compatible con preferencias del perfil",
                )
            )
            return 10
        if job.remote_type == RemoteType.REMOTE and ("spain" in location or "espana" in location):
            positive.append("Permite trabajo remoto desde Espana")
            return 10
        if job.remote_type == RemoteType.REMOTE and "europe" in location:
            positive.append("Permite remoto europeo potencialmente compatible")
            return 8
        if job.remote_type == RemoteType.REMOTE and job.language == "en":
            positive.append("Oferta remota en ingles potencialmente compatible")
            return 7
        if job.remote_type == RemoteType.REMOTE:
            positive.append("Permite trabajo remoto")
            return 6
        if "sevilla" in location and job.remote_type in {RemoteType.HYBRID, RemoteType.ONSITE}:
            positive.append("Ubicacion compatible en Sevilla")
            return 8
        if job.remote_type == RemoteType.HYBRID and any(
            city in location for city in ("madrid", "malaga", "barcelona")
        ):
            positive.append("Modalidad hibrida en ciudad espanola razonable")
            return 7
        if job.remote_type == RemoteType.UNKNOWN:
            return 4
        negative.append("Ubicacion o modalidad poco alineada")
        return 0

    def _career_growth_score(self, job: NormalizedJob, positive: list[str]) -> int:
        text = _job_text(job)
        role_config = self.scoring_config.get("role_keywords", {})
        growth = (
            _string_list(role_config.get("growth", [])) if isinstance(role_config, dict) else []
        )
        matches = [keyword for keyword in growth if _keyword_in_text(keyword, text)]
        if not matches:
            return 0
        positive.append(
            self._message(
                "career_growth",
                "Alinea con evolucion hacia cloud, DevOps, platform o AppSec",
            )
        )
        return min(5, len(matches) * 2)

    def _disability_focus_score(self, job: NormalizedJob, positive: list[str]) -> int:
        text = _job_text(job)
        role_config = self.scoring_config.get("role_keywords", {})
        disability_focus = (
            _string_list(role_config.get("disability_focus", []))
            if isinstance(role_config, dict)
            else []
        )
        if not disability_focus:
            return 0
        if not any(_keyword_in_text(keyword, text) for keyword in disability_focus):
            return 0
        positive.append(
            self._message(
                "disability_focus",
                "Oferta dirigida a personas con certificado de discapacidad",
            )
        )
        return 3

    def _penalties(
        self,
        job: NormalizedJob,
        role_score: int,
        technology_score: int,
        negative: list[str],
    ) -> int:
        penalties = self.scoring_config.get("penalties", {})
        if not isinstance(penalties, dict):
            return 0
        text = _job_text(job)
        total = 0
        total += self._missing_technical_fit_penalty(
            penalties, role_score, technology_score, negative
        )
        total += self._missing_primary_stack_penalty(text, penalties, negative)
        total += self._salary_penalty(job, penalties, negative)
        title_text = f"{job.title} {job.normalized_title}".lower()
        total += self._keyword_penalty(
            title_text,
            penalties,
            "senior",
            self._message("senior", "Puesto senior; se conserva pero queda penalizado"),
            negative,
        )
        total += self._keyword_penalty(
            title_text,
            penalties,
            "senior_leadership",
            self._message("senior_leadership", "Puesto lead, staff, principal o manager"),
            negative,
        )
        total += self._experience_penalty(job, penalties, negative)
        total += self._keyword_penalty(
            title_text,
            penalties,
            "helpdesk",
            self._message("helpdesk", "Puesto de helpdesk, soporte basico o microinformatica"),
            negative,
        )
        total += self._keyword_penalty(
            title_text,
            penalties,
            "non_developer_role",
            self._message(
                "non_developer_role",
                "Rol no alineado con desarrollo backend o full-stack",
            ),
            negative,
        )
        total += self._keyword_penalty(
            text,
            penalties,
            "unsupported_language",
            self._message(
                "unsupported_language",
                "Requiere un idioma no compatible con el perfil",
            ),
            negative,
        )
        total += self._pure_role_penalty(
            text,
            penalties,
            "frontend_pure",
            self._message("frontend_pure", "Frontend puro sin backend claro"),
            negative,
        )
        total += self._pure_role_penalty(
            text,
            penalties,
            "mobile_pure",
            self._message("mobile_pure", "Mobile puro sin backend o cloud claro"),
            negative,
        )
        total += self._keyword_penalty(
            text,
            penalties,
            "soc_l1",
            self._message("soc_l1", "SOC L1 puramente operativo"),
            negative,
        )
        total += self._pentesting_penalty(text, penalties, negative)
        return total

    def _missing_technical_fit_penalty(
        self,
        penalties: dict[str, Any],
        role_score: int,
        technology_score: int,
        negative: list[str],
    ) -> int:
        if role_score > 0 or technology_score > 0:
            return 0
        config = penalties.get("missing_technical_fit", {})
        negative.append(
            self._message(
                "missing_technical_fit",
                "No hay senales claras de backend, desarrollo o cloud",
            )
        )
        return int(config.get("points", -35)) if isinstance(config, dict) else -35

    def _missing_primary_stack_penalty(
        self,
        text: str,
        penalties: dict[str, Any],
        negative: list[str],
    ) -> int:
        config = penalties.get("missing_primary_stack", {})
        if not isinstance(config, dict):
            return 0
        required_keywords = _string_list(config.get("required_keywords", []))
        exception_keywords = _string_list(config.get("exception_keywords", []))
        if any(_keyword_in_text(keyword, text) for keyword in required_keywords):
            return 0
        if any(_keyword_in_text(keyword, text) for keyword in exception_keywords):
            return 0
        negative.append(
            self._message(
                "missing_primary_stack",
                "No contiene Java, Spring, JVM o un foco AppSec claro",
            )
        )
        return int(config.get("points", -35))

    def _salary_penalty(
        self,
        job: NormalizedJob,
        penalties: dict[str, Any],
        negative: list[str],
    ) -> int:
        minimum = int(self.salary_config.get("minimum_annual_eur", 21000))
        if job.salary_unknown or job.salary_min is None:
            return 0
        _, salary_max_eur = _salary_bounds_eur(job)
        if salary_max_eur is not None and salary_max_eur < minimum:
            negative.append("Penalizacion fuerte por salario inferior al minimo")
            config = penalties.get("low_salary", {})
            return int(config.get("points", -50)) if isinstance(config, dict) else -50
        return 0

    def _experience_penalty(
        self,
        job: NormalizedJob,
        penalties: dict[str, Any],
        negative: list[str],
    ) -> int:
        config = penalties.get("too_much_experience", {})
        if not isinstance(config, dict):
            return 0
        threshold = float(config.get("threshold_years", 5))
        exp = job.experience_max_years or job.experience_min_years
        if exp is not None and exp > threshold:
            negative.append("Penalizacion por experiencia obligatoria demasiado alta")
            return int(config.get("points", -30))
        return 0

    def _keyword_penalty(
        self,
        text: str,
        penalties: dict[str, Any],
        key: str,
        reason: str,
        negative: list[str],
    ) -> int:
        config = penalties.get(key, {})
        if not isinstance(config, dict):
            return 0
        keywords = _string_list(config.get("keywords", []))
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in keywords):
            negative.append(reason)
            return int(config.get("points", 0))
        return 0

    def _pure_role_penalty(
        self,
        text: str,
        penalties: dict[str, Any],
        key: str,
        reason: str,
        negative: list[str],
    ) -> int:
        if any(
            _keyword_in_text(token, text)
            for token in ("backend", "java", "spring", "api", "cloud", "aws")
        ):
            return 0
        return self._keyword_penalty(text, penalties, key, reason, negative)

    def _pentesting_penalty(self, text: str, penalties: dict[str, Any], negative: list[str]) -> int:
        if any(
            _keyword_in_text(token, text)
            for token in (
                "appsec",
                "application security",
                "product security",
                "devsecops",
                "cloud security",
                "cloud",
                "aws",
                "secure development",
            )
        ):
            return 0
        return self._keyword_penalty(
            text,
            penalties,
            "pentesting_pure",
            self._message(
                "pentesting_pure",
                "Pentesting puro sin AppSec, cloud o desarrollo seguro",
            ),
            negative,
        )

    def _level(self, score: int) -> str:
        levels = self.scoring_config.get("match_levels", {})
        if not isinstance(levels, dict):
            return "low"
        if score >= int(levels.get("excellent", 80)):
            return "excellent"
        if score >= int(levels.get("good", 65)):
            return "good"
        if score >= int(levels.get("possible", 50)):
            return "possible"
        return "low"

    def _matches_preferred_local_location(self, location: str) -> bool:
        profile = self.profile_config.get("profile", {})
        if not isinstance(profile, dict):
            return False
        location_config = profile.get("location", {})
        if not isinstance(location_config, dict):
            return False
        preferred_locations = _string_list(location_config.get("preferred_locations", []))
        broad_terms = {"spain", "espana", "espa\u00f1a", "europe", "european union"}
        for preferred_location in preferred_locations:
            term = preferred_location.lower()
            if term in broad_terms:
                continue
            if term and term in location:
                return True
        return False

    def _message(self, key: str, default: str) -> str:
        value = self.messages.get(key)
        return str(value) if value else default


def _job_text(job: NormalizedJob) -> str:
    return " ".join(
        part.lower()
        for part in (
            job.title,
            job.normalized_title,
            job.description,
            job.requirements or "",
            job.location or "",
            " ".join(job.technologies),
        )
        if part
    )


def _mapping_keys(config: object, group: str) -> list[str]:
    if not isinstance(config, dict):
        return []
    entries = config.get(group, {})
    if not isinstance(entries, dict):
        return []
    return [str(key) for key in entries]


def _salary_bounds_eur(job: NormalizedJob) -> tuple[int | None, int | None]:
    if job.salary_unknown or job.salary_min is None:
        return None, None
    currency = (job.salary_currency or "EUR").upper()
    rate = EUR_CONVERSION_RATES.get(currency)
    if rate is None:
        return None, None
    salary_min = int(round(job.salary_min * rate))
    salary_max = int(round(job.salary_max * rate)) if job.salary_max is not None else None
    return salary_min, salary_max


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _keyword_in_text(keyword: str, text: str) -> bool:
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    if normalized == "api":
        return re.search(r"(?<!\w)apis?(?!\w)", text, re.IGNORECASE) is not None
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE) is not None
