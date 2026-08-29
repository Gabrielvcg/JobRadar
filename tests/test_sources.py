from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from app.models.enums import RemoteType
from app.services.ingestion import _matches_search_scope
from app.services.normalizer import NormalizedJob
from app.sources.adzuna import AdzunaJobSource
from app.sources.adzuna import _matches_affinity as adzuna_matches_affinity
from app.sources.ats import (
    AshbyJobSource,
    CompanySetting,
    GreenhouseJobSource,
    LeverJobSource,
    PersonioJobSource,
    PinpointJobSource,
    RecruiteeJobSource,
    WorkableJobSource,
    _dedupe_job_variants,
)
from app.sources.ats import _matches_affinity as ats_matches_affinity
from app.sources.base import RawJob, SearchConfig
from app.sources.bizneo import BizneoJobSource, BizneoPage
from app.sources.bizneo import _matches_affinity as bizneo_matches_affinity
from app.sources.domestiko import DomestikoJobSource
from app.sources.domestiko import _job_posting as domestiko_job_posting
from app.sources.domestiko import _matches_affinity as domestiko_matches_affinity
from app.sources.domestiko import _raw_job_from_posting as domestiko_raw_job_from_posting
from app.sources.eurofirms import EurofirmsJobSource, EurofirmsPage
from app.sources.eurofirms import _matches_affinity as eurofirms_matches_affinity
from app.sources.fundacion_adecco import FundacionAdeccoJobSource, FundacionAdeccoPage
from app.sources.fundacion_adecco import (
    _enriched_from_detail as fundacion_adecco_enriched_from_detail,
)
from app.sources.fundacion_adecco import (
    _matches_affinity as fundacion_adecco_matches_affinity,
)
from app.sources.fundacion_randstad import FundacionRandstadJobSource
from app.sources.himalayas import HimalayasJobSource
from app.sources.himalayas import _matches_affinity as himalayas_matches_affinity
from app.sources.infoempleo import InfoempleoJobSource, InfoempleoPage
from app.sources.infoempleo import _matches_affinity as infoempleo_matches_affinity
from app.sources.jobicy import JobicyJobSource
from app.sources.jobicy import _matches_affinity as jobicy_matches_affinity
from app.sources.jobtoday import JobTodayJobSource, JobTodayPage
from app.sources.jobtoday import _matches_affinity as jobtoday_matches_affinity
from app.sources.manpower import ManpowerJobSource, ManpowerPage
from app.sources.manpower import _matches_affinity as manpower_matches_affinity
from app.sources.pagepersonnel import PagePersonnelJobSource, PagePersonnelPage
from app.sources.pagepersonnel import _matches_affinity as pagepersonnel_matches_affinity
from app.sources.portalento import PortalentoJobSource
from app.sources.portalento import _matches_affinity as portalento_matches_affinity
from app.sources.remoteok import RemoteOkJobSource
from app.sources.remoteok import _matches_affinity as remoteok_matches_affinity
from app.sources.remotive import RemotiveJobSource, _matches_affinity
from app.sources.rss import RssJobSource, _rss_items
from app.sources.rss import _matches_affinity as rss_matches_affinity
from app.sources.talent import TalentJobSource, TalentPage, _enriched_from_detail
from app.sources.talent import _matches_affinity as talent_matches_affinity
from app.sources.tecnoempleo import TecnoempleoJobSource, TecnoempleoPage
from app.sources.tecnoempleo import (
    _enriched_from_detail as tecnoempleo_enriched_from_detail,
)
from app.sources.tecnoempleo import _matches_affinity as tecnoempleo_matches_affinity
from app.sources.trabajos import TrabajosJobSource, TrabajosPage
from app.sources.trabajos import _matches_affinity as trabajos_matches_affinity


def test_remotive_maps_remote_job_with_salary() -> None:
    source = RemotiveJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": 123,
            "company_name": "Example",
            "title": "Junior Java Backend Engineer",
            "description": "Build Spring APIs",
            "tags": ["Java", "Spring", "REST"],
            "job_type": "full_time",
            "candidate_required_location": "Europe",
            "salary": "$30k - $45k",
            "url": "https://remotive.com/remote-jobs/software-dev/example-123",
            "publication_date": "2026-06-27T10:00:00",
        }
    )

    assert raw.source_name == "remotive"
    assert raw.source_job_id == "123"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.salary_original_text == "$30k - $45k"
    assert raw.requirements == "Java, Spring, REST"


def test_remotive_affinity_filter_excludes_senior_product_roles() -> None:
    source = RemotiveJobSource(
        {
            "required_any_keywords": ["java", "spring", "backend"],
            "title_required_any_keywords": ["java", "backend", "engineer"],
            "excluded_keywords": ["senior", "product manager"],
        }
    )

    jobs = [
        source._to_raw_job(
            {
                "id": 1,
                "company_name": "Example",
                "title": "Junior Java Backend Engineer",
                "description": "Spring APIs",
            }
        ),
        source._to_raw_job(
            {
                "id": 2,
                "company_name": "Example",
                "title": "Senior Product Manager",
                "description": "Java platform roadmap",
            }
        ),
    ]

    filtered = [
        job
        for job in jobs
        if _matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_remoteok_maps_remote_job_with_usd_salary() -> None:
    source = RemoteOkJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": "1135000",
            "company": "Example",
            "position": "Junior Java Backend Engineer",
            "description": "Build Spring APIs",
            "tags": ["java", "spring", "api"],
            "location": "Worldwide",
            "salary_min": 30000,
            "salary_max": 45000,
            "url": "https://remoteok.com/remote-jobs/example",
            "date": "2026-06-27T10:00:00+00:00",
        }
    )

    assert raw.source_name == "remoteok"
    assert raw.source_job_id == "1135000"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.salary_original_text == "$30000 - $45000"
    assert raw.requirements == "java, spring, api"


def test_remoteok_affinity_filter_excludes_unrealistic_roles() -> None:
    source = RemoteOkJobSource(
        {
            "required_any_keywords": ["java", "spring", "backend"],
            "title_required_any_keywords": ["java", "backend", "engineer"],
            "excluded_keywords": ["senior", "staff", "manager"],
            "allowed_location_keywords": ["worldwide", "europe"],
        }
    )

    jobs = [
        source._to_raw_job(
            {
                "id": "1",
                "company": "Example",
                "position": "Junior Java Backend Engineer",
                "description": "Spring APIs",
                "location": "Worldwide",
            }
        ),
        source._to_raw_job(
            {
                "id": "2",
                "company": "Example",
                "position": "Senior Backend Software Developer",
                "description": "Java platform",
                "location": "Worldwide",
            }
        ),
        source._to_raw_job(
            {
                "id": "3",
                "company": "Example",
                "position": "Backend Engineer",
                "description": "Spring APIs",
                "location": "USA",
            }
        ),
    ]

    filtered = [
        job
        for job in jobs
        if remoteok_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_rss_source_maps_weworkremotely_item() -> None:
    source = RssJobSource("weworkremotely", {"enabled": True})

    item = _rss_items(
        """
        <rss version="2.0">
          <channel>
            <item>
              <title>Example Co: Full-Stack Java Engineer</title>
              <region>LATAM or Europe</region>
              <country>Spain</country>
              <skills>Java, Spring Boot, AWS</skills>
              <category>Programming</category>
              <description><![CDATA[Build Spring APIs with React and AWS.]]></description>
              <link>https://weworkremotely.com/remote-jobs/example</link>
              <guid>wwr-123</guid>
              <pubDate>Sat, 27 Jun 2026 10:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """
    )[0]

    raw = source._to_raw_job(item)

    assert raw.source_name == "weworkremotely"
    assert raw.source_job_id == "wwr-123"
    assert raw.company_name == "Example Co"
    assert raw.title == "Full-Stack Java Engineer"
    assert raw.location == "LATAM or Europe, Spain"
    assert raw.country == "Europe"
    assert raw.requirements == "Programming, Java, Spring Boot, AWS, LATAM or Europe, Spain"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.publication_date is not None


def test_rss_affinity_filter_keeps_remote_engineers_and_excludes_managers() -> None:
    source = RssJobSource(
        "weworkremotely",
        {
            "required_any_keywords": ["java", "spring", "backend"],
            "title_required_any_keywords": ["engineer", "developer"],
            "excluded_keywords": ["manager", "business development"],
            "allowed_location_keywords": ["europe", "world"],
        },
    )

    jobs = [
        source._to_raw_job(
            _rss_items(
                """
                <rss version="2.0"><channel><item>
                  <title>Example: Backend Java Engineer</title>
                  <region>Europe</region>
                  <category>Programming</category>
                  <description>Spring APIs</description>
                  <guid>1</guid>
                </item></channel></rss>
                """
            )[0]
        ),
        source._to_raw_job(
            _rss_items(
                """
                <rss version="2.0"><channel><item>
                  <title>Example: Manager Business Development</title>
                  <region>Anywhere in the World</region>
                  <category>Programming</category>
                  <description>Java platform partnerships</description>
                  <guid>2</guid>
                </item></channel></rss>
                """
            )[0]
        ),
    ]

    filtered = [
        job
        for job in jobs
        if rss_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_rss_must_have_java_does_not_match_javascript() -> None:
    source = RssJobSource(
        "weworkremotely",
        {
            "must_have_any_keywords": ["java", "spring"],
            "required_any_keywords": ["developer", "software"],
            "title_required_any_keywords": ["developer", "engineer"],
            "allowed_location_keywords": ["world"],
        },
    )
    job = source._to_raw_job(
        _rss_items(
            """
            <rss version="2.0"><channel><item>
              <title>Example: Software Developer in Test (JavaScript)</title>
              <region>Anywhere in the World</region>
              <category>Programming</category>
              <description>Build browser automation.</description>
              <skills>JavaScript, Testing</skills>
              <guid>1</guid>
            </item></channel></rss>
            """
        )[0]
    )

    assert (
        rss_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
            source.must_have_any_keywords,
        )
        is False
    )


def test_jobicy_maps_remote_job_with_salary_and_level() -> None:
    source = JobicyJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": 144087,
            "companyName": "Veeam Software",
            "jobTitle": "Software Developer in Test (JavaScript)",
            "jobDescription": "Build CI/CD pipelines and cloud automation.",
            "jobIndustry": ["Programming"],
            "jobType": ["Full-Time"],
            "jobGeo": "Poland",
            "jobLevel": "Midweight",
            "url": "https://jobicy.com/jobs/example",
            "pubDate": "2026-06-26T19:51:41+00:00",
            "salaryMin": 30000,
            "salaryMax": 45000,
            "salaryCurrency": "EUR",
            "salaryPeriod": "yearly",
        }
    )

    assert raw.source_name == "jobicy"
    assert raw.source_job_id == "144087"
    assert raw.company_name == "Veeam Software"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.location == "Poland"
    assert raw.requirements == "Programming, Full-Time, Midweight"
    assert raw.salary_original_text == "30000-45000 EUR yearly"
    assert raw.publication_date is not None


def test_jobicy_affinity_filter_excludes_senior_level_roles() -> None:
    source = JobicyJobSource(
        {
            "required_any_keywords": ["developer", "backend", "cloud"],
            "title_required_any_keywords": ["developer", "engineer"],
            "excluded_keywords": ["senior", "principal", "lead", "manager"],
            "allowed_location_keywords": ["poland", "europe"],
        }
    )

    jobs = [
        source._to_raw_job(
            {
                "id": 1,
                "companyName": "Example",
                "jobTitle": "Software Developer in Test",
                "jobDescription": "Build CI/CD automation for a leading cloud product.",
                "jobIndustry": ["Programming"],
                "jobType": ["Full-Time"],
                "jobGeo": "Poland",
                "jobLevel": "Midweight",
            }
        ),
        source._to_raw_job(
            {
                "id": 2,
                "companyName": "Example",
                "jobTitle": "Backend Engineer",
                "jobDescription": "Build cloud APIs.",
                "jobIndustry": ["Software Engineering"],
                "jobType": ["Full-Time"],
                "jobGeo": "Europe",
                "jobLevel": "Senior",
            }
        ),
    ]

    filtered = [
        job
        for job in jobs
        if jobicy_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_himalayas_maps_junior_java_offer_with_salary() -> None:
    source = HimalayasJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "guid": "https://himalayas.app/companies/irium/jobs/desarrollador-a-java-junior",
            "companyName": "IRIUM",
            "title": "DESARROLLADOR/A JAVA JUNIOR (REMOTO)",
            "description": "Java Junior con microservicios, Spring Boot en AWS.",
            "categories": ["Java-Development", "Backend-Development", "Cloud-Computing"],
            "seniority": ["Entry-level"],
            "employmentType": "Full Time",
            "locationRestrictions": ["Spain"],
            "minSalary": 25000,
            "maxSalary": 33000,
            "currency": "EUR",
            "salaryPeriod": "annual",
            "pubDate": 1782707713,
            "expiryDate": 1787891713,
            "applicationLink": "https://himalayas.app/companies/irium/jobs/desarrollador-a-java-junior",
        }
    )

    assert raw.source_name == "himalayas"
    assert raw.source_job_id == "https://himalayas.app/companies/irium/jobs/desarrollador-a-java-junior"
    assert raw.company_name == "IRIUM"
    assert raw.location == "Spain"
    assert raw.country == "Spain"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.salary_original_text == "25000-33000 EUR annual"
    assert raw.publication_date is not None
    assert raw.expiration_date is not None


def test_himalayas_affinity_filter_requires_java_and_rejects_trainers() -> None:
    source = HimalayasJobSource(
        {
            "must_have_any_keywords": ["java", "spring", "kotlin"],
            "required_any_keywords": ["java", "spring", "backend"],
            "title_required_any_keywords": ["java", "backend", "developer"],
            "excluded_keywords": ["teacher", "trainer"],
            "allowed_location_keywords": ["spain", "worldwide"],
        }
    )
    jobs = [
        source._to_raw_job(
            {
                "guid": "1",
                "companyName": "Example",
                "title": "Backend Java Developer",
                "description": "Spring Boot APIs",
                "locationRestrictions": ["Spain"],
            }
        ),
        source._to_raw_job(
            {
                "guid": "2",
                "companyName": "Example",
                "title": "Kotlin Coding Specialist - AI Trainer",
                "description": "Review Kotlin exercises",
                "locationRestrictions": [],
            }
        ),
    ]

    filtered = [
        job
        for job in jobs
        if himalayas_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
            source.must_have_any_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_himalayas_summarizes_long_european_country() -> None:
    source = HimalayasJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "guid": "1",
            "companyName": "Example",
            "title": "Senior Java Developer",
            "description": "Spring Boot APIs",
            "locationRestrictions": [
                "Austria",
                "Belgium",
                "Bulgaria",
                "Croatia",
                "Cyprus",
                "Czechia",
                "Denmark",
                "Estonia",
                "Finland",
                "France",
                "Germany",
                "Greece",
                "Hungary",
                "Ireland",
                "Italy",
                "Latvia",
                "Lithuania",
                "Luxembourg",
                "Netherlands",
                "Poland",
                "Portugal",
                "Romania",
                "Slovakia",
                "Slovenia",
                "Spain",
                "Sweden",
            ],
        }
    )

    assert raw.country == "Europe"
    assert raw.location is not None
    assert len(raw.location) <= 500


def test_fundacion_adecco_maps_disability_it_listing_and_detail() -> None:
    source = FundacionAdeccoJobSource({"enabled": True})
    jobs = source._jobs_from_listing(
        """
        <html>
          <body>
            <div class="search-result-card">
              <div class="search-result-job-title">
                <a href="https://empleo.fundacionadecco.org/oferta-empleo/desarrollador-a-java_3PQ8E"
                   data-id="2863140c-3ca2-9ade-8a24-6629bdc202f2">
                  <h3>Desarrollador/a Java 100% remoto con discapacidad en Madrid</h3>
                </a>
              </div>
              <div class="search-result-job-details">
                <div>Madrid</div><div>Publicada: 19/05/2026</div>
              </div>
              <div class="search-result-bottom-details-text">Tiempo completo</div>
              <div class="search-result-bottom-details-text">Indefinido</div>
              <div class="search-result-bottom-details-text">Salario según experiencia</div>
              <div class="search-result-disability-certificate-label">
                Personas con certificado de discapacidad
              </div>
            </div>
          </body>
        </html>
        """,
        FundacionAdeccoPage(
            "https://empleo.fundacionadecco.org/ofertas-empleo-discapacidad/informatica-sistemas",
            "Spain",
            "Spain",
        ),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "fundacion_adecco"
    assert raw.source_job_id == "2863140c-3ca2-9ade-8a24-6629bdc202f2"
    assert raw.title == "Desarrollador/a Java 100% remoto con discapacidad"
    assert raw.location == "Madrid"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.employment_type == "full_time"
    assert raw.salary_original_text == "Salario según experiencia"
    assert raw.publication_date is not None


def test_fundacion_adecco_detail_salary_text_is_bounded() -> None:
    raw = RawJob(
        source_name="fundacion_adecco",
        source_job_id="java",
        company_name="Fundación Adecco",
        title="Desarrollador/a Java 100% remoto con discapacidad",
        description="Java Spring Boot.",
        requirements="Certificado de discapacidad.",
        location="Madrid",
        country="Spain",
        url="https://empleo.fundacionadecco.org/oferta-empleo/desarrollador-a-java_3PQ8E",
    )

    enriched = fundacion_adecco_enriched_from_detail(
        raw,
        """
        <html><body>
          <h1>Desarrollador/a Java 100% remoto con discapacidad en Madrid</h1>
          <div class="job-info-paragraph"><p>Java Spring Boot y AWS.</p></div>
          <div class="job-info-paragraph"><p>Certificado de discapacidad.</p></div>
          <div class="job-info-paragraph">
            <p>100% trabajo en remoto. Puesto estable. Proyecto de carrera.
            Salario competitivo en función de la experiencia.
            Amplio paquete de beneficios sociales y otras condiciones.</p>
          </div>
        </body></html>
        """,
    )

    assert enriched.salary_original_text == "Salario competitivo"
    assert len(enriched.salary_original_text) < 300


def test_fundacion_adecco_affinity_keeps_java_and_rejects_support() -> None:
    source = FundacionAdeccoJobSource(
        {
            "required_any_keywords": ["java", "spring", "backend", "aws"],
            "title_required_any_keywords": ["java", "backend", "engineer"],
            "excluded_keywords": ["soporte informatico", "helpdesk", "data engineer"],
            "allowed_location_keywords": ["spain", "madrid"],
        }
    )
    jobs = [
        RawJob(
            source_name="fundacion_adecco",
            source_job_id="java",
            company_name="Fundación Adecco",
            title="Desarrollador/a Java 100% remoto con discapacidad",
            description="Java Spring Boot REST APIs y AWS.",
            requirements="Certificado de discapacidad.",
            location="Madrid",
            country="Spain",
        ),
        RawJob(
            source_name="fundacion_adecco",
            source_job_id="support",
            company_name="Fundación Adecco",
            title="Técnico/a de Soporte Informático N 1 con discapacidad",
            description="Soporte informático a usuarios.",
            requirements="Certificado de discapacidad.",
            location="Valencia",
            country="Spain",
        ),
        RawJob(
            source_name="fundacion_adecco",
            source_job_id="data",
            company_name="Fundación Adecco",
            title="Data Engineer con discapacidad",
            description="AWS, Kafka y Kubernetes.",
            requirements="Certificado de discapacidad.",
            location="Madrid",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if fundacion_adecco_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["java"]


def test_greenhouse_maps_curated_company_job() -> None:
    source = GreenhouseJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": 8503792002,
            "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/8503792002",
            "company_name": "GitLab",
            "title": "Backend Engineer, Java Platform",
            "content": "<p>Build Java services with Spring Boot and Kubernetes.</p>",
            "location": {"name": "Remote, Spain"},
            "first_published": "2026-04-17T05:58:03-04:00",
            "departments": [{"name": "Engineering"}],
        },
        source.companies[0] if source.companies else CompanySetting("gitlab", "GitLab"),
    )

    assert raw.source_name == "greenhouse_curated"
    assert raw.source_job_id == "gitlab:8503792002"
    assert raw.company_name == "GitLab"
    assert raw.location == "Remote, Spain"
    assert raw.country == "Spain"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.publication_date is not None


def test_lever_maps_curated_company_job() -> None:
    source = LeverJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": "abc",
            "hostedUrl": "https://jobs.lever.co/watchguard/abc",
            "text": "Java Backend Developer",
            "descriptionPlain": "Build Spring Boot APIs.",
            "additionalPlain": "Cloud-native services on AWS.",
            "categories": {
                "commitment": "Full-time: Remote",
                "department": "Engineering",
                "team": "Platform",
                "allLocations": ["Spain", "Remote - Europe"],
            },
            "createdAt": 1782698147772,
        },
        source.companies[0] if source.companies else CompanySetting("watchguard", "WatchGuard"),
    )

    assert raw.source_name == "lever_curated"
    assert raw.source_job_id == "watchguard:abc"
    assert raw.company_name == "WatchGuard"
    assert raw.location == "Spain, Remote - Europe"
    assert raw.country == "Spain"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.publication_date is not None


def test_ashby_maps_curated_company_job() -> None:
    source = AshbyJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "title": "Product Engineer (Backend)",
            "location": "Remote (Europe)",
            "isRemote": True,
            "workplaceType": "Remote",
            "descriptionPlain": "Build backend services with Kotlin or Java.",
            "department": "Engineering",
            "team": "Product",
            "employmentType": "FullTime",
            "publishedAt": "2026-06-30T12:00:00+00:00",
            "jobUrl": "https://jobs.ashbyhq.com/flip/example",
            "compensation": {
                "scrapeableCompensationSalarySummary": "EUR 50000 - 70000"
            },
        },
        CompanySetting("flip", "Flip"),
    )

    assert raw.source_name == "ashby_curated"
    assert raw.source_job_id == "flip:https://jobs.ashbyhq.com/flip/example"
    assert raw.company_name == "Flip"
    assert raw.location == "Remote (Europe)"
    assert raw.country == "Europe"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.salary_original_text == "EUR 50000 - 70000"
    assert raw.publication_date is not None


def test_workable_maps_and_deduplicates_curated_company_job() -> None:
    source = WorkableJobSource({"enabled": True})

    items = [
        {
            "title": "Java Developer (remote, work anywhere)",
            "shortcode": "A6E4426247",
            "telecommuting": True,
            "department": "Endless Lifecycle Support",
            "function": "Information Technology",
            "url": "https://apply.workable.com/j/A6E4426247",
            "published_on": "2026-05-21",
            "country": "Spain",
            "city": "Madrid",
            "locations": [{"country": "Spain", "city": "Madrid", "hidden": False}],
        },
        {
            "title": "Java Developer (remote, work anywhere)",
            "shortcode": "A6E4426247",
            "telecommuting": True,
            "department": "Endless Lifecycle Support",
            "function": "Information Technology",
            "url": "https://apply.workable.com/j/A6E4426247",
            "published_on": "2026-05-21",
            "country": "Poland",
            "city": "Warsaw",
            "locations": [{"country": "Poland", "city": "Warsaw", "hidden": False}],
        },
    ]
    grouped = source._to_raw_job(
        {
            **items[0],
            "locations": [
                {"country": "Spain", "city": "Madrid", "hidden": False},
                {"country": "Poland", "city": "Warsaw", "hidden": False},
            ],
        },
        CompanySetting("cloudlinux-1", "CloudLinux"),
    )

    assert grouped.source_name == "workable_curated"
    assert grouped.source_job_id == "cloudlinux-1:A6E4426247"
    assert grouped.company_name == "CloudLinux"
    assert grouped.location == "Madrid, Spain, Warsaw, Poland"
    assert grouped.country == "Spain"
    assert grouped.remote_type == RemoteType.REMOTE
    assert grouped.publication_date is not None


def test_recruitee_maps_curated_company_job() -> None:
    source = RecruiteeJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": 2553140,
            "title": "Rust & Java Engineer (Zurich, Vienna or Remote)",
            "description": "Build secure backend APIs.",
            "requirements": "Professional Java backend experience with Spring Boot.",
            "department": "Development",
            "remote": True,
            "published_at": "2026-04-07 08:27:16 UTC",
            "careers_url": "https://careers.procivis.ch/o/rust-java-engineer",
            "locations": [
                {
                    "name": "Remote within Europe",
                    "country": "Switzerland",
                    "note": "B2B Contract",
                },
                {"name": "Vienna", "country": "Austria"},
            ],
            "tags": ["Java", "Spring"],
        },
        CompanySetting("procivisag", "Procivis"),
    )

    assert raw.source_name == "recruitee_curated"
    assert raw.source_job_id == "procivisag:2553140"
    assert raw.company_name == "Procivis"
    assert raw.location == (
        "Remote within Europe, Switzerland, B2B Contract, Vienna, Austria"
    )
    assert raw.country == "Europe"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.publication_date is not None


def test_pinpoint_maps_curated_company_job_with_location_hint() -> None:
    source = PinpointJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "id": "457770",
            "title": "Java Software Engineer - Compliance",
            "description": "Develop Java backend services.",
            "skills_knowledge_expertise": "3–5 years of experience with Java.",
            "employment_type_text": "Full Time",
            "workplace_type_text": "Hybrid",
            "compensation": "Kč1,435,600 - Kč1,635,600 / year",
            "url": "https://tradingtechnologies.pinpointhq.com/en/postings/457770",
            "location": {"city": "Prague", "province": "Praha 1"},
        },
        CompanySetting("tradingtechnologies", "Trading Technologies", "Czechia"),
    )

    assert raw.source_name == "pinpoint_curated"
    assert raw.source_job_id == "tradingtechnologies:457770"
    assert raw.company_name == "Trading Technologies"
    assert raw.location == "Prague, Praha 1, Czechia"
    assert raw.country == "Europe"
    assert raw.remote_type == RemoteType.UNKNOWN
    assert raw.salary_original_text == "Kč1,435,600 - Kč1,635,600 / year"


def test_personio_maps_curated_company_job() -> None:
    source = PersonioJobSource({"enabled": True, "language": "en"})
    item = ET.fromstring(
        """
        <position>
          <id>2550716</id>
          <subcompany>LUMASERV GmbH</subcompany>
          <office>Remote RLP</office>
          <additionalOffices><office>Koblenz</office></additionalOffices>
          <department>Product Management</department>
          <name>Java Developer (Spring Boot) [gn]</name>
          <jobDescriptions>
            <jobDescription>
              <name>Summary</name>
              <value>As a Java Backend Engineer, build Spring Boot APIs.</value>
            </jobDescription>
            <jobDescription>
              <name>Qualifications</name>
              <value>Extensive professional experience in Java backend development.</value>
            </jobDescription>
          </jobDescriptions>
          <employmentType>permanent</employmentType>
          <seniority>experienced</seniority>
          <schedule>full-time</schedule>
          <yearsOfExperience>2-5</yearsOfExperience>
          <keywords>java,backend,springboot,restapi</keywords>
          <occupation>software_and_web_development</occupation>
          <occupationCategory>it_software</occupationCategory>
          <createdAt>2026-03-02T17:05:43+00:00</createdAt>
          <salaryInformation>
            <min>50000.00</min>
            <max>65000.00</max>
            <currencyCode>EUR</currencyCode>
            <type>yearly</type>
          </salaryInformation>
        </position>
        """
    )

    raw = source._to_raw_job(item, CompanySetting("lumaserv", "LUMASERV", "Germany"))

    assert raw.source_name == "personio_curated"
    assert raw.source_job_id == "lumaserv:2550716"
    assert raw.company_name == "LUMASERV GmbH"
    assert raw.location == "Remote RLP, Koblenz, Germany"
    assert raw.country == "Europe"
    assert raw.remote_type == RemoteType.REMOTE
    assert raw.salary_original_text == "50000.00-65000.00 EUR yearly"
    assert raw.url == "https://lumaserv.jobs.personio.de/job/2550716?language=en"
    assert raw.publication_date is not None
    assert raw.requirements and "2-5 years" in raw.requirements


def test_adzuna_maps_administrative_job_with_salary() -> None:
    source = AdzunaJobSource({"enabled": True, "country": "es"})

    raw = source._to_raw_job(
        {
            "id": "123",
            "title": "Auxiliar administrativo/a",
            "description": "Gestion documental, facturacion y atencion al cliente.",
            "redirect_url": "https://www.adzuna.es/details/123",
            "created": "2026-07-02T08:00:00Z",
            "salary_min": 18000,
            "salary_max": 22000,
            "salary_currency": "EUR",
            "company": {"display_name": "Example Admin"},
            "location": {"display_name": "Sevilla, Andalusia, Spain"},
            "category": {"display_name": "Admin Jobs"},
            "contract_time": "full_time",
        }
    )

    assert raw.source_name == "adzuna"
    assert raw.source_job_id == "123"
    assert raw.company_name == "Example Admin"
    assert raw.location == "Sevilla, Andalusia, Spain"
    assert raw.country == "Spain"
    assert raw.salary_original_text == "18000-22000 EUR annual"
    assert raw.publication_date is not None


def test_adzuna_affinity_filter_keeps_admin_and_rejects_sales_noise() -> None:
    source = AdzunaJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad", "facturacion"],
            "title_required_any_keywords": ["administrativo", "contabilidad"],
            "excluded_keywords": ["comercial puerta fria"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        source._to_raw_job(
            {
                "id": "1",
                "title": "Administrativo/a contable",
                "description": "Contabilidad y facturacion con Excel.",
                "location": {"display_name": "Almeria, Spain"},
            }
        ),
        source._to_raw_job(
            {
                "id": "2",
                "title": "Comercial puerta fria",
                "description": "Ventas por objetivos.",
                "location": {"display_name": "Sevilla, Spain"},
            }
        ),
    ]

    filtered = [
        job
        for job in jobs
        if adzuna_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_infoempleo_maps_administrative_listing() -> None:
    source = InfoempleoJobSource({"enabled": True})
    jobs = source._jobs_from_html(
        """
        <html>
          <body>
            <li class="offerblock">
              <h2 class="title mb15">
                <a href="/ofertasdetrabajo/auxiliar-administrativoa/sevilla/3188283/">
                  Auxiliar Administrativo/a
                </a>
              </h2>
              <p class="trunkat mb15">
                Facturacion, contabilidad, gestion documental y atencion al cliente.
                <p class="small extra-data mb15">
                  Al menos 2 anos de experiencia | jornada completa |
                  contrato indefinido | salario 18.000-24.000€
                </p>
                <div class="logoplusname mb15">
                  <span class="extra-data">Example Admin</span>
                </div>
              </p>
            </li>
          </body>
        </html>
        """,
        InfoempleoPage(
            "https://www.infoempleo.com/trabajo/oferta-empleo/administrativo/en_sevilla/",
            "Sevilla",
            "Spain",
        ),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "infoempleo"
    assert raw.source_job_id == "3188283"
    assert raw.company_name == "Example Admin"
    assert raw.title == "Auxiliar Administrativo/a"
    assert raw.location == "Sevilla"
    assert raw.country == "Spain"
    assert raw.remote_type == RemoteType.ONSITE
    assert raw.employment_type == "full_time"
    assert raw.salary_original_text is not None
    assert raw.url == (
        "https://www.infoempleo.com/ofertasdetrabajo/"
        "auxiliar-administrativoa/sevilla/3188283/"
    )


def test_infoempleo_affinity_filter_keeps_admin_and_rejects_course_noise() -> None:
    source = InfoempleoJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad", "facturacion"],
            "title_required_any_keywords": ["administrativo", "contable"],
            "excluded_keywords": ["oposiciones", "curso", "mozo"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="infoempleo",
            source_job_id="1",
            company_name="Example",
            title="Administrativo/a contable",
            description="Contabilidad, facturacion y Excel.",
            location="Almeria",
            country="Spain",
        ),
        RawJob(
            source_name="infoempleo",
            source_job_id="2",
            company_name="Academy",
            title="Curso de auxiliar administrativo",
            description="Oposiciones y formacion online.",
            location="Sevilla",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if infoempleo_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_trabajos_maps_administrative_listing() -> None:
    source = TrabajosJobSource({"enabled": True})
    jobs = source._jobs_from_html(
        """
        <html>
          <body>
            <div class="listado2014 card oferta">
              <a
                class="oferta"
                href="https://www.trabajos.com/ofertas/1196224136/admin-contable/"
                data-j4m_val="1196224136"
              >
                Administrativo/a Contable
              </a>
              <a class="empresa"><span>ATARJEA Asesores</span></a>
              <span class="location">Sevilla</span>
              <span class="fecha">26/06/2026</span>
              <div class="doextended">
                Facturacion, contabilidad, compras y apoyo administrativo con Excel.
              </div>
              <p class="oi">Contrato indefinido Jornada Completa 20.000 EUR - 21.000 EUR</p>
            </div>
          </body>
        </html>
        """,
        TrabajosPage(
            "https://www.trabajos.com/ofertas-empleo/contables/sevilla",
            "Sevilla",
            "Spain",
        ),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "trabajos"
    assert raw.source_job_id == "1196224136"
    assert raw.company_name == "ATARJEA Asesores"
    assert raw.title == "Administrativo/a Contable"
    assert raw.location == "Sevilla"
    assert raw.country == "Spain"
    assert raw.remote_type == RemoteType.ONSITE
    assert raw.employment_type == "full_time"
    assert raw.salary_original_text is not None
    assert raw.publication_date is not None


def test_trabajos_affinity_filter_keeps_admin_and_rejects_language_noise() -> None:
    source = TrabajosJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad", "compras"],
            "title_required_any_keywords": ["administrativo", "contable", "compras"],
            "excluded_keywords": ["portugues", "almacen", "cajero"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="trabajos",
            source_job_id="1",
            company_name="Example",
            title="Administrativo/a de compras",
            description="Compras, facturacion y Excel.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="trabajos",
            source_job_id="2",
            company_name="Example",
            title="Administrativo/a - Portugu\u00e9s",
            description="Atencion al cliente y archivo.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="trabajos",
            source_job_id="3",
            company_name="Example",
            title="Preparador de pedidos",
            description="Almacen y pedidos on line.",
            location="Almeria",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if trabajos_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_jobtoday_maps_internal_job_and_skips_external_jobs() -> None:
    source = JobTodayJobSource({"enabled": True, "internal_only": True})
    jobs = source._jobs_from_html(
        """
        <html>
          <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "feed": {
                  "sections": [
                    {
                      "items": [
                        {
                          "type": "job",
                          "payload": {
                            "key": "p3VB2m",
                            "role": "Tecnico administrativo contable",
                            "description": "Administrativo contable con Excel.",
                            "descriptionDeMarkdown": "Administrativo contable con Excel.",
                            "employmentType": "PART_TIME",
                            "isExternalJob": false,
                            "canonicalUrl": "/es/trabajo/tecnico-administrativo-contable-p3VB2m",
                            "companyName": "Grupo CIMAC",
                            "createDate": 1783070940081,
                            "salary": {
                              "from": 10,
                              "to": 15,
                              "currencyCode": "EUR",
                              "period": "HOURLY",
                              "isValid": true
                            },
                            "addressInfo": {
                              "display": {"city": "Seville"}
                            },
                            "categories": [
                              {"label": "Oficina y Administracion"}
                            ]
                          }
                        },
                        {
                          "type": "job",
                          "payload": {
                            "key": "external",
                            "role": "Administrativo contable",
                            "description": "External duplicate.",
                            "isExternalJob": true,
                            "externalUrl": "https://via.jobtoday.com/v2?job=external",
                            "companyName": "External"
                          }
                        }
                      ]
                    }
                  ]
                }
              }
            }
          }
          </script>
        </html>
        """,
        JobTodayPage(
            "https://jobtoday.com/es/trabajos-administrativo-contable/sevilla",
            "Sevilla",
            "Spain",
        ),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "jobtoday"
    assert raw.source_job_id == "p3VB2m"
    assert raw.company_name == "Grupo CIMAC"
    assert raw.title == "Tecnico administrativo contable"
    assert raw.location == "Sevilla"
    assert raw.employment_type == "part_time"
    assert raw.salary_original_text == "Salary 10-15 EUR hourly"
    assert raw.url == "https://jobtoday.com/es/trabajo/tecnico-administrativo-contable-p3VB2m"


def test_jobtoday_affinity_filter_rejects_retail_and_language_noise() -> None:
    source = JobTodayJobSource(
        {
            "required_any_keywords": ["administrativo", "contable"],
            "title_required_any_keywords": ["administrativo", "contable"],
            "excluded_keywords": ["tienda", "portugues"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="jobtoday",
            source_job_id="1",
            company_name="Example",
            title="Auxiliar Administrativo/a",
            description="Gestion documental y contabilidad.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="jobtoday",
            source_job_id="2",
            company_name="Example",
            title="Responsable de tienda",
            description="Administrativo de tienda.",
            location="Almeria",
            country="Spain",
        ),
        RawJob(
            source_name="jobtoday",
            source_job_id="3",
            company_name="Example",
            title="Administrativo/a - Portugues",
            description="Atencion al cliente.",
            location="Sevilla",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if jobtoday_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_talent_maps_listing_card_and_enriches_json_ld_detail() -> None:
    source = TalentJobSource({"enabled": True})
    jobs = source._jobs_from_html(
        """
        <html>
          <body>
            <article data-testid="job-card-unified">
              <h2 class="JobCard_title__abc">Administrativo/a</h2>
              <div class="JobCard_company__abc">ARES CONSULTORES</div>
              <div class="JobCard_location__abc">Almeria, ES</div>
              <div class="JobCard_snippet__abc">
                Departamento de Contabilidad y Administracion con Excel.
              </div>
              <span class="JobCard_timeText__abc">Ultima actualizacion: hace 3 dias</span>
              <a href="/view?id=622415509443390199">Mostrar mas</a>
            </article>
          </body>
        </html>
        """,
        TalentPage("https://es.talent.com/jobs?k=administrativo&l=almeria", "Almeria", "Spain"),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "talent"
    assert raw.source_job_id == "622415509443390199"
    assert raw.company_name == "ARES CONSULTORES"
    assert raw.location == "Almeria, ES"
    assert raw.publication_date is not None
    assert raw.url == "https://es.talent.com/view?id=622415509443390199"

    enriched = _enriched_from_detail(
        raw,
        """
        <html>
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@graph": [
              {
                "@type": "JobPosting",
                "title": "Administrativo/a",
                "description": "<p>Gestion de facturas, cobros, pagos y archivo digital.</p>",
                "datePosted": "2026-06-20",
                "hiringOrganization": {"name": "ARES CONSULTORES"},
                "jobLocation": {
                  "address": {
                    "addressLocality": "Almeria",
                    "addressRegion": "Andalucia",
                    "addressCountry": "ES"
                  }
                },
                "baseSalary": {
                  "currency": "EUR",
                  "value": {
                    "minValue": 18000,
                    "maxValue": 22000,
                    "unitText": "YEAR"
                  }
                }
              }
            ]
          }
          </script>
        </html>
        """,
    )

    assert "facturas" in enriched.description
    assert enriched.salary_original_text == "Salary 18000-22000 EUR year"
    assert enriched.location == "Almeria, Andalucia, ES"


def test_talent_affinity_filter_rejects_duplicate_aggregators_and_off_location() -> None:
    source = TalentJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad"],
            "title_required_any_keywords": ["administrativo"],
            "excluded_keywords": ["page personnel", "malaga", "almacen"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="talent",
            source_job_id="1",
            company_name="ARES CONSULTORES",
            title="Administrativo/a",
            description="Contabilidad, facturacion y archivo.",
            location="Almeria",
            country="Spain",
        ),
        RawJob(
            source_name="talent",
            source_job_id="2",
            company_name="Page Personnel",
            title="Administrativo/a contable",
            description="Contabilidad.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="talent",
            source_job_id="3",
            company_name="Example",
            title="Administrativo de operaciones",
            description="Puesto presencial en Malaga.",
            location="Sevilla",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if talent_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_manpower_maps_listing_and_structured_job_detail() -> None:
    source = ManpowerJobSource({"enabled": True})
    urls = source._job_urls_from_html(
        """
        <html>
          <body>
            <a href="/es/empleos/agricultura/administrativo-h-m-x-/729114">
              Administrativo (H/M/X)
            </a>
            <a href="/es/empleos/agricultura/administrativo-h-m-x-/729114">
              Administrativo (H/M/X)
            </a>
          </body>
        </html>
        """
    )

    assert urls == [
        "https://www.manpower.es/es/empleos/agricultura/administrativo-h-m-x-/729114"
    ]

    raw = source._job_from_detail_html(
        """
        <html>
          <body>
            <span>Numero de referencia:</span><span>729114</span>
            <span>Tipo de empleo:</span><span>Seleccion directa</span>
            <span>Salario:</span><span>23000 EUR - 25000 EUR</span>
            <span>Sector:</span><span>Industria</span>
            <span>Experiencia:</span><span>No requerida</span>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org/",
              "@type": "JobPosting",
              "title": "Administrativo Calidad y medio ambiente Sevilla(H/M/X)",
              "description": "<p>Gestion documental, Excel y apoyo administrativo.</p>",
              "datePosted": "20260605T085703",
              "validThrough": "20260705T215959Z",
              "employmentType": "Seleccion directa",
              "hiringOrganization": {"@type": "Organization", "name": "Manpower Spain"},
              "jobLocation": {
                "@type": "Place",
                "address": {
                  "@type": "PostalAddress",
                  "addressLocality": "Dos Hermanas",
                  "addressCountry": "SPAIN"
                }
              }
            }
            </script>
          </body>
        </html>
        """,
        "https://www.manpower.es/es/empleos/industria/admin/725115",
        ManpowerPage(
            "https://www.manpower.es/es/buscar-trabajo/ciudad/sevilla",
            "Sevilla",
            "Spain",
        ),
    )

    assert raw is not None
    assert raw.source_name == "manpower"
    assert raw.source_job_id == "725115"
    assert raw.company_name == "Manpower Spain"
    assert raw.location == "Dos Hermanas, SPAIN, Sevilla"
    assert raw.salary_original_text == "23000 EUR - 25000 EUR"
    assert raw.requirements is not None
    assert "No requerida" in raw.requirements
    assert raw.publication_date is not None
    assert raw.expiration_date is not None


def test_manpower_affinity_filter_keeps_target_location_and_rejects_senior_roles() -> None:
    source = ManpowerJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad"],
            "title_required_any_keywords": ["administrativo", "contable"],
            "excluded_keywords": ["responsable", "senior"],
            "allowed_location_keywords": ["sevilla", "almeria", "la algaba"],
        }
    )
    jobs = [
        RawJob(
            source_name="manpower",
            source_job_id="1",
            company_name="Manpower",
            title="Administrativo/a",
            description="Gestion documental y contabilidad.",
            location="La Algaba, Spain",
            country="Spain",
        ),
        RawJob(
            source_name="manpower",
            source_job_id="2",
            company_name="Manpower",
            title="Responsable administrativo",
            description="Gestion documental.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="manpower",
            source_job_id="3",
            company_name="Manpower",
            title="Administrativo/a",
            description="Contabilidad.",
            location="Madrid",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if manpower_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_bizneo_maps_filtered_listing_and_detail_page() -> None:
    source = BizneoJobSource({"enabled": True, "base_url": "https://empleo.imancorp.es"})
    urls = source._job_urls_from_html(
        """
        <html>
          <body>
            <a class="job-card" href="https://empleo.imancorp.es/jobs/admin-contable">
              Administrativo/a Contable 25H Dos Hermanas Presencial
            </a>
            <a class="job-card" href="https://empleo.imancorp.es/jobs/admin-contable">
              Administrativo/a Contable 25H Dos Hermanas Presencial
            </a>
          </body>
        </html>
        """
    )

    assert urls == ["https://empleo.imancorp.es/jobs/admin-contable"]

    raw = source._job_from_detail_html(
        """
        <html>
          <body>
            <p>16 de Junio</p>
            <span>Ubicacion</span><span>Dos Hermanas</span>
            <span>Categoria</span><span>Administracion de empresas</span>
            <span>Subcategoria</span><span>Finanzas y contabilidad</span>
            <span>Jornada laboral</span><span>Parcial</span>
            <span>Modalidad de trabajo</span><span>Presencial</span>
            <h1>Administrativo/a Contable 25H</h1>
            <p>Buscamos Administrativo/a Contable para facturas, archivo y bancos.</p>
            <p>Salario 11.00 Euros Brutos/Hora</p>
            <h2>Requisitos minimos</h2>
            <p>Experiencia demostrable en contabilidad y Excel.</p>
            <h2>Competencias</h2>
          </body>
        </html>
        """,
        "https://empleo.imancorp.es/jobs/admin-contable",
        BizneoPage(
            "https://empleo.imancorp.es/jobs?location=county:yeAcvi6dNm3l",
            "Sevilla",
            "Spain",
        ),
    )

    assert raw is not None
    assert raw.source_name == "bizneo"
    assert raw.source_job_id == "admin-contable"
    assert raw.company_name == "Unknown company"
    assert raw.title == "Administrativo/a Contable 25H"
    assert raw.location == "Dos Hermanas, Sevilla"
    assert raw.remote_type == RemoteType.ONSITE
    assert raw.employment_type == "part_time"
    assert raw.salary_original_text == "Salario 11.00 Euros Brutos/Hora"
    assert raw.requirements is not None
    assert "contabilidad" in raw.requirements
    assert raw.publication_date is not None


def test_bizneo_affinity_filter_rejects_warehouse_and_extra_language_noise() -> None:
    source = BizneoJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad"],
            "title_required_any_keywords": ["administrativo", "contable"],
            "excluded_keywords": ["mozo", "portugues", "frances"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="bizneo",
            source_job_id="1",
            company_name="Grupo Crit",
            title="Administrativo/a contable",
            description="Facturas, cobros y Excel.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="bizneo",
            source_job_id="2",
            company_name="Faster",
            title="Administrativo/a o Mozo/a de almacen",
            description="Administracion y almacen.",
            location="Sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="bizneo",
            source_job_id="3",
            company_name="Grupo Crit",
            title="Recepcionista auxiliar administrativa con frances alto",
            description="Atencion al cliente.",
            location="Salteras",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if bizneo_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_pagepersonnel_maps_search_result_and_skips_recommendations() -> None:
    source = PagePersonnelJobSource({"enabled": True, "include_recommended": False})
    jobs = source._jobs_from_html(
        """
        <html>
          <body>
            <div class="job-tile search-job-tile">
              <div class="job-title">
                <a href="/job-detail/administrativoa-contable/ref/jn-072026-7053201">
                  Administrativo/a Contable.
                </a>
              </div>
              <div class="job-location">Sevilla provincia</div>
              <div class="job-summary">Experiencia minima de 3 anos en contabilidad.</div>
              <div class="job_advert__job-desc-bullet-points">
                Empresa en Aznalcollar, Sevilla.
              </div>
            </div>
            <div class="job-tile recommended-job-tile search-job-tile">
              <div class="job-title">
                <a href="/job-detail/ap-operations/ref/jn-1">AP Operations Madrid</a>
              </div>
              <div class="job-location">Madrid</div>
            </div>
          </body>
        </html>
        """,
        PagePersonnelPage(
            "https://www.pagepersonnel.es/jobs/contable/seville",
            "Sevilla",
            "Spain",
        ),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "pagepersonnel"
    assert raw.source_job_id == "jn-072026-7053201"
    assert raw.company_name == "Page Personnel"
    assert raw.title == "Administrativo/a Contable"
    assert raw.location == "Sevilla provincia"
    assert raw.url == (
        "https://www.pagepersonnel.es/job-detail/administrativoa-contable/"
        "ref/jn-072026-7053201"
    )


def test_pagepersonnel_affinity_filter_keeps_target_location_only() -> None:
    source = PagePersonnelJobSource(
        {
            "required_any_keywords": ["administrativo", "contable"],
            "title_required_any_keywords": ["administrativo", "contable"],
            "excluded_keywords": ["senior", "responsable"],
            "allowed_location_keywords": ["sevilla"],
        }
    )
    jobs = [
        RawJob(
            source_name="pagepersonnel",
            source_job_id="1",
            company_name="Page Personnel",
            title="Administrativo/a Contable",
            description="Contabilidad y facturacion.",
            location="Sevilla provincia",
            country="Spain",
        ),
        RawJob(
            source_name="pagepersonnel",
            source_job_id="2",
            company_name="Page Personnel",
            title="Tecnico Contable Senior",
            description="Contabilidad.",
            location="Sevilla provincia",
            country="Spain",
        ),
        RawJob(
            source_name="pagepersonnel",
            source_job_id="3",
            company_name="Page Personnel",
            title="Administrativo/a Contable",
            description="Contabilidad.",
            location="Madrid",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if pagepersonnel_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_eurofirms_maps_listing_result() -> None:
    source = EurofirmsJobSource({"enabled": True})
    jobs = source._jobs_from_html(
        """
        <html>
          <body>
            <a href="/es/es/sevilla/asesor-atencion-cliente-500-000144">
              <article class="psf-offer" data-ordercode="500-000144" data-offerid="abc">
                <h3 class="psf-offer__title">Asesor/a comercial y atenci&#xF3;n al cliente</h3>
                <h4 class="psf-offer__site">sevilla, sevilla</h4>
                <p class="psf-offer__description">
                  Tareas de atenci&#xF3;n al cliente y gesti&#xF3;n administrativa.
                </p>
                <div class="psf-offer__info">
                  <div class="info-block info-block--salary">
                    <span>Salario 18.500&#x20AC; bruto/a&#xF1;o</span>
                  </div>
                  <div class="info-block"><span>01/07/2026</span></div>
                </div>
              </article>
            </a>
          </body>
        </html>
        """,
        EurofirmsPage("https://jobs.eurofirms.com/es/es/trabajo/sevilla", "Sevilla", "Spain"),
    )

    assert len(jobs) == 1
    raw = jobs[0]
    assert raw.source_name == "eurofirms"
    assert raw.source_job_id == "500-000144"
    assert raw.company_name == "Eurofirms"
    assert raw.title == "Asesor/a comercial y atenci\u00f3n al cliente"
    assert raw.location == "sevilla, sevilla"
    assert raw.salary_original_text == "Salario 18.500\u20ac bruto/a\u00f1o"
    assert raw.publication_date is not None
    assert raw.url == (
        "https://jobs.eurofirms.com/es/es/sevilla/asesor-atencion-cliente-500-000144"
    )


def test_eurofirms_affinity_filter_keeps_customer_service_and_rejects_noise() -> None:
    source = EurofirmsJobSource(
        {
            "required_any_keywords": ["administrativo", "atencion al cliente", "cliente"],
            "title_required_any_keywords": ["administrativo", "atencion al cliente"],
            "excluded_keywords": ["portugues", "promotor", "almacen", "operario"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="eurofirms",
            source_job_id="1",
            company_name="Eurofirms",
            title="Asesor/a comercial y atencion al cliente",
            description="Gestion administrativa y atencion al cliente.",
            location="sevilla, sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="eurofirms",
            source_job_id="2",
            company_name="Eurofirms",
            title="Administrativo/a con portugues",
            description="Atencion al cliente con portugues.",
            location="alcala de guadaira, sevilla",
            country="Spain",
        ),
        RawJob(
            source_name="eurofirms",
            source_job_id="3",
            company_name="Eurofirms",
            title="Promotor/a",
            description="Atencion al cliente a pie de calle.",
            location="sevilla, sevilla",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if eurofirms_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_domestiko_maps_jobposting_structured_data() -> None:
    posting = domestiko_job_posting(
        """
        <html>
          <script type="application/ld+json">
          {
            "@context": "http://schema.org",
            "@type": "JobPosting",
            "title": "Auxiliar administrativo logístico (Administración y secretariado)",
            "description": "Gestión documental y facturación. Salario mensual de 1800 euros.",
            "employmentType": "FULL_TIME",
            "datePosted": "2026-06-29T01:59:00.000Z",
            "validThrough": "2026-09-27T19:04:00.000Z",
            "jobLocation": {
              "@type": "Place",
              "address": {
                "@type": "PostalAddress",
                "addressCountry": "ES",
                "addressRegion": "ALMERIA",
                "addressLocality": "Arboleas"
              }
            },
            "hiringOrganization": {
              "@type": "Organization",
              "name": "Domestiko.com"
            },
            "identifier": {
              "@type": "PropertyValue",
              "value": "arboleas-auxiliar-administrativo-logistico-jha5"
            }
          }
          </script>
        </html>
        """
    )

    assert posting is not None
    raw = domestiko_raw_job_from_posting(
        "domestiko",
        "https://www.domestiko.com/empleo/oferta/arboleas-auxiliar-administrativo-logistico-jha5/",
        posting,
    )

    assert raw.source_name == "domestiko"
    assert raw.source_job_id == "arboleas-auxiliar-administrativo-logistico-jha5"
    assert raw.title == "Auxiliar administrativo logístico"
    assert raw.company_name == "Domestiko.com"
    assert raw.location == "Arboleas, Almeria"
    assert raw.country == "Spain"
    assert raw.remote_type == RemoteType.ONSITE
    assert raw.employment_type == "full_time"
    assert raw.publication_date is not None
    assert raw.expiration_date is not None


def test_domestiko_affinity_filter_keeps_admin_and_rejects_banking_noise() -> None:
    source = DomestikoJobSource(
        {
            "required_any_keywords": ["administrativo", "contabilidad", "gestion"],
            "title_required_any_keywords": ["administrativo", "contable", "gestion"],
            "excluded_keywords": ["banca", "limpieza"],
            "allowed_location_keywords": ["sevilla", "almeria"],
        }
    )
    jobs = [
        RawJob(
            source_name="domestiko",
            source_job_id="1",
            company_name="Domestiko.com",
            title="Auxiliar administrativo",
            description="Gestión administrativa y facturación.",
            location="Sevilla, SEVILLA",
            country="Spain",
        ),
        RawJob(
            source_name="domestiko",
            source_job_id="2",
            company_name="Domestiko.com",
            title="Auxiliar de banca",
            description="Atención bancaria y caja.",
            location="Sevilla, SEVILLA",
            country="Spain",
        ),
    ]

    filtered = [
        job
        for job in jobs
        if domestiko_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
    ]

    assert [job.source_job_id for job in filtered] == ["1"]


def test_ats_affinity_filter_keeps_java_europe_roles() -> None:
    source = GreenhouseJobSource(
        {
            "must_have_any_keywords": ["java", "spring", "kotlin"],
            "required_any_keywords": ["java", "backend", "spring"],
            "title_required_any_keywords": ["backend", "developer", "engineer"],
            "excluded_keywords": ["sales", "manager"],
            "allowed_location_keywords": ["spain", "europe", "remote"],
        }
    )
    job = source._to_raw_job(
        {
            "id": 1,
            "absolute_url": "https://job-boards.greenhouse.io/example/jobs/1",
            "company_name": "Example",
            "title": "Backend Java Engineer",
            "content": "Spring Boot APIs",
            "location": {"name": "Remote, Europe"},
        },
        CompanySetting("example", "Example"),
    )

    assert ats_matches_affinity(
        job,
        [],
        source.required_any_keywords,
        source.title_required_any_keywords,
        source.excluded_keywords,
        source.allowed_location_keywords,
        source.must_have_any_keywords,
    )


def test_ats_deduplicates_same_job_variants_and_prefers_europe_location() -> None:
    jobs = [
        _raw_ats_job(
            source_job_id="pandadoc:poland",
            company_name="PandaDoc",
            title="Application Security Engineer",
            description="Secure Java Spring services with OWASP and CI/CD. Salary 21,000 PLN.",
            location="Remote (Poland)",
        ),
        _raw_ats_job(
            source_job_id="pandadoc:europe",
            company_name="PandaDoc",
            title="Application Security Engineer",
            description="Secure Java Spring services with OWASP and CI/CD. Salary 21,000 PLN.",
            location="Remote (Europe)",
        ),
        _raw_ats_job(
            source_job_id="pandadoc:portugal",
            company_name="PandaDoc",
            title="Application Security Engineer",
            description="Secure Java Spring services with OWASP and CI/CD. Salary 222000 PLN.",
            location="Remote (Portugal)",
        ),
    ]

    deduped = _dedupe_job_variants(jobs)

    assert len(deduped) == 1
    assert deduped[0].source_job_id == "pandadoc:europe"


def test_ats_deduplication_keeps_same_title_with_distinct_description() -> None:
    jobs = [
        _raw_ats_job(
            source_job_id="example:platform",
            company_name="Example",
            title="Software Engineer",
            description="Build Java platform services with Spring Boot and Kubernetes.",
            location="Remote (Europe)",
        ),
        _raw_ats_job(
            source_job_id="example:security",
            company_name="Example",
            title="Software Engineer",
            description="Develop mobile SDK tooling for Android devices and release automation.",
            location="Remote (Europe)",
        ),
    ]

    deduped = _dedupe_job_variants(jobs)

    assert [job.source_job_id for job in deduped] == ["example:platform", "example:security"]


def test_ats_affinity_keeps_appsec_europe_roles_without_java() -> None:
    source = GreenhouseJobSource(
        {
            "must_have_any_keywords": ["java", "application security", "devsecops"],
            "required_any_keywords": ["java", "application security", "owasp"],
            "title_required_any_keywords": ["backend", "engineer", "security"],
            "excluded_keywords": ["sales", "manager"],
            "allowed_location_keywords": ["spain", "europe", "remote"],
        }
    )
    job = source._to_raw_job(
        {
            "id": 4,
            "absolute_url": "https://job-boards.greenhouse.io/example/jobs/4",
            "company_name": "Example",
            "title": "Application Security Engineer",
            "content": "OWASP, secure development, SAST and cloud security.",
            "location": {"name": "Remote, Europe"},
        },
        CompanySetting("example", "Example"),
    )

    assert ats_matches_affinity(
        job,
        [],
        source.required_any_keywords,
        source.title_required_any_keywords,
        source.excluded_keywords,
        source.allowed_location_keywords,
        source.must_have_any_keywords,
    )


def test_ats_affinity_rejects_qa_automation_title() -> None:
    source = GreenhouseJobSource(
        {
            "must_have_any_keywords": ["java", "spring"],
            "required_any_keywords": ["java", "spring"],
            "title_required_any_keywords": ["engineer", "developer"],
            "excluded_keywords": ["qa automation", "quality assurance", "test engineer"],
            "allowed_location_keywords": ["spain", "europe", "remote"],
        }
    )
    job = source._to_raw_job(
        {
            "id": 5,
            "absolute_url": "https://job-boards.greenhouse.io/example/jobs/5",
            "company_name": "Example",
            "title": "QA Automation Engineer",
            "content": "Java Spring test automation.",
            "location": {"name": "Remote, Europe"},
        },
        CompanySetting("example", "Example"),
    )

    assert (
        ats_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
            source.must_have_any_keywords,
        )
        is False
    )


def test_ats_affinity_does_not_exclude_boilerplate_manager_mentions() -> None:
    source = GreenhouseJobSource(
        {
            "must_have_any_keywords": ["java"],
            "required_any_keywords": ["java", "spring"],
            "title_required_any_keywords": ["java", "backend"],
            "excluded_keywords": ["manager"],
            "allowed_location_keywords": ["spain", "europe"],
        }
    )
    job = source._to_raw_job(
        {
            "id": 2,
            "absolute_url": "https://job-boards.greenhouse.io/example/jobs/2",
            "company_name": "Example",
            "title": "Backend Java Engineer",
            "content": "Build Spring APIs and collaborate with product managers.",
            "location": {"name": "Madrid, Spain"},
        },
        CompanySetting("example", "Example"),
    )

    assert ats_matches_affinity(
        job,
        [],
        source.required_any_keywords,
        source.title_required_any_keywords,
        source.excluded_keywords,
        source.allowed_location_keywords,
        source.must_have_any_keywords,
    )


def test_ats_affinity_rejects_remote_us_when_europe_required() -> None:
    source = GreenhouseJobSource(
        {
            "must_have_any_keywords": ["java"],
            "required_any_keywords": ["java"],
            "title_required_any_keywords": ["java"],
            "excluded_keywords": [],
            "allowed_location_keywords": ["spain", "europe"],
        }
    )
    job = source._to_raw_job(
        {
            "id": 3,
            "absolute_url": "https://job-boards.greenhouse.io/example/jobs/3",
            "company_name": "Example",
            "title": "Java Engineer",
            "content": "Build Java APIs.",
            "location": {"name": "United States, Remote"},
        },
        CompanySetting("example", "Example"),
    )

    assert (
        ats_matches_affinity(
            job,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
            source.must_have_any_keywords,
        )
        is False
    )


def test_search_scope_rejects_german_local_offer() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=["Spain", "European Union"],
        cities=["Sevilla", "Madrid", "Malaga", "Barcelona"],
        remote_from=["Spain"],
        languages=["es", "en"],
    )
    job = _normalized_job(
        title="Analytics Software Engineer (m/w/d)",
        location="Paderborn",
        country="Germany",
        remote_type=RemoteType.UNKNOWN,
        language="de",
    )

    assert _matches_search_scope(job, search_config) is False


def test_search_scope_keeps_remote_european_offer() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=["Spain", "European Union"],
        cities=["Sevilla", "Madrid", "Malaga", "Barcelona"],
        remote_from=["Spain"],
        languages=["es", "en"],
    )
    job = _normalized_job(
        title="Backend Java Engineer",
        location="Remote Europe",
        country=None,
        remote_type=RemoteType.REMOTE,
        language="en",
    )

    assert _matches_search_scope(job, search_config) is True


def test_search_scope_keeps_remote_worldwide_offer() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=["Spain", "European Union"],
        cities=["Sevilla", "Madrid", "Malaga", "Barcelona"],
        remote_from=["Spain"],
        languages=["es", "en"],
    )
    job = _normalized_job(
        title="Backend Java Engineer",
        location="Anywhere in the World",
        country=None,
        remote_type=RemoteType.REMOTE,
        language="en",
    )

    assert _matches_search_scope(job, search_config) is True


def test_search_scope_keeps_remote_eu_country_offer() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=["Spain", "European Union"],
        cities=["Sevilla", "Madrid", "Malaga", "Barcelona"],
        remote_from=["Spain"],
        languages=["es", "en"],
    )
    job = _normalized_job(
        title="Backend Java Engineer",
        location="Poland",
        country="Poland",
        remote_type=RemoteType.REMOTE,
        language="en",
    )

    assert _matches_search_scope(job, search_config) is True


def test_search_scope_rejects_non_remote_eu_country_offer() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=["Spain", "European Union"],
        cities=["Sevilla", "Madrid", "Malaga", "Barcelona"],
        remote_from=["Spain"],
        languages=["es", "en"],
    )
    job = _normalized_job(
        title="Backend Java Engineer",
        location="Berlin",
        country="Germany",
        remote_type=RemoteType.ONSITE,
        language="en",
    )

    assert _matches_search_scope(job, search_config) is False


def test_operations_search_scope_requires_target_city_not_all_spain() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=[],
        cities=["Sevilla", "Almeria", "Almería"],
        remote_from=[],
        languages=["es"],
    )
    sevilla_job = _normalized_job(
        title="Auxiliar administrativo/a",
        location="Sevilla, Spain",
        country="Spain",
        remote_type=RemoteType.ONSITE,
        language="es",
    )
    madrid_job = _normalized_job(
        title="Auxiliar administrativo/a",
        location="Madrid, Spain",
        country="Spain",
        remote_type=RemoteType.ONSITE,
        language="es",
    )

    assert _matches_search_scope(sevilla_job, search_config) is True
    assert _matches_search_scope(madrid_job, search_config) is False


def test_operations_search_scope_rejects_portuguese_language() -> None:
    search_config = SearchConfig(
        queries=[],
        countries=[],
        cities=["Sevilla", "Almeria", "Almer\u00eda"],
        remote_from=[],
        languages=["es", "en"],
    )
    job = _normalized_job(
        title="Administrativo/a",
        location="Sevilla, Spain",
        country="Spain",
        remote_type=RemoteType.ONSITE,
        language="pt",
    )

    assert _matches_search_scope(job, search_config) is False


def test_tecnoempleo_maps_listing_and_enriches_jobposting() -> None:
    source = TecnoempleoJobSource({"enabled": True})
    listing = """
    <div class="p-3 border rounded mb-3 bg-white">
      <h3><a href="https://www.tecnoempleo.com/java-dev/acme/rf-123">Java Developer</a></h3>
      <a class="text-primary link-muted">Acme</a>
      <span class="d-block d-lg-none text-gray-800">
        <b>Madrid</b> (Híbrido) - 03/07/2026<br/>42.000€ - 60.000€ b/a
      </span>
      <span class="hidden-md-down text-gray-800">
        Build Java APIs<br/><span class="badge">Java</span><span class="badge">Spring Boot</span>
      </span>
    </div>
    """
    raw = source._jobs_from_listing(
        listing,
        TecnoempleoPage(
            "https://www.tecnoempleo.com/ofertas-trabajo/discapacidad",
            "Spain",
            "Spain",
        ),
    )[0]
    posting = {
        "@context": "http://schema.org/",
        "@type": "JobPosting",
        "title": "Java Developer con certificado de discapacidad",
        "description": (
            "Java Spring Boot APIs. Imprescindible certificado de discapacidad en vigor. "
            "Experiencia requerida: 3 años."
        ),
        "datePosted": "2026-07-03",
        "employmentType": "FULL_TIME",
        "hiringOrganization": {"@type": "Organization", "name": "Acme"},
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "Madrid",
                "addressRegion": "Madrid",
                "addressCountry": "ES",
            },
        },
        "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "EUR",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": 42000,
                "maxValue": 60000,
                "unitText": "YEAR",
            },
        },
    }
    detail = f'<script type="application/ld+json">{json.dumps(posting)}</script>'

    enriched = tecnoempleo_enriched_from_detail(raw, detail)

    assert enriched.source_name == "tecnoempleo"
    assert enriched.company_name == "Acme"
    assert enriched.salary_original_text == "42000-60000 EUR al año"
    assert enriched.remote_type == RemoteType.HYBRID
    assert enriched.requirements is not None
    assert "Experiencia requerida: 3 años" in enriched.requirements


def test_tecnoempleo_affinity_requires_disability_and_technical_title() -> None:
    source = TecnoempleoJobSource(
        {
            "required_any_keywords": ["certificado de discapacidad", "discapacidad en vigor"],
            "title_required_any_keywords": ["java", "backend", "devops"],
            "excluded_keywords": ["product owner"],
            "allowed_location_keywords": ["spain", "madrid"],
        }
    )
    accepted = RawJob(
        source_name="tecnoempleo",
        source_job_id="1",
        company_name="Acme",
        title="Backend Java Developer",
        description="Spring Boot APIs. Imprescindible certificado de discapacidad en vigor.",
        location="Madrid",
        country="Spain",
    )
    rejected = RawJob(
        source_name="tecnoempleo",
        source_job_id="2",
        company_name="Acme",
        title="Product Owner",
        description="Java platform. Imprescindible certificado de discapacidad en vigor.",
        location="Madrid",
        country="Spain",
    )

    assert (
        tecnoempleo_matches_affinity(
            accepted,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
        is True
    )
    assert (
        tecnoempleo_matches_affinity(
            rejected,
            [],
            source.required_any_keywords,
            source.title_required_any_keywords,
            source.excluded_keywords,
            source.allowed_location_keywords,
        )
        is False
    )


def test_pagepersonnel_normalizes_short_annual_salary() -> None:
    source = PagePersonnelJobSource({"enabled": True})
    card = """
    <div class="job-tile search-job-tile">
      <div class="job-title"><h3>
        <a href="/job-detail/analista/ref/jn-1">
          Analista de datos con certificado de discapacidad
        </a>
      </h3></div>
      <div class="job-location">Madrid</div>
      <div class="job-salary">EUR28 - EUR40 por año</div>
      <div class="job-nature">Remoto / híbrido</div>
      <div class="job-summary">SQL y Power BI.</div>
      <div class="job_advert__job-desc-bullet-points">
        Imprescindible certificado de discapacidad.
      </div>
    </div>
    """

    job_tile = BeautifulSoup(card, "html.parser").select_one(".job-tile")
    assert job_tile is not None

    raw = source._to_raw_job(
        job_tile,
        PagePersonnelPage("https://www.pagepersonnel.es/jobs/discapacidad", "Spain", "Spain"),
    )

    assert raw is not None
    assert raw.salary_original_text == "28000-40000 EUR al año"
    assert raw.remote_type == RemoteType.HYBRID


def test_portalento_maps_dirty_jobposting_and_salary() -> None:
    source = PortalentoJobSource({"enabled": True})
    detail = """
    <div class="datosReferencia"><div class="wrapper">
      <p><strong>Empresa: </strong>Inserta Empleo</p>
      <p><strong>Lugar de trabajo: </strong>Paterna (Valencia/València)</p>
      <p><strong>Tipo contrato: </strong>Indefinido</p>
      <p><strong>Salario bruto: </strong>Entre 16.501 € y 33.000 €</p>
      <p><strong>Fecha publicación: </strong>03/07/2026</p>
    </div></div>
    <script type="application/ld+json">
    {
      "@context" : "http://schema.org",
      "@type" : "JobPosting",
      "title" : "Analista de Ciberseguridad N1",
      "hiringOrganization" : "Inserta Empleo",
      "jobLocation" : {"@type" : "Place", "address" : "Paterna (Valencia/València)"},
      "datePosted": "2026-07-03",
      "description" : "Gestión de alertas SIEM.
      Desarrollo de automatizaciones SOAR y análisis con WAF EDR firewall"
    }
    </script>
    """

    raw = source._job_from_detail(
        detail,
        "https://www.portalento.es/Candidatos/Ofertas/Detalle/analista-de-ciberseguridad-n1/71387a44-b65b-44a4-8248-e41c74164c74",
    )

    assert raw is not None
    assert raw.title == "Analista de Ciberseguridad N1"
    assert raw.salary_original_text == "16501-33000 EUR"
    assert (
        portalento_matches_affinity(
            raw,
            [],
            ["ciberseguridad", "siem", "soar"],
            ["analista", "ciberseguridad"],
            ["vigilante"],
            ["valencia", "spain"],
        )
        is True
    )


def test_fundacion_randstad_maps_api_job_with_experience_and_salary() -> None:
    source = FundacionRandstadJobSource({"enabled": True})

    raw = source._to_raw_job(
        {
            "offerId": 2990023,
            "title": "Ingeniero/a de PLC con certificado de discapacidad del 33% o más",
            "company": "Fundación Randstad",
            "date": "2026-07-02T04:00:00",
            "description": "Diseñar y probar sistemas de control basados en PLC.",
            "requirements": (
                "Certificado de discapacidad. "
                "Experiencia en desarrollo de software para PLC."
            ),
            "conditions": "Contrato indefinido.",
            "url": "https://www.randstad.es/candidatos/ofertas-empleo/oferta/plc-2990023",
            "minSalary": 35000,
            "maxSalary": 40000,
            "salarayTypeName": "Año",
            "province": {"name": "Vizcaya"},
            "city": {"name": "Bilbao"},
            "experienceYears": 4,
            "journalType": {"name": "Completa"},
            "workModality": {"name": "Presencial"},
        }
    )

    assert raw is not None
    assert raw.source_name == "fundacion_randstad"
    assert raw.salary_original_text == "35000-40000 EUR al año"
    assert raw.requirements is not None
    assert "Experiencia requerida: 4 años" in raw.requirements


def _raw_ats_job(
    *,
    source_job_id: str,
    company_name: str,
    title: str,
    description: str,
    location: str,
) -> RawJob:
    return RawJob(
        source_name="greenhouse_curated",
        source_job_id=source_job_id,
        company_name=company_name,
        title=title,
        description=description,
        location=location,
        remote_type=RemoteType.REMOTE,
        url=f"https://example.test/jobs/{source_job_id}",
    )


def _normalized_job(
    *,
    title: str,
    location: str,
    country: str | None,
    remote_type: RemoteType,
    language: str | None,
) -> NormalizedJob:
    return NormalizedJob(
        source_job_id="test",
        company_name="Example",
        company_website=None,
        title=title,
        normalized_title=title.lower(),
        description="Build Java services",
        requirements=None,
        location=location,
        country=country,
        remote_type=remote_type,
        employment_type=None,
        experience_min_years=None,
        experience_max_years=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        salary_original_text=None,
        salary_unknown=True,
        url=None,
        publication_date=None,
        expiration_date=None,
        technologies=["Java"],
        raw_payload={},
        content_hash="hash",
        language=language,
    )
