#!/usr/bin/env python3
"""Migrate the company list ("B1 Bedrijven" tab of "B1 klanten voor
profiling.xlsx") to the Leadbeheer template:

    Soort klant  Huidig ERP  Naam klant  Vestigingsplaats  Provincie
    Grootte (medewerkers)  Type bedrijf  Website  Bron  Aantal contactpersonen
    Verdeling  Kwalificatie  URL linkedin  Trigger  P4 contactpersoon
    Referentieklant/ casus  Partner  Campagne  Alternatieve naam  Opmerkingen
    Sub Industry  Industry  Bron3  Bronreferentie

Company-level data only -- one output row per company, no contacts (those
come from migrate_prospects_prio.py).

Rules (as requested):
  - "Verdeling" becomes the company's initial TAG. A comma/semicolon inside
    a value is replaced by " -" (the template's Tags column splits on those,
    so "SKIP, is 1 verfwinkel" would otherwise become two tags).
  - A "Kwalificatie" starting with "4." (4.Skip geografie, 4.Te klein,
    4.Failliet, ...) sets Fase to "Verloren". Every other row keeps the
    app's default (Nieuw).

Other judgment calls (check the output, adjust here if wrong):
  - Naam klant -> Company, URL linkedin -> Company LinkedIn (a tracking
    "?query" part is dropped), Grootte (medewerkers) -> Company Size,
    Huidig ERP -> Installed Technology (shown as "Technologie").
  - Industry -> Industry, with Sub Industry appended as "Industry (Sub
    Industry)" when both exist.
  - Website -> Domain, but only when it looks like a URL/domain; some cells
    hold a web-page title ("eldoLED(R) | LED Drivers, ...") -- those go into
    the notes as "Website: ..." instead of a bogus Domain.
  - Everything with no template field is folded into Bedrijfsnotities, each
    line tagged with its source column: Opmerkingen, Kwalificatie (always,
    so the reason behind a "4." stays visible), Trigger, Vestigingsplaats,
    Provincie, Type bedrijf, Partner, Campagne, Alternatieve naam,
    Referentieklant/ casus, Bron, Bron3, Bronreferentie, and Soort klant when
    it isn't plain "B1" (that value is on nearly every row and only adds noise).
  - Ignored: "Aantal contactpersonen" (a stale count -- the app counts
    contacts itself), "P4 contactpersoon" (empty in this file) and an
    "Alternatieve naam" that is just a number (it is 29 on nearly every row).
  - In the current file Industry, Sub Industry and Opmerkingen are empty
    and Huidig ERP is "B1" (SAP Business One) on all but two rows; the
    mappings are there for when they're filled.

Usage:
    pip install pandas openpyxl
    python migrate_klanten_bedrijven.py "B1 klanten voor profiling.xlsx" [output.xlsx]

The "B1 Bedrijven" tab is picked by name, so it needn't be the first tab.
"""

import re
import sys
from pathlib import Path

from _common import append_note, clean, read_source, write_output

SHEET_NAME = "B1 Bedrijven"

REQUIRED_COLUMNS = [
    "Naam klant", "Huidig ERP", "Verdeling", "Kwalificatie", "URL linkedin",
    "Website", "Grootte (medewerkers)", "Industry", "Sub Industry",
    "Opmerkingen", "Trigger", "Vestigingsplaats", "Provincie", "Type bedrijf",
    "Partner", "Campagne", "Alternatieve naam", "Referentieklant/ casus",
    "Bron", "Bron3", "Bronreferentie", "Soort klant",
]

# Source column -> label in the notes, in the order they should appear.
NOTE_FIELDS = [
    ("Opmerkingen", "Opmerkingen"),
    ("Kwalificatie", "Kwalificatie"),
    ("Trigger", "Trigger"),
    ("Vestigingsplaats", "Vestigingsplaats"),
    ("Provincie", "Provincie"),
    ("Type bedrijf", "Type bedrijf"),
    ("Partner", "Partner"),
    ("Campagne", "Campagne"),
    ("Alternatieve naam", "Alternatieve naam"),
    ("Referentieklant/ casus", "Referentieklant/casus"),
    ("Bron", "Bron"),
    ("Bron3", "Bron3"),
    ("Bronreferentie", "Bronreferentie"),
]


def tag_from_verdeling(value):
    return re.sub(r"\s*[;,]\s*", " - ", clean(value))


def is_lost(kwalificatie):
    return clean(kwalificatie).startswith("4.")


def linkedin_url(value):
    return clean(value).split("?")[0]


def looks_like_domain(value):
    return bool(value) and not re.search(r"\s", value)


def industry(r):
    main, sub = clean(r["Industry"]), clean(r["Sub Industry"])
    if main and sub:
        return f"{main} ({sub})"
    return main or sub


def migrate(df):
    rows = []
    for _, r in df.iterrows():
        company = clean(r["Naam klant"])
        if not company:
            continue

        notes = ""
        website = clean(r["Website"])
        if website and not looks_like_domain(website):
            notes = append_note(notes, "Website", website)
            website = ""
        for column, label in NOTE_FIELDS:
            value = clean(r[column])
            # "Alternatieve naam" holds the number 29 on 268 of 270 rows --
            # a stray constant, not a name; a bare number is never a name.
            if column == "Alternatieve naam" and value.isdigit():
                continue
            notes = append_note(notes, label, value)
        soort = clean(r["Soort klant"])
        if soort and soort.upper() != "B1":
            notes = append_note(notes, "Soort klant", soort)

        rows.append({
            "Company": company,
            "Company LinkedIn": linkedin_url(r["URL linkedin"]),
            "Fase": "Verloren" if is_lost(r["Kwalificatie"]) else "",
            "Bedrijfsnotities": notes,
            "Tags": tag_from_verdeling(r["Verdeling"]),
            "Domain": website,
            "Company Size": clean(r["Grootte (medewerkers)"]),
            "Industry": industry(r),
            "Installed Technology": clean(r["Huidig ERP"]),
        })
    return rows


def main(in_path_str=None, out_path_str=None):
    if in_path_str is None:
        if len(sys.argv) < 2:
            raise SystemExit(f"Usage: python {Path(__file__).name} input.xlsx [output.xlsx]")
        in_path_str = sys.argv[1]
        out_path_str = sys.argv[2] if len(sys.argv) > 2 else None
    in_path = Path(in_path_str)
    out_path = Path(out_path_str) if out_path_str else in_path.with_name(in_path.stem + "_bedrijven_migrated.xlsx")

    df = read_source(in_path, REQUIRED_COLUMNS, sheet_name=SHEET_NAME)
    rows = migrate(df)
    lost = sum(1 for r in rows if r["Fase"] == "Verloren")
    print(f"{len(rows)} companies, {lost} set to Verloren, {len({r['Tags'].lower() for r in rows if r['Tags']})} distinct tags")
    write_output(rows, out_path)


if __name__ == "__main__":
    main()
