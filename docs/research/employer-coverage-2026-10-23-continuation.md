# Further employer coverage — 23 October 2026

This continues the [previous 64-employer investigation](employer-coverage-2026-10-23.md).
Production baseline at 16:08 UTC: 616 candidate records (601 market records plus
15 disabled fixtures), 191 market employer names, 27 A/B records from seven employers,
and 156 secondary-profile records. Twenty-five A/B application checks were still fresh;
two had passed the existing 24-hour evidence lifetime. This is verification expiry,
not two removed vacancies.

## Sources reviewed

| Employer | Official source / interface | Current evidence and decision |
| --- | --- | --- |
| Wallapop | [Greenhouse board](https://job-boards.greenhouse.io/wallapop), public posting API | Five current jobs; engineering manager, MLOps, data science and nonengineering. No Java backend individual-contributor opening in the observed feed. No integration added. |
| BlaBlaCar | [Lever board](https://jobs.lever.co/blablacar), public posting API | Eight live postings, including three backend roles. Locations are Paris/France; generic remote benefits do not establish employment from Spain. No integration added. |
| rindus | [Personio board](https://rindus.jobs.personio.de/), public XML | Eleven live vacancies. The attractive non-senior backend listing 2745945 returns 404 and is absent from the XML. Current Java/SAP Commerce role requires senior experience; other engineering role is hybrid Málaga. No current A/B contribution proved. |
| Xolo | [Corporate careers](https://www.xolo.io/zz-en/careers), linked Workable embed account 714240 | Fourteen location entries, representing eight distinct shortcodes, currently contain no engineering vacancy. Indexed Product Engineer pages offering Spain remote and EUR 60–69k are absent from the live feed. The guessed company-name slug returned 404; the numeric account was subsequently obtained from the employer's own public embed configuration. No stale source added. |
| Veeva Systems | [Technical Consultant – Integrations](https://jobs.lever.co/veeva/dd1d2834-b9d2-400b-987e-d9b102c3996b), Lever | HTML and CV form return 200 and describe Spain remote, three years of Java, and EUR 50–85k **total compensation**, not guaranteed base salary. However, the 916-posting public feed omits it and its documented individual API URL returns 404. Conflicting availability stays manual/unconfirmed. Current entry-level consulting role requires Barcelona commuting. |
| Global Human Capital Group | [Corporate careers](https://globalhumancapitalgroup.com/en/careers/) links [Zoho portal](https://globalhumancapitalgroup.zohorecruit.com/jobs/Careers); portal advertises public RSS | Live portal contains 21 roles; RSS supplies two Java/Spring vacancies. Junior role has one–two years in actual requirements, B2 minimum/C1 desired, Spain remote, concrete API development duties, and unknown salary. The vacancy-bound rendered CV/email form was checked without entering personal data or solving CAPTCHA. Integrate the advertised RSS with bounded public-detail enrichment. |
| EUROPEAN DYNAMICS | [Workable board](https://apply.workable.com/european-dynamics/), public widget | 189 location entries; Spain entries are Python/React fullstack and senior Databricks administration/architecture. No eligible Java contribution proved. |
| Plexus Tech | [Official corporate careers](https://www.plexus.es/unete-al-equipo/), WordPress | Primary web index shows a two-year Java/Microservices opening. Direct corporate index/robots GET returns Cloudflare 403. No bypass. The employer-unconfirmed Bizneo tenant from the preceding report remains excluded and is not used as Plexus identity evidence. |
| AD4 Octógono | [Official Viterbit vacancy](https://ad4octogono.viterbit.site/desarrollador-java-remoto-mdxR9fHTYWZy/) | Indexed Java/Spring Boot role asks around two years and advertises EUR 25–35k, remote. Direct GET returns a 403 challenge; robots alone allows access. Strong manual lead; no blocked source integrated. |
| Krell | [Viterbit board](https://krell-consulting.viterbit.site/) | Indexed board advertises several remote Java roles, including senior backend. Direct board GET returns 403. The older two-and-a-half–four-year analyst role is marked closed by its employer publication. No unsupported scraper added. |
| Coderland | [Manatal vacancy](https://www.careers-page.com/coderlandjob/job/4R4V59Y5) | Employer vacancy explicitly offers Spain remote but requires at least ten years of backend experience. Future-level reference, not a current A/B discovery. |
| Bahía Software | [Official Java role](https://enjoybahia.es/portfolio/desarrolladores-java/) | Primary indexed role asks two–three years of Java/Spring MVC/Hibernate but names Galicia/Santander offices without establishing Spain remote or Sevilla eligibility. No automatic A/B claim. |
| IOON | [Employer Java/Spring Boot publication](https://es.linkedin.com/jobs/view/desarrollador-java-springboot-at-ioon-4469303151) | Employer publication describes two–three years, remote, Java/Spring Boot/Oracle and EUR 28–30k. Promising manual lead. Corporate careers links LinkedIn and InfoJobs; a reusable authorized vacancy feed was not established. Neither portal is scraped or integrated. |
| Apiux Tech | [Employer Java/LRBA publication](https://es.linkedin.com/jobs/view/desarrollador-java-con-experiencia-y-certificaci%C3%B3n-en-lrba-at-apiux-tech-4479571295) | Spain remote, one–three years, but actual LRBA experience/certification is explicitly required. Other current indexed Java role is hybrid Madrid/four-plus years. No current A/B source established. |

| INNOCV Solutions | [Official Teamtailor index](https://jobs.innocv.com/jobs) | Direct current index has eleven postings, including junior Go and Python/AI backend, but no Java opening. Older Java Senior mirrors remain indexed. No Java source added solely for those mirrors. |
| Babel | [Official Workday Java Health role](https://babelgroup.wd103.myworkdayjobs.com/es/REC_External_Career_Site/job/Java-Developer--Health-_JR107776) | Indexed official role names Sevilla and Full Remote. Direct HTTP response is an empty JavaScript shell, and no suitable authorized complete public feed was established. Manual lead with current requirements/application unconfirmed; no private Workday API guessed. |
| Viewnext | [Corporate careers](https://www.viewnext.com/empleo/) links LinkedIn jobs and its ePreselec CV portal | Corporate page is accessible and advertises remote choices. Its ePreselec portal and robots both return a 405 bot/CAPTCHA challenge. No bypass or inference that generic remote benefits apply to a particular Java job. |

These are **17 additional named employers**, bringing the research inventory to
81 named employers. This count is separate from employers represented in JobRadar
and from employers with verified A/B opportunities.

## GHCG integration and limitations

The existing RSS adapter performs discovery and title/technology filtering. Its
excerpt omits the actual requirements and responsibilities. A small Zoho RSS
extension reads those fields from the **public detail page's server-rendered JSON**;
it does not call private APIs or execute employer JavaScript. Detail requests stay
on the configured HTTPS employer host, check numeric vacancy identity and title,
retain the complete requirements, and are limited to five per 12-hour collection.
Generic RSS's implicit remote fallback is discarded: the normalizer must find
actual remote evidence. Structured experience is retained even when it conflicts
with the prose.

The junior title conflicts with “Senior” in the description template, but its actual
requirements explicitly say one–two years; portal metadata says one–three years.
The senior role has two–three years in requirements, minimum three in the description,
and four–five in structured metadata. These discrepancies remain visible; no score
threshold or candidate profile was changed. Both advertisements date from **5 January
2026**. They are newly discovered by this run, not newly published vacancies or a
proven monthly opportunity rate. The end client is unnamed, so two postings do not
prove two independent hiring projects.

The junior form was observed in the rendered browser on 23 October: matching job
title/ID, email and name fields, required CV attachment, CAPTCHA and Submit Application.
The CAPTCHA was not completed, and no application or personal information was sent.
The automatic HTTP verifier cannot confirm this JavaScript-rendered form. Browser
evidence is recorded explicitly and remains subject to the existing 24-hour expiry;
future unverified vacancies remain U until a real application check is available.

See the companion delivery report for measured ingestion, deployment, preservation
and final export results.
