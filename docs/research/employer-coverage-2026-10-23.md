# Employer coverage continuation — 23 October 2026

This continues the [49-employer investigation](employer-coverage-2026-10-22.md),
starting from deployed 0.1.48. The focus remains new eligible Java/backend employers,
with current evidence taking precedence over search indexes and portal mirrors.
Fifteen additional named employers and one employer-unconfirmed portal were reviewed.
This does not mean sixteen new eligible hiring companies were found.

## Live baseline and attribution

At **13:58 UTC**, the candidate profile contained 609 records, including 15 disabled
synthetic records: 594 market records, 191 distinct market employer names, 26 A/B
records from seven employers, all 26 with fresh application-path evidence. The
secondary profile contained 156 records. Production health, login, dashboard and
protected export were checked again.

The preceding delivery ended with 601 candidate records. Eight records had therefore
arrived through scheduled collection before this continuation began. They are not
discoveries produced by this research round. Scheduled ingestion continued during
the research; later counts and the specific scoring correction are separated in
the companion delivery report.

## New employer/source review

| Employer / source | Interface and evidence quality | Actual finding | Integration decision |
| --- | --- | --- | --- |
| [Clarity AI](https://job-boards.eu.greenhouse.io/clarityai/jobs/4847799101) | Official EU Greenhouse vacancy; direct HTTP check | Indexed Junior Software Engineer used Java/Kotlin/Spring, but the live URL redirects to an inactive-board error and returns 404. | Removed. No current application or source value established. Avoid importing older mirrors. |
| [Teya](https://www.teya.com/careers) | Corporate careers links Ashby; documented public posting feed fetched | 116 live records. Backend examples are senior/principal and list Porto, Riga or London; no compatible Spain role was proved. | Existing Ashby adapter could be reused; no current A/B contribution justifies adding this board now. |
| [TransferGo](https://www.transfergo.com/careers) | Corporate careers HTML | Current advertised department links do not establish eligible Java hiring from Spain; an older Greenhouse backend result names Vilnius. | No eligible current vacancy proved. Do not treat generic international hiring as Spain eligibility. |
| [Isotrol](https://www.isotrol.com/es/careers) | Official SSR careers index | Sevilla presence and hybrid benefits are real. The observed current cards cover sales, finance, project engineering and systems; no Java role found in that index. | Useful product employer for future monitoring, insufficient current Java value for a custom connector. |
| [Tier1](https://www.tier1.es/web/guest/uneteatier1) | Public vacancy host redirects to corporate careers | Corporate page offers general CV intake. The previously advertised [Java product role](https://www.getmanfred.com/en/job-offers/8208/tier1-java-developer-dic25) explicitly closed in June. | Do not turn general CV intake or a closed Manfred role into a live vacancy. |
| [Imatia](https://jobs.imatia.com/jobs/desarrollador-a-backend-java-mid-e6bbc10a-b6c8-45ae-9c15-107b44b50483) | Bizneo public listing/detail, robots permits public paths | Current payment-platform Java/Spring role, minimum three years. Fullstack technologies are largely desirable. Index explicitly labels A Coruña/hybrid, while detail benefits mention telework and omit structured work-mode metadata. | Manual geography question. Do not assume 100% Spain remote from generic benefits or the adapter's fallback. No A/B source added. |
| [Serem](https://www.serem.com/language/en/employment/job-offers/) | Corporate WordPress index and one actual detail | The recent Sevilla backend card links to Tecnoempleo. The separate directly hosted two-year Java/APIGEE detail is dated 2023. | Recent snippet plus old corporate form is insufficient current application evidence. No bespoke scraper for stale details or a blocked downstream portal. |
| [atmira](https://www.atmira.com/posiciones-abiertas-formulario/) | Corporate position-selection/CV page | Public role choices include Java Analyst/Microservices and Java PL/SQL. Current accessible page does not provide vacancy-specific duties, numeric experience or remote-Spain terms sufficient for scoring. | Named manual lead only; a general selection form does not supply complete vacancy evidence. |
| [Genki](https://genki.world/careers) | Official careers page; public indexed role descriptions treated separately | Product startup publicly describes worldwide remote work. The indexed mid backend role uses Kotlin and a custom event-sourcing framework; current corporate HTML did not expose a direct role/application link in the inspected content. | Interesting broader backend lead. Exact current vacancy, Spain contract and Kotlin fit remain unconfirmed; no automatic Java A/B claim. |
| [Grupo Data Portugal](https://grupo-data.careers-page.com/jobs/69874257-e39b-4d09-80ab-7bac8bec852b) | Public Manatal JobPosting HTML, job-specific apply route | Live Java Backend & AI, minimum three years, body explicitly allows PT or ESP, English B1/preferred B2 and Spanish C1. Mandatory list also includes Node.js/JavaScript. Metadata says Portugal while the body includes Spain. Salary absent. | Useful manual lead with explicit country discrepancy. Apply route returns 200 with the role title but fields are JavaScript-rendered; email/CV form not independently established. Do not count as verified A/B. Corporate website returned 520; employer URL is declared by the posting. |
| [SCI Serviclients](https://empleo.serviclients.com/jobs) | Corporate website links its official Teamtailor host; advertised public RSS checked | Current feed/index has 14 vacancies and no Java role. Search engines still show a Sevilla healthcare Java role among an older 19-job snapshot. | Existing RSS adapter technically reusable, but no current Java contribution. Respect live feed over indexed mirrors. |
| [cleversoft](https://www.clever-soft.com/careers/java-engineer-2/) | Official corporate Java page indexed; direct automated GET blocked 403 | RegTech product company with Seville included and up to 50% home working. Indexed corporate requirements say 1–5 years; a newer employer LinkedIn publication asks five years. Salary absent. | Strong manual product/Sevilla lead, with conflicting experience and blocked current verification. No bypass or automatic A/B classification. |
| [AUTO1 Group](https://www.auto1-group.com/en/jobs/) | Existing SmartRecruiters public API, company `AUTO1Group`, Java/country `es` query | Current documented API query returns zero postings. Mirrors advertise older Car Data Java roles with three-year requirements and inconsistent remote/location labels. | No live eligible posting proved. Do not add a source based on mirror labels. |
| [XTB](https://jobs.eu.lever.co/xtb) | Official EU Lever board and employer listing in primary web results | Current Java example is senior and lists Warsaw. Broad lists of 65 eligible countries appear on mirrors, not in the inspected employer evidence. | No Spain-compatible early/mid Java vacancy confirmed; do not copy mirror eligibility. |
| [NTT DATA](https://careers.services.global.ntt/global/en/job/c854d353bd3ec00/Profesionales-Java-Andaluc%C3%ADa) | Official employer result explicitly shows position filled | Older Java Andalucía advertisement offered 2–4 years and Sevilla, but employer page says filled while mirrors continue to republish it. | Closed primary evidence; not a current A/B discovery. |

The named employer inventory is now **64 distinct researched employers across the
two reports**. The separate portal below is excluded from that employer count.
Primary web-index evidence and direct HTTP evidence are explicitly distinguished;
no claim is made that every indexed job was directly accessible or current.

## Important rejected portal: employer identity

[A Bizneo tenant branded “Plexus”](https://plexus.careers.ats.bizneo.cloud/jobs)
contains apparently suitable backend Java roles and an accessible job-specific
CV application fragment. Its observed
[privacy link](https://plexus.careers.ats.bizneo.cloud/politica-privacidad?company=plexus&locale=es&site_id=1887)
explicitly states that this is a **blind application** and that the employer cannot
currently be identified. No corporate Plexus Tech link to this tenant was proved.

It would be incorrect to label this as a verified new Plexus Tech employer source
merely because the tenant says “Plexus” or its upload form works. Some content also
resembles banking roles published under other agencies. There is insufficient
evidence to merge them as one project or count them as independent employers.
The portal was not integrated, allowlisted or used to inflate A/B employer counts.
Only observed GET routes were read; no personal data, CV or application was sent.

## Real new-ingestion quality finding

While scheduled sources continued collecting jobs, the official knowmad mood role
[8594415](https://knowmadmood.teamtailor.com/jobs/8594415-ingeniero-a-de-soporte-de-aplicaciones-java-remoto)
entered as **A / 72**. Its actual description explicitly says that its main work
is operation and support, with monitoring, incidents and small corrective Java
changes. A Java title, Spring stack and accessible upload form do not establish a
backend-engineering career fit.

The small 0.1.49 correction recognizes explicit Spanish predominance statements
such as “orientado principalmente a la operación y soporte” before incidental
software duties determine work focus. Both software and operations evidence are
retained. Existing operations points, career weights, thresholds, salary rules,
cloud experience rules and personal profiles remain unchanged. A regression uses
this real vacancy, with controls for negated operations focus and backend work
with incidental support. It is a focused defect correction during new-ad validation,
not a new scoring audit or architecture redesign.

No new employer was integrated in this round: the inspected remaining options
were removed, blocked, outside the location/experience scope or insufficiently
specified. Manual leads are retained with their uncertainty instead of being
converted into artificial verified A/B records. The goals of ten A/B employers
and a measured monthly discovery rate remain unproven.
