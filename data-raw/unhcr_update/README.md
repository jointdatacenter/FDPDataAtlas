# Adding new UNHCR Microdata Library studies

These scripts add studies released in the [UNHCR Microdata Library](https://microdata.unhcr.org/index.php/catalog) since the last refresh to `inst/extdata/metadata.csv` and `inst/extdata/metadata_v2.csv`, then rebuild the packaged data in `data/`. Existing rows are never changed.

## Source

The library blocks most scripted requests, so the input is the archive kept by the Joint Data Center's [mdl_collector](https://github.com/worldbank/mdl_collector) repository, which collects the catalog every week:

- `data/unhcr/metadata.csv`: one row per study in the catalog (title, country, years, creation date, URL).
- `data/unhcr/datasets.csv`: the full study description for each study.

The collector fetches a study's description only once, when it first sees the study, and some records are empty. Those studies are still added, with title, country, year and URL from the catalog list, and the other fields set to `NA`.

## Steps

```sh
# 1. Download the collector archive (any folder outside the repository).
gh api -H "Accept: application/vnd.github.raw" repos/worldbank/mdl_collector/contents/data/unhcr/metadata.csv > unhcr_metadata.csv
gh api -H "Accept: application/vnd.github.raw" repos/worldbank/mdl_collector/contents/data/unhcr/datasets.csv > unhcr_datasets.csv

# 2. Optional: check the keyword rules against the existing hand-coded studies.
python3 -I data-raw/unhcr_update/evaluate.py unhcr_datasets.csv inst/extdata

# 3. Append the new studies and write the decision log.
# Use a new log name each run; the script refuses to overwrite an existing log.
python3 -I data-raw/unhcr_update/build.py unhcr_metadata.csv unhcr_datasets.csv inst/extdata inst/extdata/metadata_update_<date>.csv

# 4. Rebuild data/metadata.rda (and the other packaged objects).
Rscript data-raw/unhcr_update/rebuild_rda.R
```

## Which studies are added

The original atlas covers studies the library created up to 2024-08-15 (`ORIGINAL_SNAPSHOT` in `build.py`). A study is a candidate when it was created after that date, is not in `metadata.csv`, and has no decision in an earlier `metadata_update_*.csv` log. Candidates are chosen by id, so a study that reaches the collector late is picked up by the next run. Each run writes a new log, and when there are no candidates it writes none. The log must be `inst/extdata/metadata_update_<date>.csv`, because later runs and `evaluate.py` look for logs there. The script writes the log and both CSVs to temporary files first and only then moves them into place. Before changing anything, it checks that every study logged as added is in the CSVs and that every added row in the CSVs is logged, and stops if not. A run that failed part way is therefore reported, not repeated on top of half-written files.

A candidate is added when:

- it covers exactly one country, and that country is in `inst/extdata/wb_bounds.csv`;
- it is household or individual microdata. Site and location assessments, displacement tracking baselines, key informant files and event records are left out, as they were in earlier releases;
- the original atlas did not leave out every earlier study of the same series in the same country. The series is the title with only its date parts removed (years, months, quarters, halves and round numbers); parenthetical text and other numbers are kept, so "Protection Monitoring (Household Survey)" and "Protection Monitoring (Key Informant Survey)" are different series. A matching earlier pattern is not a documented reason, since the original team recorded none, so these exclusions are listed in the log for checking.

`metadata_v2.csv`, which the app uses, holds the non-project-specific studies of `metadata.csv` from 2010 onward. Project-specific studies (post-distribution monitoring, programme beneficiary surveys, impact evaluations) and studies from before 2010 go into `metadata.csv` only. This matches the original files with one exception: study 1111 (a post-distribution monitoring study) is coded as not project-specific but was left out of `metadata_v2.csv` by hand.

These rules approximate the original selection; they do not reproduce it. Of the 643 single-country studies in focus countries that the library created before the snapshot, the original atlas left out 139, and some of those match all the rules above (for example some multi-sector needs assessments and the Ethiopia SESRE 2023). The original team recorded no reasons, so each new decision is listed in the log for checking.

## How the coded columns are filled

`rules.py` holds the keyword rules. `evaluate.py` scores them against the studies coded by hand (rows listed in an update log are skipped). `project_specific` and `idp` are scored on the 522 studies in `metadata.csv`; the topic tags exist only in `metadata_v2.csv`, so they are scored on its 314 studies.

| Column | Source text | Studies scored | Positive by hand | Agreement | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| `project_specific` | title and series | 522 | 197 | 99% | 98% | 99% |
| `idp` | title and universe | 522 | 42 | 96% | 80% | 67% |
| `tag_new_food_insecurity` | notes | 314 | 133 | 99% | 98% | 99% |
| `tag_new_health` | notes | 314 | 216 | 98% | 97% | 100% |
| `tag_new_water_sanitation` | notes | 314 | 115 | 99% | 98% | 100% |
| `tag_new_education` | notes | 314 | 112 | 100% | 100% | 100% |
| `tag_new_welfare` | notes | 314 | 74 | 98% | 99% | 95% |
| `tag_new_labor_employment` | notes | 314 | 43 | 98% | 89% | 98% |
| `tag_new_finance_credit_debt` | notes | 314 | 32 | 99% | 91% | 100% |
| `tag_new_protection` | notes | 314 | 113 | 94% | 85% | 100% |
| `tag_new_gender` | notes | 314 | 53 | 99% | 96% | 100% |
| `tag_new_safety_security_conflict` | notes | 314 | 45 | 96% | 95% | 80% |
| `tag_new_housing_assets` | notes | 314 | 51 | 99% | 96% | 100% |
| `tag_new_shocks` | notes | 314 | 13 | 100% | 100% | 100% |
| `tag_new_agriculture_livestock_fishery` | notes | 314 | 22 | 100% | 100% | 100% |
| `tag_new_subjective_poverty` | notes | 314 | 7 | 99% | 100% | 43% |
| `tag_new_coping_mechanisms` | notes | 314 | 75 | 100% | 100% | 100% |
| `tag_new_demographics` | notes | 314 | 154 | 99% | 99% | 99% |
| `tag_new_social` | notes | 314 | 14 | 98% | 74% | 100% |
| `tag_new_remmitance` | notes | 314 | 6 | 100% | 100% | 100% |
| `tag_new_child_labor` | notes | 314 | 2 | 100% | 100% | 100% |
| `tag_new_migration` | notes | 314 | 8 | 98% | 57% | 100% |

Agreement is high for rare tags even when the rule is weak, so read precision and recall for them: `subjective_poverty` finds fewer than half of the hand-coded cases, and half of the `migration` matches are wrong. The rules were tuned on these same studies, so the scores are likely higher than on new ones.

Missing evidence stays missing:

- `idp` is 1 when the title names internally displaced people, 0 when the title does not and the universe text does not either, and `NA` when there is no universe text.
- Studies without notes in the collector have `NA` topic tags.
- The displacement question flags (`country_of_birth` to `loc_usual`) need the study's variable list, which the collector does not keep, so they are `NA` for new studies.
- When the collector has no study description, `project_specific` is judged from the title alone.

All of these can be filled in by hand from the study's page in the library.
