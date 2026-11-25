# Rebuild the packaged data in data/ from inst/extdata.
#
# Same steps as the metadata chunk in vignettes/run_app.Rmd, saved with the
# settings usethis::use_data() uses, so it runs without usethis installed.
# Run from the repository root: Rscript data-raw/unhcr_update/rebuild_rda.R

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(sf)
})

extdata <- file.path("inst", "extdata")

old <- new.env()
load(file.path("data", "metadata.rda"), envir = old)

metadata <- read_csv(file.path(extdata, "metadata_v2.csv"), show_col_types = FALSE) %>%
  filter(!is.na(Longitude)) %>%
  dplyr::select(-database, -method_research_instrument, -cit_req, -disclaimer, -Region_v2, -Economy)

bounds <- read_rds(file.path(extdata, "WB_bounds.rds"))
list_inc <- bounds %>%
  st_drop_geometry() %>%
  select(ISO_A3)

list_drop <- c("asy_ven", "NY.GDP.PCAP.CD", "ref_ven", "SL.UEM.TOTL.ZS", "SP.POP.TOTL")
ref_data <- read_rds(file.path(extdata, "WB_bounds_stats.rds")) %>%
  filter(!indicator %in% list_drop) %>%
  filter(ISO_A3 %in% list_inc$ISO_A3)

bounds$geom_valid <- st_is_valid(bounds)
bounds <- bounds %>%
  filter(geom_valid == "TRUE")

ref_data <- ref_data %>%
  mutate(indicator = ifelse(indicator == "Refugee population by country or territory of asylum (2021) (WDI)",
                            "Refugee population by country or territory of asylum (2021) (UNHCR Refugee Data Finder)",
                            indicator)) %>%
  mutate(indicator = ifelse(indicator == "Refugee population by country or territory of origin (2021) (WDI)",
                            "Refugee population by country or territory of origin (2021) (UNHCR Refugee Data Finder)",
                            indicator))

datadictionary <- read_csv(file.path(extdata, "datadictionary.csv"), show_col_types = FALSE)

for (name in c("metadata", "bounds", "ref_data", "datadictionary")) {
  save(list = name, file = file.path("data", paste0(name, ".rda")), compress = "bzip2", version = 2)
}

cat("metadata rows:", nrow(old$metadata), "->", nrow(metadata), "\n")
cat("metadata columns unchanged:", identical(sort(names(old$metadata)), sort(names(metadata))), "\n")
cat("countries:", n_distinct(old$metadata$nation_abbreviation), "->", n_distinct(metadata$nation_abbreviation), "\n")
cat("years:", paste(range(metadata$year, na.rm = TRUE), collapse = " to "), "\n")
