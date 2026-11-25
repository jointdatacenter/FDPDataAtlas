"""Score the keyword rules against the atlas's existing hand-coded flags.

Usage: python3 -I evaluate.py <collector unhcr_datasets.csv> <atlas inst/extdata dir>
"""
import csv
import glob
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from rules import TAG_RES, is_idp, is_project_specific, tags_for  # noqa: E402

csv.field_size_limit(10**9)


def load(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def score(pairs):
    tp = sum(1 for p, t in pairs if p and t)
    fp = sum(1 for p, t in pairs if p and not t)
    fn = sum(1 for p, t in pairs if not p and t)
    agree = sum(1 for p, t in pairs if p == t) / len(pairs)
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    return f"agree {agree:.0%}  precision {prec:.0%}  recall {rec:.0%}  (n={len(pairs)}, true={tp + fn})"


def main():
    datasets_path, extdata = sys.argv[1:3]
    ds = {r["id"]: r for r in load(datasets_path)}
    # Score only hand-coded studies: rows added by build.py are listed in the
    # metadata_update_*.csv decision logs and were coded by these same rules.
    generated = {r["id"] for log in glob.glob(f"{extdata}/metadata_update_*.csv") for r in load(log)}
    m1 = [r for r in load(f"{extdata}/metadata.csv") if r["id"] not in generated]
    m2 = [r for r in load(f"{extdata}/metadata_v2.csv") if r["id"] not in generated]

    print("project_specific:", score([
        (is_project_specific(ds[r["id"]]["title_statement.title"], ds[r["id"]]["series_statement.series_name"]),
         r["project_specific"] == "1") for r in m1]))
    print("idp:             ", score([
        (is_idp(ds[r["id"]]["title_statement.title"], ds[r["id"]]["universe"]), r["idp"] == "1") for r in m1]))

    preds = {r["id"]: tags_for(ds[r["id"]]["notes"]) for r in m2}
    for tag in TAG_RES:
        print(f"tag {tag:30s}", score([(preds[r["id"]][tag], r[f"tag_new_{tag}"] == "1") for r in m2]))

    if len(sys.argv) > 3:
        tag = sys.argv[3]
        for r in m2:
            p, t = preds[r["id"]][tag], r[f"tag_new_{tag}"] == "1"
            if p != t:
                print(f"\n[{'FP' if p else 'FN'}] {r['id']} {r['statement_title'][:70]}\n  ", ds[r["id"]]["notes"][:300].replace("\n", " | "))


main()
