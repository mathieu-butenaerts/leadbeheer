"""Shared helpers for the migrate_*.py scripts in this folder.

Not a script itself -- imported by migrate_plaats_regio.py,
migrate_land.py and migrate_native_format.py.
"""

import pandas as pd

# Must match TEMPLATE_COLUMNS in index.html exactly (same order, same
# spelling) -- this is what "Importeren" in the app expects as the header
# row.
TEMPLATE_COLUMNS = [
    "Company", "Company LinkedIn", "Fase", "Bedrijfsnotities",
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


def read_source(path, required_columns):
    df = pd.read_excel(path, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise SystemExit(
            "This file doesn't look like the expected source format.\n"
            f"Missing column(s): {', '.join(missing)}\n"
            f"Columns found: {', '.join(df.columns)}"
        )
    return df


def write_output(rows, out_path):
    df = pd.DataFrame(rows, columns=TEMPLATE_COLUMNS)
    df.to_excel(out_path, index=False)
    print(f"Wrote {len(df)} row(s) to {out_path}")
    print("Upload this file via \"Importeren\" in Leadbeheer to finish the migration.")
