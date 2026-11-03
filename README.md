# tender-lt-relay

GitHub Actions relay for `viesiejipirkimai.lt` (Lithuania), used by the
DriveLock/idgard Tender Intelligence pipeline.

## Why this exists

The production server (Strato shared hosting) cannot reach
`viesiejipirkimai.lt` at all — confirmed 2026-11-04 via a raw
`curl -4 -v --max-time 15 https://viesiejipirkimai.lt/` run directly from the
server itself, which timed out after 15 seconds trying to connect to
195.182.78.144:443 (no WAF page, no TLS error, no IPv6 involved — IPv6
resolved to "none" for this host — the connection simply never completes).
This is the same problem the project already solved twice before, for
`oeffentlichevergabe.de` (`tenderdiscovery/tender-oev-relay`) and
`publicprocurement.be` (`tenderdiscovery/tender-be-relay`): run the fetch on
GitHub's own infrastructure instead, where this specific network block does
not apply, and have the production server read the *result* back over a
plain HTTPS GET to `raw.githubusercontent.com` (which is not blocked).

## How it works

1. `.github/workflows/relay.yml` runs daily at 05:10 UTC (and on manual
   "Run workflow" dispatch), executing:
   ```
   python3 fetch_viesiejipirkimai_lt.py --days 90 --out latest_lt.json --dataset ted_shaped_final_snapshot.json
   ```
2. The workflow commits `latest_lt.json` back to this repo (using the
   built-in `GITHUB_TOKEN`, no extra secrets needed).
3. The production server's `run_daily_digest.py` reads
   `https://raw.githubusercontent.com/<your-account>/tender-lt-relay/main/latest_lt.json`
   on every cron cycle via a plain `urllib` GET (see `fetch_lt_via_github_relay()`
   in `run_daily_digest.py`).

## About `ted_shaped_final_snapshot.json`

This is a **one-time snapshot** (taken 2026-11-04, from this build sandbox's
own copy of the dataset — 41 records at time of copy, almost certainly
smaller/staler than the real production master, which already has 433+
records; see the paragraph below for why that's fine), committed here only
so `fetch_viesiejipirkimai_lt.py` has *something* to dedupe against when it
runs in isolation on GitHub. It will go stale over time and this workflow
does **not** refresh it automatically — that's fine and intentional, same
accepted limitation as the existing `tender-oev-relay`/`tender-be-relay`: the
real, authoritative dedup against the live, up-to-date master dataset
happens centrally in `run_daily_digest.py` itself *after* reading this
relay's output (via `existing_ids` / `looks_like_duplicate_of_master()`). A
stale snapshot here only means a handful of already-known records get
needlessly re-listed in `latest_lt.json` every run — it can never cause
anything wrong to reach the real master dataset or the user, since that
downstream check is unconditional for every source.

## Setup (one-time, by hand)

1. Create a new **public** GitHub repo (public is required for the
   unauthenticated `raw.githubusercontent.com` read to work without a token)
   under the same account/org as `tenderdiscovery/tender-be-relay` — e.g.
   `tenderdiscovery/tender-lt-relay`.
2. Push the contents of this folder to that repo's `main` branch, unchanged.
3. Actions should be enabled by default for a new repo. If not: repo
   Settings → Actions → General → "Allow all actions and reusable workflows".
4. Confirm `contents: write` permission is available to the workflow (repo
   Settings → Actions → General → "Workflow permissions" → "Read and write
   permissions" — needed for the `git push` step in `relay.yml`).
5. Trigger the workflow once manually (Actions tab → "Lithuania
   (viesiejipirkimai.lt) relay" → "Run workflow") and confirm it completes
   successfully and `latest_lt.json` appears in the repo.
6. Tell Claude the exact final repo URL (account/org name may differ from
   `tenderdiscovery`) so `GITHUB_LT_RELAY_URL` in `run_daily_digest.py` can be
   set to the correct
   `https://raw.githubusercontent.com/<account>/<repo>/main/latest_lt.json`
   value before that file is uploaded to the production server.

## Maintenance

Nothing regular is required. If viesiejipirkimai.lt ever changes its page
structure or the `type=cftFTS` query shape, `fetch_viesiejipirkimai_lt.py`
here needs the same fix applied as the production copy in
`~/.tender-pipeline/fetch_viesiejipirkimai_lt.py` — the two are currently
identical copies, not symlinked or auto-synced.
