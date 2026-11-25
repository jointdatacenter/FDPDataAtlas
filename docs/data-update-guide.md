# Adding new datasets to the FDP Data Atlas

Steps to add studies released in the UNHCR Microdata Library since the last update, so the atlas shows them.

## The data files

| File | What it is |
| --- | --- |
| `inst/extdata/metadata.csv` | Every reviewed UNHCR study, one row each. |
| `inst/extdata/metadata_v2.csv` | The studies the app shows: not project-specific, from 2010 onward. |
| `inst/extdata/metadata_update_<date>.csv` | Log of each update: every new study and whether it was added or why not. |
| `data/metadata.rda` | The packaged copy of `metadata_v2.csv` that the app reads. Built by a script, not edited by hand. |

New studies are added to the end of both CSV files. Existing rows are not changed.

## Setup (once)

- Python 3 and R, with the R packages dplyr, readr and sf.
- The GitHub command line tool (`gh`), signed in.

## Steps

1. Make a branch: `git switch -c data-update-<date>`.

2. Download the World Bank's weekly copy of the UNHCR library catalog into a folder outside the repository:

   ```sh
   gh api -H "Accept: application/vnd.github.raw" repos/worldbank/mdl_collector/contents/data/unhcr/metadata.csv > unhcr_metadata.csv
   gh api -H "Accept: application/vnd.github.raw" repos/worldbank/mdl_collector/contents/data/unhcr/datasets.csv > unhcr_datasets.csv
   ```

3. Add the new studies (from the repository folder, with a new log name each time):

   ```sh
   python3 -I data-raw/unhcr_update/build.py path/to/unhcr_metadata.csv path/to/unhcr_datasets.csv inst/extdata inst/extdata/metadata_update_<date>.csv
   ```

   It prints how many studies it found and added. If there is nothing new, it adds nothing and writes no log.

4. Read the log. Each new study has a decision: added; added to `metadata.csv` only (project-specific or before 2010); or left out (more than one country, country not on the atlas map, site and event records, or a series the atlas left out before). Change a decision by hand only if it is clearly wrong.

5. Rebuild the packaged data and reinstall the package:

   ```sh
   Rscript data-raw/unhcr_update/rebuild_rda.R
   git checkout -- data/bounds.rda data/datadictionary.rda data/ref_data.rda
   R CMD INSTALL --no-test-load .
   ```

   The rebuild prints the old and new number of studies. It also rewrites three other data files with the same contents; the `git checkout` line puts the committed copies back.

6. Run the app and check it:

   ```sh
   cd inst/shiny-examples/FDPDataAtlas
   Rscript -e 'shiny::runApp(".")'
   ```

   - The Database tab shows the new total number of entries.
   - Clicking a country on the map lists its new studies.
   - The Heatmap shows the new years.

7. Commit the two CSV files, the new log and `data/metadata.rda`, then open a pull request.

## If something does not match

- A country name in the library that the script does not recognise is logged as "not in wb_bounds.csv". If it is a new spelling of an atlas country, add it to `COUNTRY_ALIASES` in `data-raw/unhcr_update/build.py`.
- Some studies have no description in the World Bank's copy. They are added with title, country, year and link, and the other fields left as `NA`.
- The rules the script uses to decide what to add, and to fill the topic tags, are described in `data-raw/unhcr_update/README.md`.
