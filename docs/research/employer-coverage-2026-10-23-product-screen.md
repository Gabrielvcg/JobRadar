# Product and employer source screening — 23 October 2026

This follows the [GHCG delivery](../operations/employer-coverage-delivery-2026-10-23-continuation.md).
The baseline is production **0.1.50**, revision `e601e01601344d80b2abd6e8407b55bb38853fcb`,
with 618 candidate records, 603 market posting URLs, 192 market employer names,
28 A/B postings and eight A/B employers. All 28 application checks were fresh.

## Useful manual leads

These are research leads, **not new verified A/B records**. No application was sent,
and their salary or active recruitment cannot be assumed from an accessible advert.

| Employer / primary publication | Actual fit | Missing evidence and decision |
| --- | --- | --- |
| [UST — Java Software Engineer, Spain remote](https://es.linkedin.com/jobs/view/java-software-engineer-100%25-remote-spain-at-ust-espa%C3%B1a-latam-4478456821) | Explicit Spain remote; Java/API development, microservices, event-driven systems, Maven/Gradle, Jenkins and testing. The detailed mandatory list publishes no numeric years. AWS, AWS serverless, Docker and AWS certification appear under nice-to-have, not mandatory paid cloud experience. | Salary absent; strong hands-on experience still requested. Employer LinkedIn publication has an Apply control, but a vacancy-bound CV form was not verified. Corporate careers GET returns 403. Manual lead; no automated LinkedIn collection or access bypass. |
| [agap2 — Desarrollador Java](https://es.linkedin.com/jobs/view/desarrollador-java-at-agap2-spain-4479794683) | Spain, 100% remote; concrete duties include Java application development, REST APIs, microservices and migrations. Requires Java/Spring/Boot experience without numeric years in this publication. | Salary absent; application process unverified. Do not merge with the separate corporate Spring Boot advert below: no shared hiring-process identity was established. |
| [Nunegal — Java, 100% remote](https://www.nunegal.com/web/desarrollador-a-java-100-remoto/) | Corporate page is live with concrete Java/Spring MVC/Hibernate development duties and an inline email/CV form. | Explicitly asks **more than four years**. Remote country is not explicitly stated in the vacancy text; a Spanish corporate address alone is not the same as a job-specific employment-country statement. Salary absent. Outside the preferred early-career range; no automatic A/B claim or integration justified. |

## Additional employer inventory

The following **15 new named employers** were checked against primary sources. With
the prior 81, the documented inventory reaches **96**. This is a research count,
not growth in useful opportunities. Individual-role or landing-page checks below
are not represented as an exhaustive survey of every global vacancy at a company.

| Employer | Official interface inspected | Evidence / integration decision |
| --- | --- | --- |
| [Camunda](https://jobs.ashbyhq.com/camunda) | Documented public Ashby posting feed | 42 live postings. Indexed non-senior Backend Core/API role 93fc1bfe is absent. Current backend roles are senior distributed systems/data layer/streaming; the non-senior alternatives concern engineering operations and installation/infrastructure artifacts with strong prior platform skills. They do not establish a new early-career Java backend opportunity. No source added just for future-level references. |
| [Hazelcast](https://hazelcast.pinpointhq.com/) | Public Pinpoint board/feed | Nine postings; current Java Core and Java SDET roles are senior and specify UK remote. Corporate remote benefits do not establish Spain eligibility. Existing Pinpoint adapter is reusable, but current value is insufficient. |
| [Sportserve](https://careers.sportserve.co/jobs) | Public Teamtailor index and its advertised RSS | Index exposes no current Java job cards and the observed RSS contains zero items. An old indexed senior Java detail is insufficient live-feed evidence. Do not infer company-wide hiring has stopped, or add an empty feed as a discovery result. |
| [Sympower](https://careers.sympower.net/) | Corporate-linked Recruitee public careers site | Current observed index shows General Counsel and Head of Energy Markets/Trading. The earlier corporate join-the-team URL is 404 and points to this current host. No Java vacancy in the observed index. |
| [Axoniq](https://www.axoniq.io/careers) | Corporate careers HTML | Current advertised positions are Business Development Researcher and Sales Executive, both US remote. Core Java/event-sourcing product expertise does not imply an available Java engineering position. |
| [Appfire](https://job-boards.greenhouse.io/appfire) | Documented public Greenhouse posting API | 27 live postings. Spain entries are Product Launch Manager and Senior TypeScript/Node/Effect fullstack. Current Java/React roles specify Poland/Bulgaria and require substantial frontend experience. Indexed Software Engineer–Java Spain is absent. No stale or wrong-country source added. |
| [Servinform](https://www.servinform.es/empleo/) | Corporate-linked [Bizneo portal](https://empleo.servinform.es/jobs) | Public paths allowed by robots. Current observed index is mainly BPO/admin/contact-center; its available category selector has no programming option. Previously indexed Sevilla junior Java ads do not prove a current vacancy. No eligible role established in this screening; no claim about uninspected historical pages. |
| [ITPartner — itpartner.es](https://itpartner.es/busco-oportunidades/) | Corporate opportunities page | Accessible general recruitment/contact page, with no vacancy-specific Java listing or reusable ATS feed established. The similarly named Italian IT Partner and other IT Partner brands are not substituted for this company. |
| [Nexion Solutions](https://nexions.com/carrera-laboral/) | Corporate careers URL from primary web index; direct GET | Corporate page returns HTTP 500. Indexed corporate backend example asks four-plus years; the separate two-year Java/Spring employer advert is on Indeed, without a suitable authorized feed or verified direct form established. Do not import salary/availability from republished mirrors. |
| [Grupo NS](https://grupo-ns.com/ofertas-de-trabajo/) | Corporate and public [Bizneo programming index](https://empleo.grupo-ns.com/jobs?subcategory=programming) | Current programming index has 13 entries. Its three Java examples are hybrid Madrid/Málaga, including Java/Scripting/PLSQL; the indexed remote Java/Eclipse advert is absent. Existing Bizneo adapter is sufficient technically, but current geography is incompatible. |
| [agap2 España](https://agap2.com/spain/jobs/) | Corporate WordPress jobs index/detail; employer publication | Observed index lists eight engineering/business roles, not Java. Separate live Spring Boot detail asks three years but mostly lists technologies and generic new development, without the concrete duties present in the distinct LinkedIn publication. Public feed paths are explicitly disallowed by robots; no RSS crawl or bespoke connector added. |
| [UST](https://www.ust.com/en/careers) | Corporate careers and employer's public job publication | Corporate GET is 403. Detailed LinkedIn role is a useful manual Java/backend lead, with cloud experience desirable. No maintainable authorized vacancy feed or verified direct application was established, and LinkedIn is not integrated. |
| [CONVOTIS Iberia](https://convotisiberia.teamtailor.com/) | Public Teamtailor RSS | Current feed has 29 entries and no Java-titled vacancy. Older Teralco/CONVOTIS Java fullstack results are hybrid and do not establish a current eligible backend role. These are the same renamed employer, not two companies. |
| [EPAM](https://careers.epam.com/en/jobs/spain) | Public Spain search and official indexed vacancy | Spain search is accessible but its observed response does not expose complete job links for reuse by an existing adapter. The examined indexed Java vacancy is senior and requires US-aligned working hours. No current early/mid Java source value proved; no undocumented/private endpoint guessed. |
| [Nunegal Consulting](https://www.nunegal.com/web/desarrollador-a-java-100-remoto/) | Corporate WordPress vacancy and inline form | Real development duties and email/CV fields, but explicit more-than-four-year requirement, unpublished salary and no vacancy-specific remote-country statement. No integration added simply because a form exists. |

## Existing-source rejection check

The indexed eXperience vacancy
[Programador/a Junior Java](https://jobs.experienceis.com/jobs/programador-a-junior-java-3599ebbc-c3b0-47bd-b3e0-35d94fb4c3e7)
looks attractive in search results. Its direct live page explicitly says **Oferta
cerrada**. Its absence from the current opportunities is therefore not a demonstrated
ingestion false negative. It was not reimported as an active junior vacancy.

The separate agap2 corporate role was evaluated in a read-only scoring probe. Even
with a hypothetical fresh application check, the unchanged policy returns U49 for
insufficient concrete development responsibilities. That hypothetical evidence was
never stored. No duties were copied from another publication to force a higher
grade, and no scoring changes were made to reach a company-count target.

## Outcome and stopping decision

This iteration establishes **no new verified A/B employer or posting**. The useful
output is the two manual Java leads above and primary-source evidence explaining
why the apparent automated sources do not justify integration. Additional search
results were used for discovery only; unverified company names, portal labels or
guessed ATS tenant IDs were not promoted into sources or reviewed-employer totals.

Production remains 0.1.50. No application code, profile, scoring rule, source setting
or production data was changed by this research. No new deployment or synthetic
tests were needed. The inspected remaining choices are stale, wrong-country,
senior/platform-heavy, blocked, or require a bespoke integration without proven
current opportunity value. This meets the requested stopping criterion for this
iteration; the target of ten current A/B employers is still unmet.

## Final operational check

Final read-only snapshot at **17:44 UTC**:

| Metric | Baseline | Final |
| --- | ---: | ---: |
| Candidate records, including disabled fixtures | 618 | 618 |
| Market records / distinct canonical posting URLs | 603 | 603 |
| Market employer names | 192 | 192 |
| A/B records with fresh application evidence | 28 | 28 |
| Employers with A/B records | 8 | 8 |
| Secondary-profile records | 156 | 156 |
| Exact duplicate URLs per profile | 0 | 0 |

The final snapshot has no source errors. Public health reports the exact unchanged
0.1.50 feature revision; login returns 303, dashboard 200, authenticated export 200
and anonymous export 401. The refreshed full CSV contains **618 rows / 36 columns**.
The five-to-ten useful-new-postings monthly goal is not established by this unchanged
snapshot, nor by increasing the research-inventory count.
