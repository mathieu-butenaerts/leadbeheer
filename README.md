# Leadbeheer

Shared CRM for tracking sales leads — companies expand to show notes, stage,
and contact-person details. Colleagues sign in with the **same account** they
already use for [Marktmonitor](https://github.com/KLoos1123/Scrappingtool-v2)
(same Supabase project), and the page updates live for everyone as people
edit.

Styling matches Marktmonitor's dashboard: same colors, fonts, and
login/register flow, copied from that repo's `web/` folder.

## One-time setup

1. **Database.** In your Supabase project (the same one Marktmonitor uses):
   open **SQL Editor > New query**, paste the contents of
   [`supabase/schema.sql`](supabase/schema.sql), and run it. This creates the
   `companies` and `contacts` tables, keeps `contact_count` in sync
   automatically, turns on row-level security (any signed-in user can read
   and write — same trust model Marktmonitor already uses), enables realtime,
   and seeds two example companies.
2. **GitHub Pages.** In this repo's Settings > Pages, set **Source** to
   "GitHub Actions" (only needs doing once). The workflow in
   [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)
   then deploys automatically on every push to `main`.
3. Open the Pages URL GitHub gives you (Settings > Pages, or the workflow
   run's summary) → `login.html`. Anyone with an existing Marktmonitor login
   can sign in immediately; new colleagues register the same way (needs a
   registration key from an admin, same as Marktmonitor).

## Files

- `index.html` — the CRM itself.
- `login.html` / `register.html` / `auth.js` — copied from Marktmonitor,
  pointing at the same Supabase project (same accounts work on both sites).
- `supabase/schema.sql` — the one-time database migration.
- `.github/workflows/deploy-pages.yml` — builds and publishes to GitHub Pages
  on every push to `main`.
- `tools/migrate_*.py` — one-off converters for legacy Excel exports that
  don't match the app's own template columns (see below).

## Importing legacy Excel exports

The app's own "Sjabloon downloaden" / "Importeren" buttons handle files that
already use its column names. For older exports with different headers,
`tools/` has a converter per known source format:

- `migrate_plaats_regio.py` — `Notities, Telefoon 1, Naam, Functie, Bedrijf, Plaats / regio, E-mail, Telefoon 2, LinkedIn`
- `migrate_land.py` — `Comment, Telefoonnummer, Naam, Functie, Bedrijf, Land, Email, LinkedIn URL`
- `migrate_native_format.py` — `Notities, Beller, Vervolg, Belaantekeningen, Mogelijk interessante hook, Id, First Name, Last Name, Gender, Email, Email 2, Mobile Phone, Work Phone, Company, Company LinkedIn, Job Function`
- `migrate_linkedin_engagement.py` — a LinkedIn Company Page engagement export (`.csv`): `Company name, Company page URL, Engagement level, Organic impressions, Organic engagements, Paid impressions, Paid clicks, Paid engagements, Paid video views, Paid conversions, Paid leads, Paid qualified leads, Cost per qualified lead`. Unlike the others, this source is company-level metrics only (no contact people) — see [Engagement score](#engagement-score-from-linkedin-data) below.

Each reads one file (`.xlsx` or, for the LinkedIn one, `.csv`) and writes a new `.xlsx` shaped like the app's template —
the docstring at the top of each script spells out exactly which source
column goes where, and the judgment calls that had no clean answer (splitting
a single "Naam" field, a personal LinkedIn URL with nowhere else to go).
Check a few output rows against the source before importing; a mapping
that's obviously wrong for your data is easier to fix in the script than to
clean up after 200 rows land in the database.

```bash
pip install pandas openpyxl
python tools/migrate_plaats_regio.py path/to/export.xlsx
```

Then upload the `_migrated.xlsx` file it produces via "Importeren" in the
app, same as any other file — that step already checks for duplicates before
writing anything.

## Engagement score (from LinkedIn data)

Importing a `migrate_linkedin_engagement.py` output stores that company's raw
LinkedIn metrics (impressions, clicks, leads, cost per qualified lead, ...).
Re-uploading a later export for a company already in Leadbeheer only ever
refreshes those numbers — it never touches its Fase, notes, or LinkedIn URL.

The app then computes a 0–100 "Score" for any company with at least one
metric, shown as a sortable column and, expanded, alongside the raw numbers
it's built from. The score itself isn't stored anywhere — it's recalculated
live from `engagementScore()` in `index.html` every time the page renders, so
adjusting its weights is a one-line code change with no re-import needed. It
currently weighs, roughly: qualified leads heaviest, then leads, then
conversions, in that funnel order; a low cost per qualified lead as a bonus
on top of the qualified-lead score; engagement *rate* (not raw impressions)
on both organic and paid content — for paid, clicks/engagements/video views
all count as an interaction, not just engagements; and LinkedIn's own
Engagement Level as a smaller contribution, matched by substring so values
like "Very Low"/"Very High" aren't missed by an exact High/Medium/Low match.
A company with no engagement data at all shows "—", not a 0, so "never
measured" stays visually distinct from "measured, scored zero".

## Note on the Claude Artifact version

The original version of this CRM (built first, before this repo existed)
still exists as a private Claude Artifact and stores its data in Claude's own
`db` capability — that storage is completely separate from the Supabase
tables here. The two aren't kept in sync; treat this repo as the CRM going
forward and the Claude Artifact as the earlier prototype.
