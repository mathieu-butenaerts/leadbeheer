"""Shared helpers for the migrate_*.py scripts in this folder.

Not a script itself -- imported by migrate_plaats_regio.py,
migrate_land.py and migrate_native_format.py.
"""

import os

import pandas as pd

# Must match TEMPLATE_COLUMNS in index.html exactly (same order, same
# spelling) -- this is what "Importeren" in the app expects as the header
# row. The ENGAGEMENT_COLUMNS block is optional company-level LinkedIn Page
# metrics (see migrate_linkedin_engagement.py) -- blank on any row from a
# source that doesn't have them, which the app treats as "not measured".
ENGAGEMENT_COLUMNS = [
    "Engagement Level", "Organic Impressions", "Organic Engagements",
    "Paid Impressions", "Paid Clicks", "Paid Engagements", "Paid Video Views",
    "Paid Conversions", "Paid Leads", "Paid Qualified Leads",
    "Cost Per Qualified Lead",
]

TEMPLATE_COLUMNS = [
    "Company", "Company LinkedIn", "Fase", "Bedrijfsnotities",
    *ENGAGEMENT_COLUMNS,
    "First Name", "Last Name", "Job Title", "Gender",
    "Email", "Email 2", "Mobile Phone", "Work Phone",
    "Beller", "Vervolg", "Vervolgdatum",
    "Notities", "Belaantekeningen", "Mogelijk interessante hook",
]


def clean(value):
    """Turn a pandas cell (which may be NaN, None, or a number) into a
    stripped string, never the literal text "nan"."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def split_name(full_name):
    """Best-effort split of a single 'Naam' column into (first, last).

    Takes the first word as the first name and everything else as the last
    name. Correct for the common "Voornaam Achternaam" case; imperfect for
    tussenvoegsels ("Jan van der Berg" -> first="Jan", last="van der Berg",
    which is usually fine) or a double first name ("Jean Pierre Dubois" ->
    first="Jean", last="Pierre Dubois", which is not). Skim the output and
    fix those by hand -- there's no reliable way to guess this from the
    name alone.
    """
    parts = clean(full_name).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def append_note(existing, label, value):
    """Fold a source column that has no matching template field into a
    free-text note, tagged with its original column name so the
    information is kept (not silently dropped) instead of guessing which
    template field it belongs in."""
    value = clean(value)
    if not value:
        return existing
    tag = f"{label}: {value}"
    return f"{existing}\n{tag}" if existing else tag


def _require_columns(df, required_columns):
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise SystemExit(
            "This file doesn't look like the expected source format.\n"
            f"Missing column(s): {', '.join(missing)}\n"
            f"Columns found: {', '.join(df.columns)}"
        )
    return df


def read_source(path, required_columns):
    return _require_columns(pd.read_excel(path, dtype=str), required_columns)


def read_csv_source(path, required_columns):
    # LinkedIn's own exports (and plenty of others) are Windows-1252, not
    # UTF-8 -- a "®" or curly quote in a company name is enough to break a
    # plain pd.read_csv(path). Try encodings in order of how likely they are
    # for this kind of export; latin-1 never raises (it maps every byte to
    # some character), so this always succeeds by the end of the list.
    last_error = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(path, dtype=str, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        if encoding != "utf-8-sig":
            print(f"Note: read as {encoding} (the file isn't UTF-8) — check special characters in the output.")
        return _require_columns(df, required_columns)
    raise SystemExit(f"Could not read this file with any known encoding: {last_error}")


def to_number(value):
    """Parse a metric cell (impressions, clicks, leads, ...) to an int, or
    None when blank/unparseable -- None (not 0) so "not in this export"
    stays distinguishable from "measured, was zero"."""
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def to_money(value):
    """Parse a cost cell that may carry a currency symbol or thousands
    separator (e.g. "$1,234.50") to a float, or None when blank/unparseable."""
    text = clean(value)
    if not text:
        return None
    stripped = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def write_output(rows, out_path):
    df = pd.DataFrame(rows, columns=TEMPLATE_COLUMNS)

    if os.path.exists(out_path):
        existing_df = pd.read_excel(out_path)
        df = pd.concat([existing_df, df], ignore_index=True)

    df.to_excel(out_path, index=False)
    print(f"Wrote {len(df)} row(s) to {out_path}")
    print("Upload this file via \"Importeren\" in Leadbeheer to finish the migration.")

def clear_output(out_path):
    if os.path.exists(out_path):
        os.remove(out_path)
        print(f"Cleared existing file: {out_path}")
