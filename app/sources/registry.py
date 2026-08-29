from __future__ import annotations

from typing import Any

from app.core.config import get_settings, load_yaml_config
from app.core.profiles import get_profile, resolve_profile_key
from app.sources.adzuna import AdzunaJobSource
from app.sources.arbeitnow import ArbeitnowJobSource
from app.sources.ats import (
    AshbyJobSource,
    GreenhouseJobSource,
    LeverJobSource,
    PersonioJobSource,
    PinpointJobSource,
    RecruiteeJobSource,
    WorkableJobSource,
)
from app.sources.base import JobSourceAdapter, SearchConfig
from app.sources.bizneo import BizneoJobSource
from app.sources.domestiko import DomestikoJobSource
from app.sources.eurofirms import EurofirmsJobSource
from app.sources.fixture import FixtureJobSource
from app.sources.fundacion_adecco import FundacionAdeccoJobSource
from app.sources.fundacion_randstad import FundacionRandstadJobSource
from app.sources.himalayas import HimalayasJobSource
from app.sources.infoempleo import InfoempleoJobSource
from app.sources.jobicy import JobicyJobSource
from app.sources.jobtoday import JobTodayJobSource
from app.sources.manpower import ManpowerJobSource
from app.sources.pagepersonnel import PagePersonnelJobSource
from app.sources.portalento import PortalentoJobSource
from app.sources.remoteok import RemoteOkJobSource
from app.sources.remotive import RemotiveJobSource
from app.sources.rss import RssJobSource
from app.sources.talent import TalentJobSource
from app.sources.tecnoempleo import TecnoempleoJobSource
from app.sources.trabajos import TrabajosJobSource


def load_search_config(profile_key: str | None = None) -> SearchConfig:
    profile = get_profile(profile_key)
    config = load_yaml_config(profile.searches_config)
    locations = config.get("locations", {})
    if not isinstance(locations, dict):
        locations = {}
    return SearchConfig(
        queries=_string_list(config.get("queries", [])),
        countries=_string_list(locations.get("countries", [])),
        cities=_string_list(locations.get("cities", [])),
        remote_from=_string_list(locations.get("remote_from", [])),
        languages=_string_list(config.get("languages", [])),
    )


def build_enabled_sources() -> list[JobSourceAdapter]:
    sources_config = load_yaml_config("sources.yml").get("sources", {})
    if not isinstance(sources_config, dict):
        msg = "sources.yml must contain a sources mapping"
        raise ValueError(msg)

    adapters: list[JobSourceAdapter] = []
    for name, raw_settings in sources_config.items():
        if not isinstance(raw_settings, dict) or not _is_source_enabled(raw_settings):
            continue
        adapter_name = raw_settings.get("adapter", name)
        adapter: JobSourceAdapter
        if adapter_name == "fixtures":
            adapter = FixtureJobSource(raw_settings)
        elif adapter_name == "fundacion_adecco":
            adapter = FundacionAdeccoJobSource(raw_settings)
        elif adapter_name == "fundacion_randstad":
            adapter = FundacionRandstadJobSource(raw_settings)
        elif adapter_name == "portalento":
            adapter = PortalentoJobSource(raw_settings)
        elif adapter_name == "tecnoempleo":
            adapter = TecnoempleoJobSource(raw_settings)
        elif adapter_name == "arbeitnow":
            adapter = ArbeitnowJobSource(raw_settings)
        elif adapter_name == "remotive":
            adapter = RemotiveJobSource(raw_settings)
        elif adapter_name == "remoteok":
            adapter = RemoteOkJobSource(raw_settings)
        elif adapter_name == "rss":
            adapter = RssJobSource(name, raw_settings)
        elif adapter_name == "jobicy":
            adapter = JobicyJobSource(raw_settings)
        elif adapter_name == "himalayas":
            adapter = HimalayasJobSource(raw_settings)
        elif adapter_name == "greenhouse":
            adapter = GreenhouseJobSource(raw_settings)
        elif adapter_name == "lever":
            adapter = LeverJobSource(raw_settings)
        elif adapter_name == "ashby":
            adapter = AshbyJobSource(raw_settings)
        elif adapter_name == "workable":
            adapter = WorkableJobSource(raw_settings)
        elif adapter_name == "recruitee":
            adapter = RecruiteeJobSource(raw_settings)
        elif adapter_name == "pinpoint":
            adapter = PinpointJobSource(raw_settings)
        elif adapter_name == "personio":
            adapter = PersonioJobSource(raw_settings)
        elif adapter_name == "adzuna":
            adapter = AdzunaJobSource(raw_settings)
        elif adapter_name == "infoempleo":
            adapter = InfoempleoJobSource(raw_settings)
        elif adapter_name == "jobtoday":
            adapter = JobTodayJobSource(raw_settings)
        elif adapter_name == "bizneo":
            adapter = BizneoJobSource(raw_settings)
        elif adapter_name == "talent":
            adapter = TalentJobSource(raw_settings)
        elif adapter_name == "manpower":
            adapter = ManpowerJobSource(raw_settings)
        elif adapter_name == "pagepersonnel":
            adapter = PagePersonnelJobSource(raw_settings)
        elif adapter_name == "eurofirms":
            adapter = EurofirmsJobSource(raw_settings)
        elif adapter_name == "domestiko":
            adapter = DomestikoJobSource(raw_settings)
        elif adapter_name == "trabajos":
            adapter = TrabajosJobSource(raw_settings)
        else:
            continue
        _attach_source_identity(adapter, name, raw_settings)
        adapters.append(adapter)
    return adapters


def configured_sources() -> dict[str, dict[str, Any]]:
    sources = load_yaml_config("sources.yml").get("sources", {})
    if not isinstance(sources, dict):
        return {}
    return {
        str(name): _effective_source_settings(settings)
        for name, settings in sources.items()
        if isinstance(settings, dict)
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _is_source_enabled(settings: dict[str, Any]) -> bool:
    if not bool(settings.get("enabled", False)):
        return False
    return not (
        get_settings().app_env == "production" and settings.get("production_enabled") is False
    )


def _effective_source_settings(settings: dict[str, Any]) -> dict[str, Any]:
    effective = dict(settings)
    effective["enabled"] = _is_source_enabled(settings)
    effective["profile_key"] = resolve_profile_key(_optional_str(settings.get("profile_key")))
    return effective


def _attach_source_identity(
    adapter: JobSourceAdapter, name: str, settings: dict[str, Any]
) -> None:
    adapter.name = name
    adapter.profile_key = resolve_profile_key(_optional_str(settings.get("profile_key")))  # type: ignore[attr-defined]


def source_profile_key(adapter: JobSourceAdapter) -> str:
    return resolve_profile_key(_optional_str(getattr(adapter, "profile_key", None)))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
