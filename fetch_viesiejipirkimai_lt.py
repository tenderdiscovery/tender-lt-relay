"""
fetch_viesiejipirkimai_lt.py

Detects genuinely new DriveLock/idgard-relevant tenders on Lithuania's
CURRENT national public procurement information system (CVP IS), live at
https://viesiejipirkimai.lt/ (operated by Viesuju Pirkimu Tarnyba / VPT, the
Lithuanian Public Procurement Office, built on the "European Dynamics ePPS"
e-procurement platform), dedupes against the existing master dataset, and
shapes new records into the same schema used for the other sources
(ted_shaped_final.json), tagged with "source": "viesiejipirkimai.lt".

DILIGENCE SUMMARY - A REAL, SURPRISE PLATFORM MIGRATION FOUND (all of the
below live-verified 2026-11-03, not assumed from the task brief's own
starting guess):

The task brief's working assumption was that Lithuania's platform is "CVP IS
at cvpp.eviesiejipirkimai.lt". That hostname DOES exist, DOES return HTTP 200,
and DOES have a genuinely open, anonymous, plain-GET search/listing (a
"<form action="/" method="get">" with Query/SelectedTextFilter/NoticeTypeIds/
PublicationTypeIds/Cpvs/PublishedFromDate/PublishedToDate/IncludeExpired/
PageSize/PageNumber params, no login, no API key, no robots.txt restriction
at all - confirmed GET https://cvpp.eviesiejipirkimai.lt/robots.txt -> HTTP
404, not a blanket block). HOWEVER, live date-distribution testing (not
assumed) found this listing is NOT current: sorting by publication date
descending with IncludeExpired=true, the newest entry found anywhere in the
system is 2026-08-27 (a single stray "Skelbimo kodas: 2026-635103" row,
itself an outlier against the surrounding "2024-699998"-style code sequence,
most likely a late correction to an old record rather than fresh content);
per-year filtered queries show 2025 return ZERO records ("Skelbimų
nerasta") and 2026 (through today) returns exactly ONE. This is not a
network/reachability problem (every request returned clean HTTP 200 with
real HTML) - it is a DEAD/ARCHIVE-ONLY data source: a websearch (see below)
confirmed Lithuania migrated its ENTIRE live CVP IS to a brand-new platform,
https://viesiejipirkimai.lt/, on 2024-12-01, with the old cvpp.
eviesiejipirkimai.lt host explicitly repurposed as a read-only archive for
pre-2024-12-01 notices plus a narrow post-migration residual function
(contract/EBVPD publication by contracting authorities) - confirmed via
multiple independent Lithuanian sources (propirkimai.lt, pirkimai365.lt, and
VPT's own https://vpt.lrv.lt/en/cpp-is/important-information-about-new-cpp-is-cvp-is/
page) found via web search, not just one blog's claim. Building a fetcher
against cvpp.eviesiejipirkimai.lt would have silently returned near-zero new
notices forever - a classic "the old URL still works, so it looks fine,
but it is not where reality lives anymore" trap, directly analogous to this
project's own recent Belgium/Romania production-reachability lessons, just
a data-freshness trap instead of a network trap. This fetcher therefore
targets the REAL current platform, viesiejipirkimai.lt, instead.

robots.txt (live-confirmed): GET https://viesiejipirkimai.lt/robots.txt
redirects (HTTP 302, "NSX LB" load-balancer banner) straight back to the
homepage shell - i.e. no robots.txt file exists at this host at all (same
"absence is not a blanket-block disqualifier" reasoning as e-licitatie.ro's
plain 404). No blanket Disallow: / of any kind was found anywhere on this
host.

Software/platform: "European Dynamics" ePPS (the literal page title is
"European Dynamics - Centrine viesuju pirkimu informacine sistema") - the
same vendor/platform family used by several other EU member states' national
e-procurement portals (e.g. Cyprus) - htmx-enhanced server-rendered JSP-style
pages under a "/epps/" context path, NOT a JS-bundle SPA (no reverse
engineering of a minified bundle was needed here, unlike udbud.dk/
publicprocurement.be/e-licitatie.ro in this same codebase - the real
search/listing endpoints were found directly in plain server-rendered HTML).

THE REAL SEARCH/LISTING MECHANISM (live-verified, works from a bare,
cookie-less, never-logged-in client, repeatedly):
    GET https://viesiejipirkimai.lt/epps/viewCFTSAction.do
        ?type=cftFTS
        &title=<free-text substring query, optional>
        &publicationFromDate=<DD/MM/YYYY, optional>
        &publicationUntilDate=<DD/MM/YYYY, optional>
        &d-<TABLE_ID>-p=<1-based page number>
-> HTTP 200, plain server-rendered HTML, a <table id="T01"> of up to 10 rows
per page (page size is NOT controllable via the documented "<tableId>_ps"
query param mechanism found in this platform's own common.js - live-tested
and found to have NO EFFECT, still returns exactly 10 rows regardless -
treated as a confirmed, not assumed, hard page-size-10 reality, same
"real, measured server-side cap" treatment as e-licitatie.ro's 3000-row
cap). This is the exact same URL the human-facing "Isplestine paieska"
(advanced search) form at /epps/prepareAdvancedSearch.do?type=cftFTS POSTs
to - live-tested both as a GET (with all params on the query string) and as
the form's own POST, both work identically and BOTH succeed with zero
cookies, zero session state, zero login of any kind, from a fresh client
every time. TABLE_ID (the "d-<N>-p=" pagination parameter's numeric ID, seen
as "3680175" throughout this build's own testing) is NOT hard-coded by this
fetcher - it is read fresh from each response's own embedded pagination
links via TABLE_ID_RE, the same "don't trust a one-time-observed ID to stay
constant" defensiveness already used by fetch_pmp_lu.py's orgAcronyme
handling, in case this platform ever re-renders the table under a different
internal ID.

publicationFromDate/publicationUntilDate ARE live-confirmed to genuinely
narrow the result set server-side (not silently ignored) - a same-day query
for a real weekday (2026-11-03) returned 91 total matches; the preceding
Sunday (2026-11-01) and Saturday (2026-10-31) both returned 0 - this
platform, like Romania's e-licitatie.ro, evidently does not meaningfully
publish new calls for tender on weekends. This was independently
re-confirmed across a real 60-day live measurement during this build (see
MEASUREMENT NOTE below), not a one-off spot check.

SERVER-SIDE "title" FREE-TEXT FILTER IS A LOOSE SUBSTRING MATCH, used here
ONLY to confirm the mechanism works and to spot-check individual KEYWORDS
during diligence (e.g. "saugumo" standalone -> 238 total matches, "licencij"
-> 873, "kibernetinio saugumo" -> 70) - it is NOT used as this fetcher's
PRIMARY discovery mechanism, for the same reason fetch_udbud_dk.py/
fetch_e_licitatie_ro.py do not rely on their own platforms' loose/
server-side text search as the primary channel: running ~95 separate
per-KEYWORDS-entry server queries every run (and then still needing to
paginate each one up to its own total) would be far more requests than one
clean day-chunked bulk walk, and would still need the SAME precise local
KEYWORD_PATTERN re-check anyway (loose substring matching alone is not
trustworthy for word-boundary precision - "licencij" matching 873 rows is
itself proof of how loose it is). This fetcher instead walks every "cft"
("call for tenders") row published in the --days window (title param
omitted entirely, only the date-range params set) and applies the EXACT
same precise, word-boundary KEYWORD_PATTERN regex locally to title +
the row's own short "Informacija" tooltip description that every other
source in this codebase uses - the "bulk collect, then precise client-side
filter" shape already used by fetch_pmp_lu.py/fetch_udbud_dk.py/
fetch_e_licitatie_ro.py.

ROW SHAPE (live-verified, 13 <td> columns per row, confirmed via direct
HTML inspection across ~3400 real rows collected during this build's own
60-day measurement): #, Pavadinimas (title, as an <a href="/epps/cft/
prepareViewCfTWS.do?resourceId=N">), Pirkimo ID (same N, confirmed
consistently matching the href's resourceId in every sample checked),
PV (buyer/"Pirkimo vykdytojas" name, plain text only - no buyer-org-ID link
at this list level), Informacija (an <img title='...'> tooltip holding a
real, often-substantial free-text description - NOT the same text as the
title - used here for keyword matching alongside the title, at ZERO extra
request cost), Paskelbimo data (publication date+time, Java
"EEE MMM dd HH:mm:ss zzz yyyy" toString format, e.g. "Tue Nov 03 19:35:47
EET 2026"), Pasiulymu pateikimo terminas (submission deadline, same date
format), Pirkimo budas (procedure type, e.g. "Atviras konkursas"/"Skelbiama
apklausa"), Statusas (lifecycle status, e.g. "Pasiulymu teikimas"),
Skelbimas PDF formatu (a genuinely anonymous PDF download link - see below),
Laimejimo nustatymo data (award date, usually empty for open tenders),
Numatoma bendra pirkimo verte (an estimated-value NUMBER in this list
row, but in a DIFFERENT, less reliable decimal format than the detail
page's own explicitly-EUR-labelled field - the detail page's value is used
instead, see below), Zingsnis (an internal workflow "step" ordinal).

A REAL, LIVE-FOUND SCOPE BOUNDARY (not a bug): the SAME table also mixes in
"PMC" (market-consultation / "Rinkos konsultacija", a pre-tender RFI-style
notice type) rows, distinguishable ONLY by their title column linking to
"/epps/pmc/viewPmc.do?resourceId=N" instead of "/epps/cft/
prepareViewCfTWS.do?resourceId=N" (no separate "notice type" column exists
at the list level to tell them apart any other way - confirmed by directly
inspecting a real page's raw row chunks: both row kinds share the exact
same 13-column shape, cft rows have both a prepareViewCfTWS link AND a
downloadNoticeForAdvSearch PDF link, pmc rows have neither). This fetcher
DELIBERATELY SCOPES to "cft" rows only (genuine calls for tender, the data
this project actually wants to alert on) and skips pmc rows entirely - same
accepted, explicitly-logged scope-limiting judgment call as
fetch_pmp_lu.py's "AllCons&EnCours only, no award/PIN notices" decision and
fetch_e_licitatie_ro.py's "C-Notice channel only, other channels not
pursued" decision. A rough per-page count of skipped pmc rows is printed
during a run so a future maintainer can see the scope of what is excluded.

DETAIL PAGE (live-verified, 2026-11-03, genuinely anonymous - no login
redirect of any kind, unlike the document-download endpoint below):
    GET https://viesiejipirkimai.lt/epps/cft/prepareViewCfTWS.do?resourceId={id}
-> HTTP 200, a <dl> definition list containing (live-confirmed field labels,
Lithuanian originals kept here verbatim since that is what this fetcher's
regexes match against): "Aprasymas:" (a real, often multi-sentence free-text
description - in one live sample this was substantially richer than the
list row's own tooltip, e.g. a Lithuanian Parliament notice whose detail
description named "Claude seimos dirbtinio intelekto programos licencijos"
(Claude-family AI program licenses) and "ChatGPT seimos..." side by side -
genuinely current, varied, real content, not placeholder/test data),
"BVPZ kodai:" (one or more 8-digit CPV codes, each followed by its own
human-readable title and a <br/> - ALL codes are captured here via a
findall, unlike several sibling sources in this codebase that can only
capture a single principal code), "Numatoma verte (EUR):" (an explicitly
EUR-denominated estimated value, Lithuanian decimal-comma format, e.g.
"37190,08." - parsed and the trailing period stripped), "Pirkimo budas:"
(procedure type, duplicates the list row's own column but kept from the
detail page for consistency with the other detail-sourced fields),
"Sutarties trukme menesiais arba metais, isskyrus pratesimus:" (contract
duration, free text like "1 months" - the leading integer is extracted),
"Pirkimo vykdytojo pavadinimas:" (buyer name, this time as a link to
/epps/prepareViewCAOrganisation.do?id=N - this buyer-org ID is NOT available
at the list-row level at all, only here), and a "Pirkimu suvestines nuoroda:"
onclick="viewPlan('N')" link whose VISIBLE text is the human-facing
procurement reference in the "1002/2830/5004685"-style format used
throughout VPT's own public communications - captured here as
contractFolderId, a genuinely platform-native reference distinct from the
internal numeric resourceId.

BUYER ORGANISATION PAGE (live-verified, anonymous, best-effort):
    GET https://viesiejipirkimai.lt/epps/prepareViewCAOrganisation.do?id={buyerOrgId}
-> a <dl> with "Pirkimo vykdytojo tipas:" (a single combined CA-type-and-
/or-activity free-text value, e.g. "c. Gynyba" i.e. "c. Defence" - mapped
here to buyerActivity, since the observed values look like TED-style main-
activity sector labels, not legal-form labels; no separate legal-form field
was found) and "El. pastas:" (a real buyer contact e-mail, e.g.
"name@mil.lt" in the one live sample checked in full). This page was NOT
found to be populated with the same field set for every single buyer
(a second, different buyer ID spot-checked during this build did not show
the same "tipas:"/"El. pastas:" fields in a quick single grep - not
exhaustively root-caused further given this build's time budget; treated
as a best-effort enrichment step, not a guaranteed one) - buyerEmail and
buyerActivity are therefore populated opportunistically (None if the labels
are not found on a given buyer's page), an honest "best-effort, not
universally present" gap, same category as several other sources' partial-
coverage fields in this codebase. This extra GET is only made for actual
KEYWORD_PATTERN hits (one extra request per hit, same cost profile as
fetch_pmp_lu.py's CPV-enrichment-only-for-hits pattern), not for every row.

DOCUMENTS / NOTICE PDF (live-verified, two DIFFERENT download endpoints with
TWO DIFFERENT auth outcomes - an important, easy-to-get-backwards distinction
found only by testing both explicitly):
- GET https://viesiejipirkimai.lt/epps/cft/downloadNoticeForAdvSearch.do?resourceId={id}
  -> HTTP 200, Content-Type: application/pdf, a genuinely anonymous download
  of the official published notice PDF (filename e.g. "{id}_Nacionalinis
  skelbimas apie pirkima...pdf") - NO login redirect, confirmed via a plain
  HEAD request with zero cookies. Used here as documentsUrl - a real,
  stable, publicly fetchable link to the authoritative notice document,
  richer than several sibling sources' "always None" documentsUrl gap.
- GET https://viesiejipirkimai.lt/epps/cft/downloadCompetition.do?resourceId={id}
  (the full tender-dossier/competition-documents bundle, as opposed to just
  the published notice) -> HTTP 302 to /cas/login?service=... - i.e. this
  ONE specific endpoint DOES require a real CAS login, consistent with the
  web-search finding that an account is needed to "submit a bid, ask a
  question, or receive notifications" on the new portal, but NOT for
  "the procurement list, notices and procurement summaries" themselves
  (which are explicitly described as open, no-account-needed, by VPT's own
  public communications). This fetcher NEVER calls downloadCompetition.do -
  only the genuinely anonymous downloadNoticeForAdvSearch.do - so this login
  gate is irrelevant to this fetcher's own operation, documented here only
  so a future maintainer does not confuse the two endpoints.

NOTICE DATE FORMAT - A REAL, LIVE-CAUGHT BUG DURING THIS BUILD'S OWN LOCAL
TESTING (not a hypothetical): the list row's publicationDate/deadline
column text comes back in a server-locale-dependent shape that is NOT fixed
- this build's very first, header-less exploratory curl requests saw the
English Java "EEE MMM dd HH:mm:ss zzz yyyy" toString format (e.g. "Tue Nov
03 19:35:47 EET 2026"), but this fetcher's own real request headers
(Accept-Language: lt-LT,lt;q=0.9,en;q=0.8 - a deliberate, reasonable choice
for a Lithuanian source) make the SAME server render the SAME column as a
plain "DD/MM/YYYY HH:MM:SS" string instead (e.g. "03/11/2026 19:35:47").
A first draft of this fetcher only handled the English shape and silently
produced publicationDate=None/deadline=None for every single row when
actually run with its own real headers - caught via this build's own live
scratch-dataset test (Stage 3), not assumed away. Both shapes are parsed
here (LT_DATE_RE tried first, JAVA_DATE_RE as a fallback), discarding
time-of-day in both cases (every other source in this codebase's
publicationDate/deadline fields are date-only).

KEYWORDS: starts from the exact same German/English list every other source
in this codebase uses verbatim (see fetch_pmp_lu.py/fetch_udbud_dk.py), with
Lithuanian translations of the core, concrete, translatable concepts ADDED
on top (brand names are NOT translated, same reasoning as every other
multilingual source in this codebase) - judged necessary, not optional:
Lithuanian is a Baltic language with no lexical overlap with German/English
compound security terminology, same "non-English/non-German source needs
local-language additions" pattern as fetch_udbud_dk.py's Danish additions
and fetch_e_licitatie_ro.py's Romanian additions.

LIVE TEST RESULT (2026-11-03, this build's own measurement - see MEASUREMENT
NOTE below for the full methodology): across a real 60-day day-chunked bulk
collection (3416 unique raw "cft" rows, 2026-09-05 through 2026-11-03), the
precise KEYWORD_PATTERN (base list + Lithuanian additions) matched 7 records
total: a central election commission's cybersecurity-risk/business-
continuity-plan review (VRKIS system), a genocide-research-centre
cybersecurity audit, a shared-services centre's "SIEM and vulnerability
management" tooling procurement (a strong, precise product-category match),
a water utility's SIEM/event-management license renewal (equally precise),
a government building's facility-renovation notice that only matched
because its buyer's full name happens to contain "Nacionalinis kibernetinio
saugumo centras" (National Cybersecurity Centre) - a clear FALSE POSITIVE,
reported honestly rather than silently counted as a real hit - the Bank of
Lithuania's "IT security and project-management competency services", and
a national broadcaster's "password management software" procurement.
Reported honestly as a thin-but-genuine signal with a mix of precise
product-category matches, a plausibly-adjacent match, and one honest false
positive - same "thin, mostly-generic signal, not padded" honesty standard
as fetch_e_licitatie_ro.py's own Romanian finding, though with a notably
higher proportion of genuinely precise matches here (2 of 7 are exact
SIEM/vulnerability-management product-category fits) than that source's.

MEASUREMENT NOTE (methodology for the --days defaults below): a day-chunked
bulk collection was run live during this build (2026-11-03, days_ago 0
through 59, ~60 individual day-level HTTP GETs plus their own pagination
follow-ups, several hundred HTTP requests total across the full diligence
and measurement pass), yielding 3416 unique raw "cft" rows and the
KEYWORDS hit-count distribution above (1 hit within 10 days, 4 within 20,
5 within 40, 7 within 60). UNLIKE fetch_e_licitatie_ro.py/
fetch_pmp_lu.py's own measurements, this did NOT show a clear plateau - this
platform has only existed since 2024-12-01 (see migration note above) and
daily "cft" row volume was measured as remarkably STABLE and dense all the
way back to day ~65 (roughly 60-100 rows on an ordinary weekday, 0 on every
Saturday/Sunday observed, no sign of a thinning historical tail the way a
multi-year archive would show) - i.e. there is no natural "this is where it
goes quiet" cutoff to find within the 60-90 day range this build had time to
measure, unlike Luxembourg's sparse multi-year backlog. --days 3 (fetch
default) matches every other source's convention. --days 90 (backfill
default, see backfill_viesiejipirkimai_lt.py) was chosen as a PRACTICAL
cutoff consistent with fetch_e_licitatie_ro.py's own 90-day backfill choice,
NOT because a plateau was found here - this is an honest difference from
that source's own stated reasoning, flagged explicitly so a future
maintainer does not assume this 90 was derived the same way.

Known limitations (live-verified, not inferred):
- "Rinkos konsultacija" (PMC/market-consultation) rows are explicitly out of
  scope (see above) - a real, accepted scope limitation, not a bug.
- noticeType is always the fixed value "lt-cft" - no granular EU notice-type
  code (contract notice vs. PIN vs. award vs. correction) was found exposed
  anywhere in this endpoint's list or detail payload, unlike e.g.
  fetch_udbud_dk.py's formulartypeKode - an honest, coarser-than-usual gap
  for this source.
- correctionKey is the row's own resourceId (same "best available join key,
  not exhaustively verified" honesty as fetch_pmp_lu.py's refCons).
  isCorrectionHint is always False - no distinct correction/amendment notice
  TYPE was found in this fetcher's "cft" channel (the old cvpp.
  eviesiejipirkimai.lt portal DID have a distinct "Skelbimas apie pakeitima"
  (amendment notice) NoticeTypeId, but that portal is the dead archive this
  fetcher deliberately does NOT use - see migration note above; the new
  platform's equivalent, if any, was not found within this build's time
  budget).
- buyerEmail/buyerActivity are best-effort only (see "BUYER ORGANISATION
  PAGE" above) - populated when found, None otherwise, NOT confirmed present
  for every buyer.
- buyerLegalType is always None - no field distinct from the combined
  "tipas" (mapped to buyerActivity) value was found.
- lotName/awardedTo/performanceLocation/accelerated: none of these were
  found anywhere in either the list row or the detail page - always None,
  same honest-gap treatment as several sibling sources' documented missing
  fields (a "NUTS kodai:" field DOES exist on the detail page but was empty
  in every single sample checked during this build - not populated here
  given zero live-observed non-empty examples to confirm the right parsing
  shape against).
- This fetcher's own request pattern (one GET per paginated page per
  calendar day in the --days window, typically 7-12 pages/weekday, 0 on
  weekends, plus one detail-page GET and one best-effort buyer-page GET per
  actual keyword hit) has NOT been stress-tested at full production
  cron-job scale for a WAF/rate-limit response - across several hundred
  requests made live during this build's own 60-day measurement pass plus
  diligence, zero 403s/429s/WAF interstitials/CAPTCHAs of any kind were
  observed, but this is the same "not yet proven at full unattended
  production scale" caveat every sibling source in this codebase carries.

PRODUCTION REACHABILITY CAVEAT (carried over from this project's own very
recent, very real lesson with Belgium/Romania today, 2026-11-03): everything
above was verified from THIS BUILD SANDBOX only. This project has now
repeatedly found that sandbox-level HTTP reachability does NOT guarantee
reachability from the actual Strato production server (a confirmed hard
TCP-connect-level network block for Belgium, and two Romanian hostnames
unreachable even from a build sandbox with the identical failure signature).
viesiejipirkimai.lt was NOT observed to exhibit any connect-level failure at
any point during this build's extensive live testing (every single request
across the full diligence and 60-day measurement pass returned a clean HTTP
response) - but this has NOT been confirmed reachable from the real Strato
production server and MUST be live-tested there (e.g. a raw
`curl -4 -v https://viesiejipirkimai.lt/epps/home.do` from an SSH session on
the production box) before this fetcher is trusted to run on a cron schedule
in production - do not assume sandbox success implies production success.

Usage:
    python3 fetch_viesiejipirkimai_lt.py [--days N] [--out new_notices_found_viesiejipirkimai_lt.json] [--dataset ted_shaped_final.json]
"""
import argparse
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SEARCH_URL = "https://viesiejipirkimai.lt/epps/viewCFTSAction.do"
DETAIL_URL_TMPL = "https://viesiejipirkimai.lt/epps/cft/prepareViewCfTWS.do?resourceId={id}"
NOTICE_PDF_URL_TMPL = "https://viesiejipirkimai.lt/epps/cft/downloadNoticeForAdvSearch.do?resourceId={id}"
BUYER_ORG_URL_TMPL = "https://viesiejipirkimai.lt/epps/prepareViewCAOrganisation.do?id={id}"

SOURCE_NAME = "viesiejipirkimai.lt"
PUBNUM_PREFIX = "LT"
PAGE_SIZE = 10  # hard, measured reality - the "<tableId>_ps" page-size param has no effect (see module docstring)
MAX_PAGES_PER_DAY = 25  # safety net - busiest live-observed weekday during this build's 60-day measurement was ~13 pages

# Same full German/English KEYWORDS list as fetch_pmp_lu.py / fetch_udbud_dk.py /
# every other European source in this codebase - copied verbatim, not shortened -
# PLUS Lithuanian additions of the core, concrete, translatable concepts (see
# module docstring for why these are necessary here, not optional).
KEYWORDS = [
    "DriveLock", "idgard", "BitLocker", "Sealed Cloud", "HYPERSECURE",
    "Endpoint Security", "Datenräume", "Wechseldatenträger",
    "virtueller Datenraum", "Festplattenverschlüsselung", "IGEL", "IGEL OS",
    "Managed File Transfer", "ESET Endpoint", "SIEM/SOC", "File Share",
    "Virtual Data Room", "Removable Media Control", "Full Disk Encryption",
    "Secure File Transfer", "Secure File Exchange", "Application Control",
    "BitLocker Management", "USB Control", "USB-Kontrolle",
    "Schnittstellenkontrolle", "Port Control", "Application Allowlisting",
    "Endpoint Protection", "Endpoint Encryption", "Vulnerability Management",
    "Security Awareness", "Key Recovery", "Wechseldatenträgerkontrolle",
    "Application Behavior Control", "Verschlüsselung von USB-Datenträgern",
    "Encryption to Go", "Microsoft Defender Management",
    "Windows Firewall Management", "Local User and Group Management",
    "Security Configuration Management", "Endpoint Compliance",
    "Security Event Manager", "Agentic AI Control", "Hypersecure Platform",
    "sicherer Datenaustausch", "verschlüsselter Datenaustausch",
    "Filesharing", "File Sharing", "Secure Collaboration",
    "sichere externe Zusammenarbeit", "Gremienportal",
    "sichere Vorstandskommunikation", "verschlüsselter E-Mail-Anhang",
    "Secure Mail", "sichere Dateiübertragung", "Company Drive",
    "Datenhoheit", "Datensouveränität", "digitale Souveränität",
    "DSGVO-konforme Cloud", "Datenhaltung in Deutschland", "Betreiberzugriff",
    "Zero-Knowledge", "Gastbenutzer", "SharePoint-Alternative",
    "Dropbox-Alternative", "Common Criteria", "Datenresidenz",
    "Hosting in Deutschland", "Hosting in der EU", "regulierte Branche",
    "Awareness-Maßnahme", "Awareness-Schulung", "Application Whitelisting",
    "Sicherheitsbewusstsein",
    # Lithuanian additions (core concepts only - brand names stay
    # untranslated) - live-measured 2026-11-03 against 3416 real "cft" row
    # titles+descriptions (60 days): "kibernetinio saugumo" and a generic
    # password-management phrase actually matched real rows (see module
    # docstring's LIVE TEST RESULT); the rest matched nothing in this sample
    # but are kept anyway, same reasoning as every other source's
    # local-language list (a near-zero hit rate during one build's
    # measurement window does not prove a term will never match a future
    # notice).
    "kietojo disko šifravimas", "visiškas disko šifravimas", "disko šifravimas",
    "duomenų šifravimas", "šifruotas duomenų mainai", "šifruoti duomenų mainai",
    "saugus failų perdavimas", "saugus failų bendrinimas", "saugus failų mainai",
    "virtuali duomenų saugykla", "virtuali duomenų patalpa",
    "keičiamųjų laikmenų kontrolė", "USB kontrolė", "USB įrenginių kontrolė",
    "galinio taško sauga", "galutinio taško sauga", "galinio įrenginio apsauga",
    "programų valdymo kontrolė", "programų leidimų kontrolė",
    "kibernetinio saugumo", "informacijos saugumo valdymo sistema",
    "skaitmeninis suverenitetas", "duomenų suverenitetas",
    "duomenų rezidavimas", "duomenų rezidencija",
    "saugumo sąmoningumo mokymai", "saugumo sąmoningumas",
    "slaptažodžių valdymo", "slaptažodžių saugojimo",
    "antivirusin",
]
KEYWORD_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b", re.IGNORECASE)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.8",
}

TABLE_ID_RE = re.compile(r'd-(\d+)-p=')
TOTAL_RE = re.compile(r'<strong>(\d+)</strong>\s*rezultatai')
TBODY_RE = re.compile(r'<tbody>(.*?)</tbody>', re.S)
ROW_SPLIT_RE = re.compile(r'(?=<tr>\s*<td>\d+</td>)')
CFT_LINK_RE = re.compile(r'cft/prepareViewCfTWS\.do\?resourceId=(\d+)"[^>]*>(.*?)</a>', re.S)
TD_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.S)
INFO_TITLE_RE = re.compile(r"title='([^']*)'")
JAVA_DATE_RE = re.compile(r'\w{3} (\w{3}) (\d{1,2}) \d{2}:\d{2}:\d{2} \S+ (\d{4})')
# LIVE-FOUND LOCALE QUIRK (not present in this fetcher's earliest manual
# probing, which happened to be done without an explicit Accept-Language
# header): with Accept-Language set to "lt-LT,lt;q=0.9,en;q=0.8" (this
# fetcher's own, deliberately Lithuania-appropriate header), the server
# renders Paskelbimo data/Pasiulymu pateikimo terminas in a COMPLETELY
# DIFFERENT, locale-dependent shape - plain "DD/MM/YYYY HH:MM:SS" - NOT the
# English Java toString format seen during this build's very first,
# header-less exploratory curl requests. Both shapes are handled here
# (LT_DATE_RE tried first, since it is what this fetcher's own real request
# headers actually produce in practice) - a genuine, live-discovered
# locale-dependent-rendering gotcha, not a hypothetical.
LT_DATE_RE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{2}:\d{2}:\d{2}')

CPV_BLOCK_RE = re.compile(r'BVPŽ kodai:.*?<dd[^>]*>(.*?)</dd>', re.S)
CPV_CODE_RE = re.compile(r'(\d{8})-')
VALUE_BLOCK_RE = re.compile(r'Numatoma vertė \(EUR\):.*?<dd[^>]*>(.*?)</dd>', re.S)
DESC_BLOCK_RE = re.compile(r'Aprašymas:.*?<dd[^>]*>(.*?)</dd>', re.S)
PROCEDURE_BLOCK_RE = re.compile(r'Pirkimo būdas:.*?<dd[^>]*>(.*?)</dd>', re.S)
DURATION_BLOCK_RE = re.compile(r'trukmė mėnesiais arba metais.*?<dd[^>]*>(.*?)</dd>', re.S)
BUYER_ORG_ID_RE = re.compile(r'prepareViewCAOrganisation\.do\?id=(\d+)')
PLAN_REF_RE = re.compile(r"viewPlan\('\d+'\)\">\s*([^<]+?)\s*</a>")

BUYER_ACTIVITY_RE = re.compile(r'tipas:\s*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>', re.S)
BUYER_EMAIL_RE = re.compile(r'El\. paštas:\s*</dt>\s*<dd[^>]*>\s*([^<\s][^<]*?)\s*</dd>', re.S)

MONTHS_EN = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def clean_text(s):
    if not s:
        return None
    t = re.sub(r"<[^>]+>", " ", s)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def parse_java_date(s):
    """Parses the list row's own date/time text, which has been live-found
    to come back in EITHER of two different shapes depending on server-side
    locale rendering (see LT_DATE_RE's own comment above) - the plain
    Lithuanian "DD/MM/YYYY HH:MM:SS" shape is tried first since it is what
    this fetcher's own real Accept-Language header actually produces, with
    the English Java-toString shape kept as a fallback in case that ever
    changes."""
    if not s:
        return None
    m = LT_DATE_RE.search(s)
    if m:
        day, mon, year = m.group(1), m.group(2), m.group(3)
        try:
            return f"{year}-{int(mon):02d}-{int(day):02d}"
        except ValueError:
            pass
    m = JAVA_DATE_RE.search(s)
    if m:
        mon = MONTHS_EN.get(m.group(1))
        if mon:
            try:
                return f"{m.group(3)}-{mon}-{int(m.group(2)):02d}"
            except ValueError:
                pass
    return None


def parse_lt_value(s):
    """Converts a Lithuanian-decimal-comma value like '37190,08.' or
    '35637,6.' to a float, or None if blank/unparseable."""
    if not s:
        return None
    t = s.strip().rstrip(".").replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def http_get(url, retries=3, timeout=25):
    req = urllib.request.Request(url, headers=_HEADERS)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  error {e} for {url[:140]} (attempt {attempt+1}/{retries})")
            time.sleep(1.5)
    return None


def search_day_page(day_str, table_id, page):
    params = {"type": "cftFTS", "publicationFromDate": day_str, "publicationUntilDate": day_str}
    if table_id:
        params[f"d-{table_id}-p"] = str(page)
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    return http_get(url)


def parse_rows(body):
    """Parses one search-results page into (cft_rows, pmc_row_count).
    Only genuine "cft" (call for tenders) rows are returned as dicts - "pmc"
    (market consultation) rows are counted and skipped (see module
    docstring's "A REAL, LIVE-FOUND SCOPE BOUNDARY" section)."""
    tbody_m = TBODY_RE.search(body)
    if not tbody_m:
        return [], 0
    chunks = [c for c in ROW_SPLIT_RE.split(tbody_m.group(1)) if c.strip()]
    rows = []
    pmc_count = 0
    for chunk in chunks:
        cft_m = CFT_LINK_RE.search(chunk)
        if not cft_m:
            if "pmc/viewPmc.do" in chunk:
                pmc_count += 1
            continue
        resource_id = cft_m.group(1)
        title = clean_text(cft_m.group(2))
        tds = TD_RE.findall(chunk)
        buyer = clean_text(tds[3]) if len(tds) > 3 else None
        info_m = INFO_TITLE_RE.search(chunk)
        info_desc = html.unescape(info_m.group(1)).strip() if info_m else None
        pub_date = parse_java_date(clean_text(tds[5])) if len(tds) > 5 else None
        deadline = parse_java_date(clean_text(tds[6])) if len(tds) > 6 else None
        procedure = clean_text(tds[7]) if len(tds) > 7 else None
        status = clean_text(tds[8]) if len(tds) > 8 else None
        if not title or not resource_id:
            continue
        rows.append({
            "resourceId": resource_id,
            "title": title,
            "buyerName": buyer,
            "infoDescription": info_desc,
            "publicationDate": pub_date,
            "deadline": deadline,
            "procedureType": procedure,
            "status": status,
        })
    return rows, pmc_count


def daterange(start_date, end_date):
    n_days = (end_date - start_date).days
    for n in range(n_days + 1):
        yield start_date + timedelta(days=n)


def fetch_window(start_date, end_date):
    """Walks the real viewCFTSAction.do endpoint ONE CALENDAR DAY AT A TIME
    (the date-range params are the only reliable server-side narrowing
    mechanism found - see module docstring) and returns a resourceId-
    deduplicated list of raw "cft" row dicts. Prints a running count of
    skipped "pmc" (market-consultation) rows for transparency."""
    by_id = {}
    total_pmc_skipped = 0
    for day in daterange(start_date, end_date):
        day_str = day.strftime("%d/%m/%Y")
        table_id = None
        page = 1
        day_new = 0
        day_pmc = 0
        while page <= MAX_PAGES_PER_DAY:
            body = search_day_page(day_str, table_id, page)
            if body is None:
                print(f"  WARNING: request failed for {day_str} page {page} - stopping this day here.")
                break
            if table_id is None:
                m = TABLE_ID_RE.search(body)
                table_id = m.group(1) if m else None
            total_m = TOTAL_RE.search(body)
            total = int(total_m.group(1)) if total_m else None
            if total == 0:
                break
            rows, pmc_count = parse_rows(body)
            day_pmc += pmc_count
            if not rows and pmc_count == 0:
                break
            new_count = 0
            for r in rows:
                if r["resourceId"] not in by_id:
                    new_count += 1
                    day_new += 1
                by_id[r["resourceId"]] = r
            got_rows_total = len(rows) + pmc_count
            if got_rows_total < PAGE_SIZE or (new_count == 0 and pmc_count == 0):
                break
            page += 1
            time.sleep(0.15)
        total_pmc_skipped += day_pmc
        if day_new or day_pmc:
            print(f"  {day.strftime('%Y-%m-%d')}: {day_new} new cft row(s), {day_pmc} pmc row(s) skipped")
        time.sleep(0.1)
    if total_pmc_skipped:
        print(f"  (total pmc/market-consultation rows skipped across window: {total_pmc_skipped})")
    return list(by_id.values())


def fetch_detail(resource_id):
    body = http_get(DETAIL_URL_TMPL.format(id=resource_id))
    if body is None:
        return {}
    cpv_codes = []
    cpv_m = CPV_BLOCK_RE.search(body)
    if cpv_m:
        cpv_codes = CPV_CODE_RE.findall(cpv_m.group(1))
    value_m = VALUE_BLOCK_RE.search(body)
    value = parse_lt_value(value_m.group(1)) if value_m else None
    desc_m = DESC_BLOCK_RE.search(body)
    description = clean_text(desc_m.group(1)) if desc_m else None
    proc_m = PROCEDURE_BLOCK_RE.search(body)
    procedure_type = clean_text(proc_m.group(1)) if proc_m else None
    dur_m = DURATION_BLOCK_RE.search(body)
    duration_months = None
    if dur_m:
        num_m = re.search(r'(\d+)', dur_m.group(1))
        if num_m:
            duration_months = int(num_m.group(1))
    buyer_org_m = BUYER_ORG_ID_RE.search(body)
    buyer_org_id = buyer_org_m.group(1) if buyer_org_m else None
    plan_m = PLAN_REF_RE.search(body)
    contract_folder_id = clean_text(plan_m.group(1)) if plan_m else None
    return {
        "cpvCodes": cpv_codes,
        "estimatedValue": value,
        "currency": "EUR" if value is not None else None,
        "description": description,
        "procedureType": procedure_type,
        "contractDurationMonths": duration_months,
        "buyerOrgId": buyer_org_id,
        "contractFolderId": contract_folder_id,
    }


def fetch_buyer_info(buyer_org_id):
    """Best-effort only - see module docstring's "BUYER ORGANISATION PAGE"
    section. Returns (email, activity), either possibly None."""
    if not buyer_org_id:
        return None, None
    body = http_get(BUYER_ORG_URL_TMPL.format(id=buyer_org_id))
    if body is None:
        return None, None
    email_m = BUYER_EMAIL_RE.search(body)
    activity_m = BUYER_ACTIVITY_RE.search(body)
    email = clean_text(email_m.group(1)) if email_m else None
    activity = clean_text(activity_m.group(1)) if activity_m else None
    return email, activity


def normalize_title(title):
    if not title:
        return ""
    t = title.lower().strip()
    parts = [p.strip() for p in t.split("–") if p.strip()]
    tail = parts[-1] if parts else t
    tail = re.sub(r"\s+", " ", tail)
    return tail if len(tail) >= 8 else ""


def looks_like_cross_source_duplicate(rec, existing):
    new_tail = normalize_title(rec.get("title"))
    if not new_tail:
        return None
    new_buyer = (rec.get("buyerName") or "").lower().strip()
    for ex in existing:
        ex_tail = normalize_title(ex.get("title"))
        if not ex_tail:
            continue
        if new_tail == ex_tail or new_tail in ex_tail or ex_tail in new_tail:
            ex_buyer = (ex.get("buyerName") or "").lower().strip()
            if new_buyer and ex_buyer and new_buyer[:15] not in ex_buyer and ex_buyer[:15] not in new_buyer:
                continue
            return ex.get("publicationNumber")
    return None


def main():
    parser = argparse.ArgumentParser(description="Detect new DriveLock/idgard-relevant tenders on viesiejipirkimai.lt (Lithuania, CVP IS).")
    parser.add_argument("--days", type=int, default=3, help="Lookback window in days (default: 3)")
    parser.add_argument("--out", type=str, default="new_notices_found_viesiejipirkimai_lt.json", help="Output JSON path")
    parser.add_argument("--dataset", type=str, default="ted_shaped_final.json", help="Existing dataset path for dedup")
    args = parser.parse_args()

    with open(args.dataset, "r", encoding="utf-8") as f:
        existing = json.load(f)
    existing_ids = {r["publicationNumber"] for r in existing}
    print(f"Existing dataset: {len(existing)} records")

    now_utc = datetime.now(timezone.utc)
    end_date = now_utc.date()
    start_date = end_date - timedelta(days=args.days)
    cutoff = now_utc - timedelta(days=args.days)

    print(f"Querying viesiejipirkimai.lt (day-chunked walk, {start_date} .. {end_date}, type=cftFTS)...")
    rows = fetch_window(start_date, end_date)
    print(f"{len(rows)} raw cft row(s) collected (resourceId-deduplicated).")

    keyword_hits = []
    for r in rows:
        blob = " ".join(filter(None, [r.get("title"), r.get("infoDescription")]))
        if KEYWORD_PATTERN.search(blob):
            keyword_hits.append(r)
    print(f"{len(keyword_hits)} keyword hit(s) across title+Informacija tooltip.")

    new_records = []
    seen_ids = set()
    for r in keyword_hits:
        resource_id = r["resourceId"]
        pn = f"{PUBNUM_PREFIX}-{resource_id}"
        if pn in existing_ids or pn in seen_ids:
            continue

        if r["publicationDate"]:
            try:
                pub_dt = datetime.strptime(r["publicationDate"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
            except ValueError:
                pass

        detail = fetch_detail(resource_id)
        time.sleep(0.3)
        buyer_email, buyer_activity = fetch_buyer_info(detail.get("buyerOrgId"))
        time.sleep(0.3)

        rec = {
            "publicationNumber": pn,
            "title": r["title"],
            "buyerName": r["buyerName"],
            "country": "LTU",
            "publicationDate": r["publicationDate"],
            "deadline": r["deadline"],
            "noticeType": "lt-cft",
            "procedureType": detail.get("procedureType") or r["procedureType"],
            "cpvCodes": detail.get("cpvCodes") or [],
            "estimatedValue": detail.get("estimatedValue"),
            "currency": detail.get("currency"),
            "description": detail.get("description") or r["infoDescription"],
            "originalUrl": DETAIL_URL_TMPL.format(id=resource_id),
            "lotName": None,
            "awardedTo": None,
            "documentsUrl": NOTICE_PDF_URL_TMPL.format(id=resource_id),
            "contractDurationMonths": detail.get("contractDurationMonths"),
            "buyerEmail": buyer_email,
            "buyerLegalType": None,
            "buyerActivity": buyer_activity,
            "contractFolderId": detail.get("contractFolderId"),
            "internalId": resource_id,
            "procedureCode": detail.get("procedureType") or r["procedureType"],
            "accelerated": None,
            "performanceLocation": None,
            "source": SOURCE_NAME,
            "correctionKey": resource_id,
            "isCorrectionHint": False,
        }
        dup_of = looks_like_cross_source_duplicate(rec, existing)
        if dup_of:
            print(f"  SKIP (likely same tender already in dataset as {dup_of} via another source): {pn} -> {rec['title']!r}")
            continue
        seen_ids.add(pn)
        new_records.append(rec)
        print(f"  NEW: {pn} -> {rec['title']!r} (Pirkimo vykdytojas: {rec['buyerName']})")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(new_records, f, ensure_ascii=False, indent=2)
    print(f"\nDone. {len(new_records)} genuinely new record(s) written to {args.out}")


if __name__ == "__main__":
    main()
