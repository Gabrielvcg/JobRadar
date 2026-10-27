# Official-source expansion: Signicat and bounded follow-up screening

Checked 2026-10-23. This iteration adds one useful employer source. Search-only
company mentions are discovery leads, not reviewed employers or integrations.

## Accepted source and actual vacancy

[Signicat public careers](https://signicat.teamtailor.com) exposes the standard
Teamtailor [RSS](https://signicat.teamtailor.com/jobs.rss?per_page=200). Robots allows
public job paths; it disallows internal/application-management paths. Seven live
items were inspected. Existing RSS location/title filters return exactly one:

| Employer / official vacancy | Location | Experience | Salary | Assessment | Application evidence |
| --- | --- | --- | --- | --- | --- |
| [Signicat — Java Software Engineer (Identity Proofing), Spain](https://signicat.teamtailor.com/jobs/8342057-java-software-engineer-identity-proofing-spain) | Madrid, Spain; structured fully remote and visible Fully Remote | 3+ years Java 21 / Spring Boot; candidate has 14 professional months | Unknown; expectations discussed during selection | B76 with the unchanged production profile/policy | Public job-bound [candidate/CV form](https://signicat.teamtailor.com/jobs/8342057-java-software-engineer-identity-proofing-spain/applications/new), HTTP 200; checked 18:04 UTC |

Duties include designing and developing services in distributed applications,
quality/security/performance, code reviews and platform improvements. SQL/NoSQL,
RabbitMQ and microservices are required. Fluent English and Spanish are explicit;
the current engine reports no standardized English level, so this requirement must
remain visible in the human review. B2 certification does not establish fluency.
GCP appears in the stack, with cloud-native familiarity desirable; AWS is not a
required skill in this advert. Salary compatibility cannot be assumed.

The vacancy was published September 8, 2026. It is newly discovered by this run,
not newly published today. One posting, one employer and one accessible application
are established; no count of unseen client projects is inferred.

Reuse the RSS collector and existing Teamtailor form verifier, with a twelve-hour
interval, one feed request per collection and location filtering. No new adapter,
dependency, scoring rule, weight, threshold or private profile is needed. Public
form checks expire under the existing 24-hour lifetime.

## Other primary-source checks

These 12 additional employers received direct official-interface inspection.
Nunegal was a follow-up to the preceding report, not a new employer count.

| Employer / official interface | Observed evidence and decision |
| --- | --- |
| [Exceltic](https://careers.exceltic.com/jobs) | Accessible ASP.NET public index; first ten visible cards include ADA, .NET and engineering roles, without a Java vacancy. ADA's two-year remote role makes Java desirable only. Not an exhaustive survey of all pagination; no custom collector justified by this evidence. |
| [Altia](https://opportunities.altia.es/jobs?subcategory=programming) | Eight programming pages inspected. Attractive indexed junior Java is explicitly closed on its direct page. Current sampled Java roles require five-plus years, while European-agency backend/fullstack examples require up to 15 IT years and foreign locations. No new current A/B role proved. |
| [Coremain](https://empleo.coremain.com/jobs) | Current index has general CV and Analista Programador Java in hybrid Santiago de Compostela. Indexed junior and remote fullstack pages say closed. No compatible current source established. |
| [Izertis](https://jobs.izertis.com/jobs?subcategory=programming) | Both programming pages inspected. Current results concern Oracle/Apex, BI, Python/AI, cloud/operations and Portugal. Indexed Java backend advert says closed. No current Java A/B source proved. |
| [Laberit](https://careers.laberit.com/jobs?subcategory=programming) | Seven current programming-category cards and no Java-titled vacancy. Indexed three-year remote Java detail explicitly says closed. No stale role imported. |
| [Rawson BPO](https://rawsonbpo.com/ofertas-de-trabajo/) | Official WP Job Manager board identified. Its [documented public job RSS](https://rawsonbpo.com/?feed=job_feed&search_keywords=java&posts_per_page=25) has Java functional developer and AEM frontend. Full Java content requires four years, hybrid Madrid, logistics history and mandatory Oracle/backend certifications. General blog RSS is not a vacancy feed. No source added. |
| [Vermont Solutions](https://vermont-solutions.com/en/talent/) | Corporate page lists current junior Java/Angular and two-to-three-year Java analyst opportunities. Official Viterbit board and junior detail return HTTP 403 challenge. No bypass or mirror import. Useful manual follow-up; English B2+/C1 and occasional technical leadership matter for the analyst. |
| [Keapps](https://keapps.com/candidates) | Corporate-linked custom-domain Zoho site and public RSS work. Four Java/integration details checked. Data Engineer Java/Spark asks two years and publishes 36–42k, but eligible country is absent in ATS metadata. Middleware role explicitly offers hybrid Sevilla among several cities and 34–37k in prose, versus Madrid / 33–36k in metadata. Existing unchanged policy returns D in read-only probes: data duties/eligibility incomplete; middleware title/metadata mismatch. These are manual leads, not accepted A/B or reasons to inject country, rename roles or relax scoring. Other Java roles require five/six-plus years. |
| [Arelance](https://www.arelance.com/sumate-al-equipo/) | Live corporate page offers a general CV form, without vacancy-specific listings. Employer adverts on Tecnoempleo describe three-year Java microservices remote Spain at 30–36k, but no suitable official employer feed was established. No general CV represented as an open job application. |
| [Serbatic](https://www.serbatic.es/talento/) | Corporate careers link goes to VASS's Cornerstone portal. No documented public collection interface was established during this check. Search copies of Java/.NET roles concern Mexico. No assumed Spain eligibility or duplicate employer identity. |
| [Getronics](https://www.getronics.com/es/careers) | Corporate opportunities link to LinkedIn; general contact/CV option also exists. No maintainable official vacancy feed established. No LinkedIn crawler added. |
| [Marfeel](https://www.marfeel.com/) | Corporate links directly to Recruiterflow. Public index embeds six jobs as JSON; Java Developer 246 is live with complete public JobPosting data and a rendered job-specific name/email/CV/submit form, inspected without entering data. Index says Barcelona / Remote, with full remote, hybrid or office as options; country eligibility is not explicit. No minimum years/pay published; requires deep Java/concurrency, reactive execution and strong WebFlux/R2DBC. Unchanged scoring gives D34 from the Barcelona/hybrid interpretation. No custom adapter or inferred Spain eligibility added merely to reach a target. Backend Engineer 243 is primarily Node/TypeScript and asks five years; Java is only a plus. |

Only Signicat is incorporated. Further searches after finding it did not establish
another low-maintenance A/B source. The two best additional manual checks are
Vermont's junior vacancy and Marfeel Java 246; blocked collection and incomplete
eligibility/experience evidence remain explicit.

## Candidate preparation checkpoint

The following three demonstrable examples would strengthen the present Java A/B
applications; these are portfolio/training priorities, not fabricated work history:

1. A Spring Boot API with explicit contracts, SQL persistence, authentication,
   unit/integration tests and CI. Explain a concrete design trade-off and a defect
   caught by the tests. Signicat asks Java/Spring, databases, quality and security.
2. A message-driven integration with retries, idempotency, duplicate delivery,
   concurrency and recovery demonstrated by a reproducible failure scenario.
   RabbitMQ/microservices in Signicat and messaging/integrations in existing Java
   roles make this relevant. State which broker was used professionally.
3. An AWS deployment with logs, secret handling, rollback and measured behaviour,
   accompanied by a short English explanation. Label it personal-project evidence;
   it does not substitute for paid AWS experience or satisfy every specialist
   requirement. Fluent English and the experience gap remain significant.

## Code publication checkpoint

Before this iteration's commit, the public delivery branch
`codex/career-radar-release` is 29 commits ahead of `origin/main`, with zero commits
behind the locally fetched tracking reference. Production 0.1.50 was built from its
exact committed revision; this is the established operational delivery route.
This observation does not prove that Gabriel intended `main` to remain permanently
behind. No merge or change of branch strategy is authorized by the coordinating
checkpoint alone.

Recommendation: prepare a reviewable comparison/PR to main covering the complete
career-radar result, document CI and deployment evidence, and retain working-tree
changes outside the release until reviewed. Merge only with Gabriel's explicit OK.
Do not describe main as containing the deployed features until that integration
actually occurs. No PR or merge is performed by this research report.
