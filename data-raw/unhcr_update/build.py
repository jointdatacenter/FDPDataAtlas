"""Add UNHCR Microdata Library studies released since the last atlas refresh.

Reads the UNHCR archive kept by the World Bank mdl_collector repository
(https://github.com/worldbank/mdl_collector, files data/unhcr/metadata.csv and
data/unhcr/datasets.csv) and appends new studies to inst/extdata/metadata.csv
and inst/extdata/metadata_v2.csv. Existing rows are never changed.

A study is a candidate when it was added to the library after the original
atlas snapshot (ORIGINAL_SNAPSHOT), is not in metadata.csv, and has no decision
in an earlier metadata_update_*.csv log. Selecting by id rather than by the
newest creation date means a study that reaches the collector late is still
picked up by the next run.

A candidate is added when it covers a single country from wb_bounds.csv and is
household or individual microdata; site assessments, key informant files and
event records are left out, as in earlier releases. A study is also left out
when every earlier study of the same series and country was left out of the
original atlas. Project-specific studies and studies from before 2010 go into
metadata.csv only, matching how metadata_v2.csv was derived from it.

Every candidate, added or not, is written to a new decision log with the
reason. An existing log is never overwritten, and no log is written when there
are no candidates.

Usage:
  python3 -I build.py <collector unhcr_metadata.csv> <collector unhcr_datasets.csv> <inst/extdata dir> <new log csv>
"""
import ast
import csv
import fnmatch
import glob
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import TAG_RES, is_idp, is_project_specific, tags_for  # noqa: E402

csv.field_size_limit(10**9)

NA = "NA"

# Library creation date of the newest study in the original atlas. Studies
# created on or before it were reviewed by the original team: those not in
# metadata.csv were left out on purpose and are not candidates.
ORIGINAL_SNAPSHOT = "2024-08-15T07:42:05+00:00"

# metadata_v2.csv holds no study from before this year.
FIRST_V2_YEAR = 2010

MONTHS = r"january|february|march|april|may|june|july|august|september|october|november|december"

# Library country names that differ from the names already used in the atlas
# or in wb_bounds.csv.
COUNTRY_ALIASES = {
    "Congo (Democratic Republic of the)": "COD",
    "Congo": "COG",
    "Türkiye": "TUR",
    "Moldova (the Republic of)": "MDA",
    "Egypt": "EGY",
}

# Approximate country centroids for focus countries that have no atlas rows yet
# (the atlas places one marker per country at its centroid).
CENTROIDS = {
    "EGY": ("29.8619", "26.4959"),
    "TUR": ("35.1689", "39.0616"),
    "IRN": ("54.2740", "32.5756"),
    "GEO": ("43.5072", "42.1689"),
    "RUS": ("96.6865", "61.9805"),
}

# Records that are not household or individual microdata on displaced people.
EXCLUDE_RE = re.compile(
    r"site assessment|site & village|baseline assessment|location assessment|displacement data"
    r"|displacement baseline|displacement tracking|displacement rapid assessment|key informant"
    r"|event tracking|evacuation tracking|task force on population movement|returnee data"
    r"|internally displaced persons data|internally displaced persons from natural disasters"
    r"|natural disaster inventory|events and people affected|confinements and displacements"
    r"|migration data|rapid needs assessment - flood",
    re.I,
)

DISPLACEMENT_QUESTION_COLS = [
    "country_of_birth", "country_of_citizenship", "acquisition_of_citizenship", "date_arrival",
    "reason_for_migration", "place_of_birth", "date_of_first_dp", "date_of_recent_dp",
    "main_reason_initial", "main_reason_recent", "loc_habit", "loc_usual",
]


def load(path):
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def parse_list(value):
    """The collector stores nested fields as Python list literals."""
    if not value:
        return []
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return [value]
    return parsed if isinstance(parsed, list) else [parsed]


def names(value):
    return [item.get("name", "").strip() for item in parse_list(value) if isinstance(item, dict) and item.get("name")]


def or_na(value):
    value = (value or "").strip()
    return value if value else NA


def contact(value):
    parts = []
    for item in parse_list(value):
        if isinstance(item, dict):
            parts.append("/".join(str(item.get(k, "")) for k in ("name", "affiliation", "email") if item.get(k)))
    return or_na(";".join(p for p in parts if p))


def coll_dates(value):
    periods = [p for p in parse_list(value) if isinstance(p, dict)]
    if not periods:
        return NA
    return f"{periods[0].get('start', '')}-{periods[-1].get('end', '')}".strip("-") or NA


def coll_mode(value):
    modes = parse_list(value) if value.startswith("[") else [value]
    modes = ["Face-to-face" if m.strip() == "Face-to-face [f2f]" else m.strip() for m in modes if m.strip()]
    return or_na("; ".join(modes))


def series_key(nation, title):
    """Country plus the title with only its date parts removed (years, months,
    quarters, halves, rounds), so the rounds of one survey series share a key.
    Parenthetical text and other numbers are kept: "(Household Survey)" and
    "(Key Informant Survey)", or "Project 21" and "Project 22", are different
    series."""
    t = re.sub(r"^[a-z ]+: ", "", title.lower())
    t = re.sub(MONTHS, " ", t)
    t = re.sub(r"\b(q[1-4]|h[12])\b|\bround\s+[ivx\d]+\b|#\d+", " ", t)
    t = re.sub(r"\b(19|20)\d\d\b", " ", t)
    t = re.sub(r"standardised", "standardized", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return nation.strip(), " ".join(t.split())


def write_outputs(outputs):
    """Write every (path, text) pair to a temporary file beside its target,
    then move them into place. Nothing is replaced until all temporary files
    are written, so a failure while writing leaves the existing files as they
    were. The log is moved first: if a later move fails, the consistency check
    in main() reports the logged rows missing from the CSV on the next run."""
    temps = []
    try:
        for path, text in outputs:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".build-", suffix=".csv")
            temps.append(tmp)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        for (path, _), tmp in zip(outputs, temps):
            os.replace(tmp, path)
    finally:
        for tmp in temps:
            if os.path.exists(tmp):
                os.remove(tmp)


def rows_text(cols, rows, header):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    if header:
        writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main():
    cat_path, ds_path, extdata, log_path = sys.argv[1:5]
    m1_path = os.path.join(extdata, "metadata.csv")
    m2_path = os.path.join(extdata, "metadata_v2.csv")
    # Later runs and evaluate.py find decisions only in extdata/metadata_update_*.csv.
    if (os.path.realpath(os.path.dirname(os.path.abspath(log_path))) != os.path.realpath(extdata)
            or not fnmatch.fnmatch(os.path.basename(log_path), "metadata_update_*.csv")):
        sys.exit(f"{log_path}: the log must be {extdata}/metadata_update_<date>.csv")
    if os.path.exists(log_path):
        sys.exit(f"{log_path} already exists; earlier decisions are kept, so give a new log file name")
    for path in (m1_path, m2_path, extdata):
        if not os.access(path, os.W_OK):
            sys.exit(f"{path} is not writable")
    _, catalog = load(cat_path)
    detail = {r["id"]: r for r in load(ds_path)[1]}
    m1_cols, m1 = load(m1_path)
    m2_cols, m2 = load(m2_path)
    _, bounds = load(os.path.join(extdata, "wb_bounds.csv"))

    in_atlas = {r["id"] for r in m1}
    logs = [r for log in glob.glob(os.path.join(extdata, "metadata_update_*.csv")) for r in load(log)[1]]
    decided = {r["id"] for r in logs}

    # A run that stopped part way leaves logged rows missing from the CSVs, or
    # added rows without a log entry. Either would be skipped by this run and
    # misread by evaluate.py, so stop until the files are restored.
    in_v2 = {r["id"] for r in m2}
    created = {r["id"]: r["created"] for r in catalog}
    problems = [f"{r['id']} is logged as added but missing from {name}"
                for r in logs if r["decision"].startswith("added")
                for name, ids in (("metadata.csv", in_atlas), ("metadata_v2.csv", in_v2))
                if (name == "metadata.csv" or "metadata_v2.csv" in r["decision"]) and r["id"] not in ids]
    problems += [f"{i} in metadata.csv was created after the original snapshot but is in no update log"
                 for i in sorted(in_atlas - decided, key=int) if created.get(i, "") > ORIGINAL_SNAPSHOT]
    if problems:
        sys.exit("inconsistent files; restore them from git before running again:\n  " + "\n  ".join(problems))

    def title_of(c):
        return (detail.get(c["id"], {}).get("title_statement.title") or c["title"]).strip()

    # Series whose earlier studies the original team reviewed: [left out, included].
    original = {}
    for c in catalog:
        if c["created"] <= ORIGINAL_SNAPSHOT:
            counts = original.setdefault(series_key(c["nation"], title_of(c)), [0, 0])
            counts[c["id"] in in_atlas] += 1

    focus = {r["ISO_A3"]: r for r in bounds}
    name_to_iso = {r["NAME_EN"]: r["ISO_A3"] for r in bounds}
    name_to_iso.update({r["nation_name"].strip(): r["nation_abbreviation"].strip() for r in m1})
    name_to_iso.update(COUNTRY_ALIASES)

    # Location fields are identical for every atlas row of a country, so new
    # rows reuse them; Region_v2 only exists in metadata_v2.csv.
    location = {r["nation_abbreviation"]: r for r in m1}
    region_v2 = {r["nation_abbreviation"]: r["Region_v2"] for r in m2}

    candidates = sorted(
        (r for r in catalog
         if r["created"] > ORIGINAL_SNAPSHOT and r["id"] not in in_atlas and r["id"] not in decided),
        key=lambda r: int(r["id"]),
    )
    if not candidates:
        print("no new studies; no log written")
        return

    new_m1, new_m2, log = [], [], []
    for c in candidates:
        d = detail.get(c["id"], {})
        has_detail = bool(d.get("title_statement.title"))
        title = title_of(c)
        # Some single country names contain a comma ("Congo, Rep."), so try the
        # whole value before treating it as a list.
        whole = c["nation"].strip()
        nations = [whole] if whole in name_to_iso else [n.strip() for n in whole.split(",") if n.strip()]
        iso = name_to_iso.get(nations[0], "") if len(nations) == 1 else ""
        project_specific = is_project_specific(title, d.get("series_statement.series_name", ""))
        left_out, included = original.get(series_key(c["nation"], title), [0, 0])
        before_v2 = c["year_start"].isdigit() and int(c["year_start"]) < FIRST_V2_YEAR

        if len(nations) != 1 or "more" in c["nation"]:
            decision = "excluded: covers more than one country"
        elif iso not in focus:
            decision = f"excluded: {nations[0]} is not in wb_bounds.csv"
        elif EXCLUDE_RE.search(title):
            decision = "excluded: site, key informant or event records, not household microdata"
        elif left_out and not included:
            decision = f"excluded: the original atlas left out every earlier study in this series ({left_out})"
        elif project_specific:
            decision = "added to metadata.csv only: project-specific"
        elif before_v2:
            decision = f"added to metadata.csv only: before {FIRST_V2_YEAR}"
        else:
            decision = "added to metadata.csv and metadata_v2.csv"

        log.append({
            "id": c["id"],
            "idno": c["idno"],
            "title": title,
            "country": c["nation"],
            "year": c["year_start"],
            "catalog_created": c["created"][:10],
            "decision": decision,
            "detail_in_collector": "yes" if has_detail else "no",
            "topic_tags": ("from notes" if d.get("notes") else "NA: no notes in collector") if decision.startswith("added") else "",
            "url": c["url"],
        })
        if not decision.startswith("added"):
            continue

        loc = location.get(iso)
        lon, lat = (loc["Longitude"], loc["Latitude"]) if loc else CENTROIDS[iso]
        authors = names(d.get("authoring_entity", "")) or [c["authoring_entity"]]
        collectors = names(d.get("data_collectors", ""))
        notes = d.get("notes", "")
        universe = d.get("universe", "")
        row = {
            "id": c["id"],
            "idno": c["idno"],
            "nation_abbreviation": iso,
            "statement_title": title,
            "database": "UNHCR MDL",
            "data_url": c["url"],
            "nation_name": loc["nation_name"] if loc else focus[iso]["NAME_EN"],
            "year": or_na(c["year_start"]),
            "producers_name": or_na(authors[0] if authors else ""),
            "entity_name": or_na(";".join(authors)),
            "entity_contact": contact(d.get("distribution_statement.contact", "")),
            "abstract": or_na(d.get("abstract")),
            "coll_dates": coll_dates(d.get("coll_dates", "")),
            "analysis_unit": or_na(d.get("analysis_unit")),
            "geog_coverage": or_na(d.get("geog_coverage")),
            "data_kind": or_na(d.get("data_kind")),
            "notes": or_na(notes),
            "method_data_collectors_name": or_na(collectors[0] if collectors else ""),
            "method_sampling": or_na(d.get("sampling_procedure")),
            "method_coll_mode": coll_mode(d.get("coll_mode", "")),
            "method_research_instrument": or_na(d.get("research_instrument")),
            "method_weight": or_na(d.get("weight")),
            "cit_req": or_na(d.get("data_access.dataset_use.cit_req")),
            "disclaimer": or_na(d.get("data_access.dataset_use.disclaimer")),
            "project_specific": str(project_specific),
            # A title match is enough for 1; a 0 needs the universe text, so
            # without it the value is unknown.
            "idp": "1" if is_idp(title, "") else (str(is_idp(title, universe)) if universe.strip() else NA),
            "idp_title": str(is_idp(title, "")),
            "series_id": NA,
            "Longitude": lon,
            "Latitude": lat,
            "Region": loc["Region"] if loc else focus[iso]["Region"],
            "Economy": loc["Economy"] if loc else focus[iso]["NAME_EN"],
            "income_group": loc["income_group"] if loc else focus[iso]["income_group"],
            "original": "1",
            "Region_v2": region_v2.get(iso, loc["Region"] if loc else focus[iso]["Region"]),
        }
        # The displacement question flags need the study's variable list,
        # which the collector does not archive.
        row.update({col: NA for col in DISPLACEMENT_QUESTION_COLS})
        tags = tags_for(notes) if notes else None
        row.update({f"tag_new_{t}": (str(tags[t]) if tags else NA) for t in TAG_RES})

        new_m1.append(row)
        if decision == "added to metadata.csv and metadata_v2.csv":
            new_m2.append(row)

    log_cols = ["id", "idno", "title", "country", "year", "catalog_created", "decision",
                "detail_in_collector", "topic_tags", "url"]
    outputs = [(log_path, rows_text(log_cols, log, header=True))]
    for path, cols, rows in ((m1_path, m1_cols, new_m1), (m2_path, m2_cols, new_m2)):
        missing = set(cols) - set(rows[0]) if rows else set()
        if missing:
            sys.exit(f"{path}: no value for columns {sorted(missing)}")
        # Existing rows are copied byte for byte; new rows go after them.
        with open(path, encoding="utf-8", newline="") as f:
            existing = f.read()
        if existing and not existing.endswith("\n"):
            existing += "\n"
        outputs.append((path, existing + rows_text(cols, rows, header=False)))
    write_outputs(outputs)

    print(f"{len(candidates)} candidates, {len(new_m1)} added to metadata.csv, "
          f"{len(new_m2)} added to metadata_v2.csv")


main()
