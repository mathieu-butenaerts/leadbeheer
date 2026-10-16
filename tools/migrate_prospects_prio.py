#!/usr/bin/env python3
"""Migrate the contact list ("Prospects" tab of "B1 klanten voor
profiling.xlsx") to the Leadbeheer template:

    Prio  Toelichting  Telefoonnummer  Naam  Functie  Bedrijf LI
    Bedrijf in B1 lijst  Verantwoordelijk  Plaats/ land  Email  LinkedIn URL

One output row per contact. The company is "Bedrijf in B1 lijst" (as
requested) -- it's the name used on the company list, so contacts attach to
the companies migrate_klanten_bedrijven.py creates.

Judgment calls (check the output, adjust here if wrong):
  - "Naam" is one "Voornaam Achternaam" field, split on the first space
    (see _common.split_name for its limits). Functie -> Job Title,
    Email -> Email.
  - A cell that only says "x" or "?" means "none found" in this sheet and is
    treated as empty (otherwise "x" would end up as a phone number/e-mail).
  - "Telefoonnummer" -> Mobile Phone when it's a mobile number (+31 6 / 06 /
    +32 4), otherwise Work Phone. A cell with several numbers is split on
    commas/semicolons; the first mobile and the first other number get the
    two fields and any further ones go into the notes.
  - "Toelichting" is the contact's note text and becomes Notities; below it,
    labelled lines: Prio, Verantwoordelijk, Plaats/ land, LinkedIn (the
    person's own profile -- the template has no field for it) and "Bedrijf op
    LinkedIn" when LinkedIn's company name differs from "Bedrijf in B1 lijst".
  - "Verantwoordelijk" goes into the notes, not Beller: its values are group
    labels ("Sales Marketeer", "SKIP", "Nog niet toegewezen"), not people to
    call, and Beller feeds the caller filter.

Usage:
    pip install pandas openpyxl
    python migrate_prospects_prio.py "B1 klanten voor profiling.xlsx" [output.xlsx]

The "Prospects" tab is picked by name, so it needn't be the first tab.
"""

import re
import sys
from pathlib import Path

from _common import append_note, clean, read_source, split_name, write_output

SHEET_NAME = "Prospects"

REQUIRED_COLUMNS = [
    "Prio", "Toelichting", "Telefoonnummer", "Naam", "Functie", "Bedrijf LI",
    "Bedrijf in B1 lijst", "Verantwoordelijk", "Plaats/ land", "Email",
    "LinkedIn URL",
]


PLACEHOLDERS = {"x", "?", "-", "--", "n.v.t.", "nvt", "n/a", "geen"}


def real(value):
    """clean() plus: a cell that only says "x" or "?" (this sheet's way of
    writing "none found" -- 11 phone numbers, 1 e-mail, 1 job title) is empty."""
    text = clean(value)
    return "" if text.lower() in PLACEHOLDERS else text


def is_mobile(number):
    digits = re.sub(r"\(0\)", "", number)
    digits = re.sub(r"[^\d+]", "", digits)
    digits = re.sub(r"^00", "+", digits)
    return bool(re.match(r"^(\+316|06|\+324)", digits))


def split_phones(cell):
    """-> (mobile, work, extras): first mobile number, first other number,
    and whatever is left over."""
    numbers = [n.strip() for n in re.split(r"[;,]", real(cell)) if n.strip() and n.strip().lower() not in PLACEHOLDERS]
    mobile = next((n for n in numbers if is_mobile(n)), "")
    work = next((n for n in numbers if n != mobile and not is_mobile(n)), "")
    extras = [n for n in numbers if n not in (mobile, work)]
    return mobile, work, extras


def migrate(df):
    rows = []
    skipped = 0
    for _, r in df.iterrows():
        company = clean(r["Bedrijf in B1 lijst"])
        if not company:
            skipped += 1
            continue
        first_name, last_name = split_name(r["Naam"])
        mobile, work, extra_phones = split_phones(r["Telefoonnummer"])

        notes = real(r["Toelichting"])
        notes = append_note(notes, "Prio", real(r["Prio"]))
        notes = append_note(notes, "Verantwoordelijk", real(r["Verantwoordelijk"]))
        notes = append_note(notes, "Plaats/ land", real(r["Plaats/ land"]))
        notes = append_note(notes, "LinkedIn", real(r["LinkedIn URL"]))
        li_company = clean(r["Bedrijf LI"])
        if li_company and li_company.lower() != company.lower():
            notes = append_note(notes, "Bedrijf op LinkedIn", li_company)
        if extra_phones:
            notes = append_note(notes, "Extra telefoon", ", ".join(extra_phones))

        rows.append({
            "Company": company,
            "Company LinkedIn": "",
            "Fase": "",
            "Bedrijfsnotities": "",
            "Tags": "",
            "First Name": first_name,
            "Last Name": last_name,
            "Job Title": real(r["Functie"]),
            "Gender": "",
            "Email": real(r["Email"]),
            "Email 2": "",
            "Mobile Phone": mobile,
            "Work Phone": work,
            "Beller": "",
            "Vervolg": "",
            "Vervolgdatum": "",
            "Notities": notes,
            "Belaantekeningen": "",
            "Mogelijk interessante hook": "",
        })
    return rows, skipped


def main(in_path_str=None, out_path_str=None):
    if in_path_str is None:
        if len(sys.argv) < 2:
            raise SystemExit(f"Usage: python {Path(__file__).name} input.xlsx [output.xlsx]")
        in_path_str = sys.argv[1]
        out_path_str = sys.argv[2] if len(sys.argv) > 2 else None
    in_path = Path(in_path_str)
    out_path = Path(out_path_str) if out_path_str else in_path.with_name(in_path.stem + "_prospects_migrated.xlsx")

    df = read_source(in_path, REQUIRED_COLUMNS, sheet_name=SHEET_NAME)
    rows, skipped = migrate(df)
    print(f"{len(rows)} contacts across {len({r['Company'].lower() for r in rows})} companies"
          + (f"; skipped {skipped} row(s) without a company" if skipped else ""))
    write_output(rows, out_path)


if __name__ == "__main__":
    main()
