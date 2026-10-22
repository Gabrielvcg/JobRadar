# Employer coverage expansion — 22 October 2026

This investigation starts from production 0.1.47. Its purpose is distinct, usable
employer coverage, without changing career weights, grade thresholds, salary
policy, paid-cloud requirements or the candidate's profile.

## Baseline

The authenticated production export captured at 19:19 UTC contains 595 candidate
records: 580 market records and 15 disabled synthetic records. There are 187 market
employers, 580 distinct canonical URLs, 22 A/B records and 22 verified A/B paths.
Only five employers supply A/B opportunities: knowmad mood (15), T-Systems Iberia
(1), Talent Connect (2), The White Team (2), Talan (2). The top 20 contains 14
knowmad mood records. The secondary profile contains 156 records; total storage
is 751. These are historical totals, not discoveries from this execution.

The ten-employer target and five-to-ten usable discoveries per month are goals,
not evidence of current supply. A single investigation cannot establish a monthly
arrival rate.

## Accepted integrations

| Employer / official source | Interface and boundaries | Evidence / value |
| --- | --- | --- |
| [eXperience IT Solutions](https://jobs.experienceis.com/jobs?subcategory=programming) | Existing Bizneo adapter; five observed programming pages; at most 35 selected details; 1-second pacing; 12-hour interval | Three distinct current Java processes: banking integration, MQ/event-driven backend, ASO/APX APIs. Minimum experience 3/4/3 years. Two publish annual gross salary. |
| [SNGULAR](https://www.sngular.com/es/talento-y-cultura/jobs) | Small configurable employer HTML adapter; same-origin observed links; JobPosting required; visible duties supplement incomplete metadata; at most 10 details; 12-hour interval | One actual Java role, Spain and 100% remote in its vacancy metadata. Advanced Java/Spring/Kafka and agent/SDD requirements require careful preparation; numeric minimum and salary absent. |

Both sites allow the researched public paths in robots.txt. Public access and
robots permission do not establish a general reuse license; retain attribution,
use a low request rate, and disable a source if its access conditions change.
No application, CV upload, CAPTCHA solution or employer contact is performed.

Bizneo's public listing explicitly loads a job-specific candidate form. Verification
follows that observed GET only, binds its job ID and same host, and requires email,
CV picker and enabled submit controls. Generic account registration is insufficient.
SNGULAR embeds a vacancy-bound CV form. Its submit control waits for applicant
validation, consent and CAPTCHA; accessible form evidence does not mean submission
was attempted, that an employer will respond, or that salary is compatible.

## Employer inventory

The following table records actual official page/feed checks, not counts inferred
from search snippets. ATS counts are snapshots and may change. “No integration”
means the current evidence did not justify maintaining another scheduled source;
it does not mean the employer never hires Java engineers.

| Employer / official careers evidence | ATS / interface checked | Java/backend and experience / Spain evidence | Decision and maintainability |
| --- | --- | --- | --- |
| [Devoteam](https://jobs.smartrecruiters.com/Devoteam/744000154404420-desarrollador-java-) | SmartRecruiters public postings | Java role, 3 years overall / 2 Java; primarily telework Spain. Duties insufficiently concrete for current automated work-focus assessment. | Manual lead U; existing adapter reusable, but no verified A/B contribution demonstrated. |
| [Sopra Steria](https://careers.smartrecruiters.com/SopraSteria1) | SmartRecruiters | 11 indexed Java matches; Sevilla examples require French; other jobs require relocation or 5+ years. | No current compatible A/B established; avoid volume. |
| [Inetum](https://careers.smartrecruiters.com/Inetum2) | SmartRecruiters | Four Spanish Java index matches; detail checks show Madrid office / Genesys or fullstack constraints. | No new usable A/B; older backend search hit not in live query. |
| [Endava](https://careers.smartrecruiters.com/endava) | SmartRecruiters | No Spain Java records in the checked country/query response. | Public adapter viable; insufficient current value. |
| [act digital / Alter Solutions](https://careers.smartrecruiters.com/AlterSolutions) | SmartRecruiters | Current Spanish Java example requires Madrid presence. | No current Sevilla/remote match. |
| [lastminute.com](https://careers.smartrecruiters.com/lastminutecom) | SmartRecruiters and official listing | 17 live postings globally, none Spain. Finance Core Platform detail is Chiasso, Switzerland, hybrid despite an indexed Madrid label. | Reject current geography; country filtering is correct, not a false negative. |
| [Flywire](https://careers.smartrecruiters.com/Flywire1) | SmartRecruiters | Two-year Java/Ruby software role explicitly requires Valencia office/relocation. | D for residence constraint; generic remote benefits do not override office duty. |
| [SQLI](https://careers.smartrecruiters.com/SQLI1) | SmartRecruiters | Java role requires 5+ years and Valencia presence. | No current opportunity; future/reference only. |
| [Auctane](https://job-boards.greenhouse.io/auctane) | Greenhouse public board | 22 jobs, six Java mentions; Madrid integrations example requires five office days. | No current location-compatible contribution. |
| [Vonage](https://job-boards.greenhouse.io/vonage) | Greenhouse | 15 active jobs, no current Java match. Previously indexed Java/Kotlin vacancy removed. | Do not ingest removed search hits. |
| [Duetto](https://job-boards.greenhouse.io/duettoresearch) | Greenhouse | 15 postings, five Java matches; Spain roles are senior/staff. | C reference; no current A/B. |
| [FREENOW](https://job-boards.greenhouse.io/freenow) | Greenhouse | 16 active postings, no current Java match; indexed backend hit removed. | No integration value at snapshot. |
| [New Relic](https://job-boards.greenhouse.io/newrelic) | Greenhouse | 57 active postings; Java mentions largely boilerplate / US or India. Indexed Software Engineer II removed. | No current eligible vacancy confirmed. |
| [Sonatype](https://jobs.lever.co/sonatype) | Lever public postings | 11 active records mention Java in body; checked roles are outside Spain or incompatible functions. | Java company boilerplate does not prove role fit. |
| [Zartis](https://jobs.lever.co/zartis) | Lever | Seven jobs; no actual current Java role. Senior Scala/GenAI and open application do not meet target. | No source added. |
| [Job&Talent](https://jobs.lever.co/jobandtalent) | Lever | 30 jobs; no current Java match in response. | Public adapter viable, no current value. |
| [Lynx](https://lynxtech.com/es/empleo/) | Official Greenhouse links / public board | Live global board contains 11 jobs and no Java match; old EU links on corporate site are not evidence of live Java hiring. | No integration added. |
| [Secture](https://secturelabs.recruitee.com/) | Recruitee | Observed public offers endpoint returns 404; Java remote search advertisement is old. | No active feed established; no repeated retry/bypass. |
| [Capitole](https://careers.capitole-consulting.com/) | Current Viterbit; old Teamtailor feed | Old feed has 14 roles, no Java; current board blocks local automated access. Old remote Java slug redirects to index. | Respect block; do not use stale board to imply active vacancy. |
| [Q-Tech](https://qtech.teamtailor.com/) | Teamtailor RSS | 90 roles / 12 Java matches; checked matches mainly Barcelona presence/senior, one lacks location. | D/C/U; no confirmed current A/B. |
| [Kapres](https://kapres.teamtailor.com/) | Teamtailor RSS | 84 records; only one Java match and no current A/B established. | Low marginal value. |
| [TNG Technology Consulting](https://tngtech.jobs.personio.de/job/2577771?language=en) | Personio public XML, 17 roles | Entry-level software role, Sevilla/remote Spain, EUR 32,200–39,200; proficient English; German/Spanish advantageous. Role does not specify Java assignment. | Useful manual lead; do not inject corporate Java boilerplate into language-agnostic role to manufacture fit. |
| [Grupo Digital](https://ofertasempleo.grupodigital.eu/jobs) | Public Bizneo, two programming pages checked | Java candidates require Madrid/Barcelona presence or senior experience; Spring Boot generic title hides 6+ years despite a separate one-year specialist requirement. | No new current A/B; old/current board overlap needs caution. |
| [GFT](https://jobs.gft.com/go/spain/4411401/) | Official SuccessFactors RSS link | Backend Java requires 6+ years and Madrid/Bilbao office attendance three days; remote microservices role is senior. | No current A/B; RSS only exposes newest ten, so no exhaustive vacancy-count claim. |
| [Solera](https://www.solera.com/careers/) | Workday, robots-declared public sitemap | Old Sevilla Java job renders empty and is absent from current sitemap. Current Spanish sitemap cases are management. | No private Workday API or stale job integration. |
| [Sportradar](https://sportradar.com/empleo/?lang=es) | Official careers page | Automated request blocked; indexed senior Java examples do not prove current Sevilla junior/mid hiring. | No bypass; insufficient reliable feed evidence. |
| [Devo](https://www.devo.com/careers/open-positions/) | Official board | Automated access blocked; no verified live eligible Java posting recovered. | Respect block; no guessed ATS slug. |
| [Scopely](https://careers.scopely.com/us/en/search-results) | Phenom careers | Checked engineering examples are senior/staff; Barcelona office presence. | No current match; complex interface unjustified. |
| [SOLTEL](https://www.soltel.es/unete-a-nosotros/) | Corporate CV form | Employer's junior Java remote/Sevilla advertisement is promising (1–2 years), but official site exposes only general CV intake. | Manual lead; no individual live posting feed or vacancy-bound form confirmed. |
| [Tailor Hub / Manfred](https://www.getmanfred.com/en/job-offers/8375/tailor-hub-java-backend-developer-jun26) | Named employer's Manfred vacancy | Remote Spain, EUR 35–40k, but live page explicitly closed before this review. | Closed; not a discovery for current applications. |
| [Hiberus](https://www.hiberus.com/unete/ofertas-de-empleo/microservicios-java-developer) | Drupal public HTML | Java/microservices role; flexible office arrangements, no numeric minimum. Spain-wide remote eligibility not established. | U geography/application; no custom scraper without clearer benefit. |
| [Paradigma Digital](https://paradigmadigital.jobs.personio.com/) | Current Personio XML and old corporate Java page | Current XML contains one Agentic AI Architect role. Corporate Java/microservices page carries 2023 metadata. | Do not count older corporate page as current ATS vacancy. |
| [Digital Talent Agency](https://dtagency.tech/ofertas-de-empleo/) | WordPress links to portals | Official Java cards exist, but no maintained vacancy feed established; links point to third-party portals. | Insufficient freshness/application proof; avoid another custom connector. |
| [Métrica](https://empleo.metrica-global.com/) | Official recruiting host | Automated access returns 403. An unrelated metrica.com interiors careers site is not this employer. | Respect block and employer identity. |
| [Kairós DS](https://www.kairosds.com/es/job-offers) | Corporate page / Viterbit | Observed backend Java example asks 10+ years. | C; not evidence of early-career hiring. |
| [Ayesa Digital](https://ayesa-digital.com/ofertas-trabajo/oferta/analista-programador-a-java/26SP.271/) | Corporate vacancy HTML | Sevilla Java September example is senior. | Future/reference, not current A/B; distinguish digital business from unrelated engineering vacancies. |
| [Liferay](https://jobs.jobvite.com/liferay/job/otaAAfwx) | Jobvite public JobPosting | Software Engineer, 3+ years Java/Freemarker/SQL; visible Madrid, schema Spain; remote Spain not confirmed. | U geography, not remote by inference. |
| [Playtomic](https://playtomic.factorial.es/job_posting/senior-backend-engineer-325318) | Factorial | Senior role requires commuting to Madrid several times per month. | No current match from Sevilla. |
| [Metricool](https://careers.metricool.com/jobs) | Teamtailor custom host | One current role, Senior Security; no Java. | No source added. |
| [PrimeIT](https://www.primeit.es/en/carrers/jobs/java-software-engineer) | Corporate indexed job | Previously indexed remote Java page now 404. | Removed, not a live opportunity. |
| [Azertium IT](https://vacantes.azertiumit.com/jobs/7672607-programador-a-java) | Teamtailor public RSS | Indexed Java job returns 410; live RSS has Power Platform/other skills, not current Java. | No stale-vacancy ingestion. |
| [Second Window](https://second.plusats.com/publicarpeticiones/listado?PageSize=100) | Public PlusATS listing | Java role with 24 months experience requires Madrid hybrid. | D location; custom connector has poor marginal value. |
| [Hasten](https://www.grupohasten.com/grupo-hasten-unete/) | WordPress public job index | Checked Java examples are senior or fullstack with PHP/Angular required. | No verified current Java-backend A/B; no bespoke connector added. |
| [PSS](https://pss.tecnoempleo.com/trabajo.php) | Employer portal on Tecnoempleo | Public portal access blocked in this environment. | No bypass or inferred current openings. |
| [Infortec](https://empleo.infortec.net/jobs?subcategory=programming) | Bizneo, four observed programming pages | Three selected Java details: tech lead, incompatible location/Python specialist, junior with skill list but no concrete development duties. Another fullstack junior explicitly closed. | No A/B proved under existing policy. Keep manual review uncertainty; don't rewrite work-focus scoring to add employer count. |
| [SlashMobility](https://slashmobility.talentclue.com/es/job/117086846) | TalentClue | Java 1–2 years and remote label, but sparse duties. robots.txt disallows crawling `/`; public root redirects to ATS vendor. | Manual lead only; no scheduled crawling or CAPTCHA/access workaround. |
| [Revolut](https://www.revolut.com/careers/position/software-engineer-backend-530d3bfd-bdca-4390-8f8a-bc88ddc1eb51/) | Official careers HTML | Mid/Senior backend Java requires 4+ years; Spain remote eligibility differs by role. Platform Java example requires 7+. | Future/ambitious reference; do not copy broader mirror country lists into exact role. |
| [Amazon](https://www.amazon.jobs/en/search?base_query=java) | Official job search | Spain Java hits include Ring in Madrid; global results mix 5+ year runtime and architecture roles. | Big Tech reference; no specific current Sevilla/remote Java vacancy proved, no private API integration. |
| [Google](https://www.google.com/about/careers/applications/jobs/results/?location=Spain) | Official job search | Spain search shows Málaga engineer roles and remote-eligible Staff security. The checked applied-AI URL is removed. | Big Tech future/reference; Málaga attendance and staff level are not current eligibility. |
| [Adyen](https://careers.adyen.com/vacancies/6924441-software-engineer-java) | Official vacancy | Senior Java/PostgreSQL, Madrid; explicitly office-first, no remote-only roles. | Future/reference; no Sevilla-compatible current vacancy. |
| [Mozilla](https://www.mozilla.org/en-US/careers/listings/) | Official listings / RSS advertised | Remote Spain available for senior browser/security roles, not verified early Java backend. | Future/reference, no Java-role inference from company name. |

Further search-only leads (Apiux, Sandav, Krell, ITPartner, Nexion, Dedalus,
Ciklum, Feedzai, Aiven, Microsoft, Red Hat and Cognizant) are not counted as
exhaustively checked employers or integrated opportunities. Search discovery
alone did not establish a current public Java role satisfying location, duties,
experience and application requirements. No claim is made that these employers
have zero compatible positions.

## Real ingestion findings

1. Bizneo icon metadata uses HTML `title` attributes. Existing label-only parsing
   lost the EUR 30–50k salary, annual period and work-mode/location details.
   The opt-in structured layout reader preserves them and retains Spain alongside
   the city. Existing operations-profile Bizneo settings keep their old behavior.
2. Concrete vacancy bodies and minimum-requirement blocks retain paragraph/list
   boundaries; desirable frontend adjustments remain distinguishable from the
   backend role. Title filtering happens before the bounded detail budget;
   generic Software Engineer titles survive, JavaScript does not match Java.
3. Company boilerplate “empresa ... con más de 25 años de experiencia” was treated
   as candidate tenure. A narrow evidence-parser correction removes that company
   clause; actual candidate 3/4-year requirements remain. Weights are unchanged.
4. eXperience's `desarrollador-a-backend-java-madrid` has a Sevilla header but an
   explicit “Modalidad: Híbrido Madrid” duty. The latter takes priority; this is
   excluded instead of counted as an additional A.
5. SNGULAR's JobPosting uses `name`, malformed literal JSON newlines, and a
   description containing benefits rather than actual duties. The adapter checks
   metadata identity and reads visible role sections, retaining advanced Kafka,
   Spring, agent/AI and SDD requirements. No salary or experience minimum is invented.
6. lastminute.com, Flywire and Liferay illustrate correct uncertainty/rejection,
   not globally over-strict geography filtering. No country or language filter
   was relaxed. Existing ATS title/Java matching already admits ambiguous software
   titles when their complete vacancy supplies actual Java evidence.

No cross-employer project merging is performed without evidence. The three
eXperience current roles have different duties/requirements (bank integration,
IBM MQ/event-driven systems, ASO/APX). They are distinct advertised processes;
an undisclosed shared client cannot be ruled out. Provenance and original URLs
remain available; three URLs are not proof of three budgeted headcount positions.

## Delivery and production measurements

Recorded after CI, backup, deployment, controlled ingestion and repeat ingestion
in the companion delivery report. The investigation stops after these two useful
employer integrations because the remaining checked sources are blocked, stale,
geographically incompatible, too senior or lack enough role evidence to justify
another connector. This is a snapshot limitation, not a guaranteed monthly yield.
