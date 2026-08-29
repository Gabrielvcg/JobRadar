# Source Compliance

JobRadar starts with conservative source behavior:

- Prefer official APIs.
- Use public feeds only when allowed.
- Do not bypass CAPTCHA, login walls, rate limits, or access controls.
- Do not scrape sources such as LinkedIn or Indeed without an authorized API or explicit permission.
- Use fixed source base URLs; user-provided arbitrary URLs are not fetched.

## Arbeitnow

- Public API: `https://www.arbeitnow.com/api/job-board-api`
- Terms: `https://www.arbeitnow.com/terms`
- Robots: `https://www.arbeitnow.com/robots.txt`

Checked on 2026-06-27:

- The API responds without an API key.
- The terms include an API section saying the API is provided as-is/as-available and asks platforms using it to provide a link back to Arbeitnow.
- `robots.txt` does not disallow the API path. It disallows application paths such as `/jobs/companies/*/apply`.

The adapter uses the API endpoint only, applies request timeout and retry limits, waits between pages, and keeps a link back to Arbeitnow in the web UI.

## Remotive

- Public API: `https://remotive.com/api/remote-jobs`
- Documentation and terms: `https://remotive.com/api-documentation`

Checked on 2026-06-27:

- The API responds without an API key.
- The API response includes a legal notice requiring source attribution and links back to Remotive job URLs.
- The notice says job data does not need frequent requests and advises a maximum of 4 requests per day.

The adapter uses the API endpoint only, keeps Remotive job URLs as the outbound application links, filters for the configured technical profile before storing jobs, and uses a 360-minute minimum interval so the 30-minute cron does not exceed the advised request frequency.

## Remote OK

- Public API: `https://remoteok.com/api`
- Website: `https://remoteok.com`

Checked on 2026-06-27:

- The API responds without an API key.
- The first API response item includes a legal notice requiring a follow link back to the Remote OK job URL and source attribution.
- The notice says not to use the Remote OK logo without written permission.

The adapter uses the API endpoint only, keeps Remote OK job URLs as outbound application links, filters aggressively for the configured technical profile before storing jobs, and uses a 360-minute minimum interval so the 30-minute cron does not request this source too frequently.

## We Work Remotely

- Public RSS feeds: `https://weworkremotely.com/categories/remote-programming-jobs.rss`
- Website: `https://weworkremotely.com`

Checked on 2026-06-27:

- The category RSS feeds respond without an API key.
- The adapter uses RSS only and keeps We Work Remotely job links as outbound application links.
- The app uses a 180-minute minimum interval and local Java/Spring/JVM filters.

## Jobicy

- Public API: `https://jobicy.com/api/v2/remote-jobs`
- Documentation: `https://jobicy.com/jobs-rss-feed`

Checked on 2026-06-27:

- The API responds without an API key.
- The adapter uses documented API parameters such as `geo`, `industry`, `tag`, and `count`.
- The app uses a 360-minute minimum interval, waits between configured API requests, keeps Jobicy job URLs, and filters locally for Java/Spring/JVM fit.

## Himalayas

- Public API: `https://himalayas.app/jobs/api/search`
- Documentation: `https://himalayas.app/docs/remote-jobs-api`

Checked on 2026-06-30:

- The API responds without an API key.
- The adapter uses search parameters such as `q`, `country`, `worldwide`, `sort`, and `page`.
- The app uses a 360-minute minimum interval, waits between configured API requests, keeps Himalayas job URLs, and filters locally for Java/Spring/Kotlin fit.

## Fundación Adecco

- Public listing pages: `https://empleo.fundacionadecco.org/ofertas-empleo-discapacidad/informatica-sistemas`
- Public offer pages: `https://empleo.fundacionadecco.org/oferta-empleo/{slug}`
- Website: `https://empleo.fundacionadecco.org`
- Robots: `https://empleo.fundacionadecco.org/robots.txt`

Checked on 2026-07-04:

- `robots.txt` allows `/`, allows the public jobs RSS endpoint, and disallows only `?id_origen=` and `/index.php`.
- The configured Informática/Sistemas disability listing responds without login, API keys, or CAPTCHA and exposes public job links through server-rendered cards and `ItemList` structured data.
- The adapter uses only fixed public listing and offer URLs, stores only job summary/detail text needed for personal job tracking, keeps Fundación Adecco offer URLs, filters locally for Engineering's Java/backend/cloud/AppSec profile, excludes support/sales/administrative noise, and uses a 360-minute minimum interval with delays between listing and detail requests.

## Tecnoempleo

- Public listing pages: `https://www.tecnoempleo.com/ofertas-trabajo/discapacidad`, `https://www.tecnoempleo.com/ofertas-trabajo/certificado-discapacidad`, `https://www.tecnoempleo.com/ofertas-trabajo/java-discapacidad`
- Public offer pages: `https://www.tecnoempleo.com/{slug}/rf-{id}`
- Website: `https://www.tecnoempleo.com`
- Robots: `https://www.tecnoempleo.com/robots.txt`

Checked on 2026-07-04:

- The configured listing pages respond without login, API keys, or CAPTCHA and expose server-rendered job cards.
- Public offer pages include `JobPosting` structured data with title, company, location, date, and salary when available.
- `robots.txt` disallows internal/admin/AJAX/search-helper paths but does not disallow the configured public offer listing or detail paths used by the adapter.
- The adapter uses fixed public listing URLs, enriches only linked public offer pages, keeps Tecnoempleo offer URLs, filters locally for Engineering's disability-friendly backend/DevOps/systems/data/cybersecurity profile, excludes product, sales, admin, support, mobile, COBOL, and SAP noise, and uses a 360-minute minimum interval with delays between listing and detail requests.

## Por Talento / Inserta

- Public sitemap: `https://www.portalento.es/sitemap_ofertas.xml`
- Public offer pages: `https://www.portalento.es/Candidatos/Ofertas/Detalle/{slug}/{id}` and `https://www.portalento.es/Universitarios/Ofertas/Detalle/{slug}/{id}`
- Website: `https://www.portalento.es`
- Robots: `https://www.portalento.es/robots.txt`

Checked on 2026-07-04:

- The public offers sitemap responds without login, API keys, or CAPTCHA.
- The adapter filters sitemap URLs by technical slugs before opening detail pages, avoiding broad traversal of non-technical cleaning, retail, and services offers.
- Offer detail pages expose public `JobPosting` data and visible summary fields such as company, location, gross salary, publication date, and inscription deadline.
- `robots.txt` disallows some generated pagination query paths but does not disallow the public sitemap or detail pages used by the adapter.
- The adapter stores only job summary/detail text needed for personal job tracking, keeps Por Talento offer URLs, filters locally for Engineering's cybersecurity/backend fit, excludes security-guard/control-access/fraud/admin/sales noise, and uses a 360-minute minimum interval with delays between detail requests.

## Fundacion Randstad

- Public API: `https://apis.randstad.es/talent/offers/?bussinessId=9`
- Public search page: `https://www.randstad.es/fundacion-randstad/empleo-discapacidad/`
- Website: `https://www.randstad.es`

Checked on 2026-07-04:

- The Fundacion Randstad public offers endpoint responds without an API key and returns paginated JSON offers for disability-focused jobs.
- The adapter uses only the public offers API for business id `9`, keeps Randstad offer URLs, maps public salary, work modality, location, and experience metadata, and filters locally for Engineering's technical profile.
- The source is intentionally strict because most current offers are operations, cleaning, retail, or administrative roles; those are excluded before scoring.
- The app uses a 360-minute minimum interval and waits between API pages.

## Greenhouse Curated

- Public job board API: `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- Documentation: `https://developers.greenhouse.io/job-board.html`

Checked on 2026-07-02:

- Public board jobs respond without an API key for configured companies that expose a Greenhouse board.
- The adapter requests only configured company boards, keeps each company's Greenhouse job URL, tolerates missing public boards, and filters locally for Java/Spring/Kotlin/AppSec/DevSecOps and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company board requests.

## Lever Curated

- Public postings API: `https://api.lever.co/v0/postings/{company}?mode=json`
- Documentation: `https://hire.lever.co/developer`

Checked on 2026-07-02:

- Public postings respond without an API key for configured companies that expose a Lever board.
- The adapter requests only configured company boards, keeps hosted Lever job URLs, tolerates missing public boards, and filters locally for Java/Spring/Kotlin/AppSec/DevSecOps and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company board requests.

## Ashby Curated

- Public job postings API: `https://api.ashbyhq.com/posting-api/job-board/{company}`
- Documentation: `https://developers.ashbyhq.com/docs/public-job-posting-api`

Checked on 2026-07-02:

- Public job board postings respond without an API key for configured companies that expose an Ashby board.
- The adapter requests only configured company boards, keeps Ashby job URLs, includes public compensation data when available, tolerates missing public boards, and filters locally for Java/Spring/Kotlin/AppSec/DevSecOps and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company board requests.

## Workable Curated

- Public widget API: `https://apply.workable.com/api/v1/widget/accounts/{company}`
- Documentation: `https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page`

Checked on 2026-07-01:

- Public widget job listings respond without an API key for configured companies that expose a Workable board.
- The adapter requests only configured company boards, keeps Workable application URLs, deduplicates multi-location postings, tolerates missing public boards, and filters locally for Java/Spring/Kotlin and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company board requests.

## Recruitee Curated

- Careers Site API: `https://{company}.recruitee.com/api/offers/`
- Documentation: `https://docs.recruitee.com/reference/intro-to-careers-site-api`

Checked on 2026-07-01:

- Public careers offers respond without an API key for configured companies that expose a Recruitee careers site.
- The adapter requests only configured company boards, keeps Recruitee careers URLs, tolerates missing public boards, and filters locally for Java/Spring/Kotlin and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company board requests.

## Pinpoint Curated

- Public postings JSON: `https://{company}.pinpointhq.com/postings.json`
- Documentation: `https://help.pinpoint.support/en/articles/5878344-how-to-list-pinpoint-jobs-on-any-website`

Checked on 2026-07-01:

- Public postings JSON responds without an API key for configured companies that expose Pinpoint jobs.
- The adapter requests only configured company boards, keeps Pinpoint posting URLs, tolerates missing public boards, and filters locally for Java/Spring/Kotlin and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company board requests.

## Personio Curated

- Public XML feed: `https://{company}.jobs.personio.de/xml?language=en`
- Documentation: `https://support.personio.de/hc/en-us/articles/207576365-Integrate-jobs-from-Personio-into-your-website-via-XML`

Checked on 2026-07-01:

- Public XML feeds respond without an API key for configured companies that enable the Personio XML interface.
- The adapter requests only configured company feeds, keeps Personio job URLs, tolerates missing public feeds, and filters locally for Java/Spring/Kotlin and Spain/Europe/remote fit.
- The app uses a 360-minute minimum interval and waits between company feed requests.

## Adzuna

- Official API: `https://api.adzuna.com/v1/api/jobs/{country}/search/{page}`
- Documentation: `https://developer.adzuna.com/docs/search`

Checked on 2026-07-02:

- The search endpoint is an official API and requires `app_id` and `app_key`.
- The adapter does not scrape HTML. It only runs configured search requests, keeps Adzuna redirect URLs, filters locally for the active profile, and returns no jobs if credentials are not configured.
- The app uses a 360-minute minimum interval and waits between configured requests.

## Infoempleo

- Public listing pages: `https://www.infoempleo.com/trabajo/oferta-empleo/{term}/en_{province}/`
- Website: `https://www.infoempleo.com`
- Robots: `https://www.infoempleo.com/robots.txt`

Checked on 2026-07-03:

- The configured administrative/accounting listing pages for Sevilla and Almeria respond without login, API keys, or CAPTCHA.
- `robots.txt` disallows private, login, candidate, course/training, advanced-search, and several generated filter paths. The adapter uses only fixed public `/trabajo/oferta-empleo/...` listing URLs and does not request disallowed login, candidate, RSS, course, or arbitrary user-provided paths.
- The adapter stores only job-card summary data needed for personal job tracking, keeps Infoempleo outbound offer URLs, filters locally for Operations's administrative/accounting profile, and uses a 360-minute minimum interval with a delay between configured pages.

## Domestiko

- Public category pages: `https://www.domestiko.com/empleo/asistentes-personales/secretarios-y-secretarias-personales/{province}/`
- Public offer pages: `https://www.domestiko.com/empleo/oferta/{slug}/`
- Website: `https://www.domestiko.com`
- Robots: `https://www.domestiko.com/robots.txt`

Checked on 2026-07-03:

- The configured administration and secretarial category pages for Sevilla and Almeria respond without login, API keys, or CAPTCHA.
- `robots.txt` allows public pages and disallows uploads, user areas, search paths, and generated query filters such as `type`, `availability`, `languages`, and `updated`. The adapter uses only fixed category paths and their public offer links; it does not use the disallowed search or filter paths.
- Offer pages include public `JobPosting` structured data. The adapter reads that structured summary, keeps Domestiko offer URLs, filters locally for Operations's administrative/accounting profile, and uses a 360-minute minimum interval with a delay between page and offer requests.

## Trabajos.com

- Public category pages: `https://www.trabajos.com/ofertas-empleo/{category}/{province}`
- Website: `https://www.trabajos.com`
- Robots: `https://www.trabajos.com/robots.txt`

Checked on 2026-07-03:

- The configured accounting and purchasing category pages for Sevilla and Almeria respond without login, API keys, or CAPTCHA.
- `robots.txt` disallows advanced search, AJAX endpoints, and selected generated paths. The adapter uses only fixed public `/ofertas-empleo/...` category URLs and does not request disallowed advanced-search, AJAX, or arbitrary user-provided paths.
- The adapter stores only job-card summary data needed for personal job tracking, keeps Trabajos.com offer URLs, filters locally for Operations's administrative/accounting profile, excludes Portuguese-language requirements and warehouse/retail noise, and uses a 360-minute minimum interval with a delay between configured pages.

## JobToday

- Public search pages: `https://jobtoday.com/es/trabajos-{term}/{city}`
- Website: `https://jobtoday.com`
- Robots: `https://jobtoday.com/robots.txt`

Checked on 2026-07-03:

- The configured administrative/accounting pages for Sevilla and Almeria respond without login, API keys, or CAPTCHA and include structured `__NEXT_DATA__` job summaries.
- `robots.txt` disallows `/*_ext_*` for the default user agent and separately blocks selected known bots. The adapter uses fixed public search URLs and keeps only internal JobToday jobs with stable canonical `/es/trabajo/...` URLs; it does not ingest external `_ext_` paths, signed external redirect URLs, or arbitrary user-provided searches.
- The adapter stores only job summary data needed for personal job tracking, filters locally for Operations's profile, excludes Portuguese-language requirements, extra language requirements outside Spanish/English, retail/warehouse noise, and internship noise, and uses a 360-minute minimum interval with a delay between configured pages.

## Page Personnel

- Public search pages: `https://www.pagepersonnel.es/jobs/{term}/seville`
- Website: `https://www.pagepersonnel.es`
- Robots: `https://www.pagepersonnel.es/robots.txt`

Checked on 2026-07-03:

- The configured accounting and administrative pages for Sevilla respond without login, API keys, or CAPTCHA. Equivalent Almeria pages currently return no useful public listing, so they are not configured.
- `robots.txt` disallows internal search paths, application paths, salary/contract query filters, and deep faceted jobs paths. The adapter uses only fixed `/jobs/{term}/seville` pages without query filters, does not request application URLs, and ignores recommended off-location cards by default.
- The adapter stores only job-card summary data needed for personal job tracking, keeps Page Personnel job-detail URLs, filters locally for Operations's administrative/accounting profile, excludes senior/responsibility roles and off-location recommendations, and uses a 360-minute minimum interval with a delay between configured pages.

## Eurofirms

- Public listing pages: `https://jobs.eurofirms.com/es/es/trabajo/{path}`
- Website: `https://jobs.eurofirms.com`
- Robots: `https://jobs.eurofirms.com/robots.txt`

Checked on 2026-07-03:

- `robots.txt` does not disallow the public listing paths used by the adapter and publishes the site sitemap.
- The configured pages respond without login, API keys, or CAPTCHA and include server-rendered `article.psf-offer` cards with stable detail links, order codes, locations, salary snippets, and publication dates.
- The adapter uses only fixed Sevilla/Almeria listing URLs, stores only job-card summary data needed for personal job tracking, filters locally for Operations's administrative/customer-service profile, excludes warehouse, retail, promoter, Portuguese-language, and senior/responsibility roles, and uses a 360-minute minimum interval with a delay between configured pages.

## Talent.com

- Public listing pages: `https://es.talent.com/jobs?k={term}&l={city}`
- Public detail pages: `https://es.talent.com/view?id={id}`
- Website: `https://es.talent.com`
- Robots: `https://es.talent.com/robots.txt`

Checked on 2026-07-03:

- The configured Sevilla and Almeria listing pages respond without login, API keys, or CAPTCHA and include server-rendered job cards with stable `/view?id=...` links.
- `robots.txt` disallows internal API, redirect, conversion, pixel, AJAX, and generated search paths, but it does not disallow the fixed `/jobs?...` listing pages or `/view?id=...` detail pages used by the adapter.
- The adapter uses only fixed listing URLs, optionally enriches from public detail `JobPosting` JSON-LD when present, keeps Talent.com outbound job URLs, filters locally for Operations's profile, excludes duplicate aggregators and off-location pages, and uses a 360-minute minimum interval with delays between listing and detail requests.
- Production note: the VPS returned repeated `403 Forbidden` responses for these listing pages on 2026-07-03, so the source remains disabled in `sources.yml` until a stable allowed access path is available.

## Bizneo-Powered Portals

- Faster public listings: `https://jobs.faster.es/jobs`
- IMAN public listings: `https://empleo.imancorp.es/jobs`
- Grupo Crit public listings: `https://jobs.grupo-crit.com/jobs`
- Robots: `https://jobs.faster.es/robots.txt`, `https://empleo.imancorp.es/robots.txt`, `https://jobs.grupo-crit.com/robots.txt`

Checked on 2026-07-03:

- The configured portals respond without login, API keys, or CAPTCHA and expose public job cards under `/jobs/...`.
- Their `robots.txt` files disallow `/admin` and do not disallow public job listing or detail pages.
- The adapter uses only fixed native filter URLs for Sevilla/Almeria and administrative/accounting/customer-support subcategories, stores only job summary/detail text needed for personal job tracking, keeps outbound application URLs to each portal, excludes Portuguese/French-language requirements and warehouse/retail/senior noise, and uses a 360-minute minimum interval with delays between listing and detail requests.

## Manpower

- Website: `https://www.manpower.es`
- Robots: `https://www.manpower.es/robots.txt`

Checked on 2026-07-03:

- Public pages include structured job details, but `robots.txt` disallows `/` for the generic `User-agent: *`.
- The source remains disabled in `sources.yml`; it should not be enabled unless Manpower provides explicit permission, an authorized API, or a clearer allowed integration path.
