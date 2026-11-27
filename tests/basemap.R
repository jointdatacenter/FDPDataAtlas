# Run directly with Rscript tests/basemap.R, or as part of R CMD check.
app_dir <- if (dir.exists("inst/shiny-examples/FDPDataAtlas")) {
  "inst/shiny-examples/FDPDataAtlas"
} else {
  system.file("shiny-examples", "FDPDataAtlas", package = "FDPDataAtlas")
}
source(file.path(app_dir, "basemap.R"))

expect_error <- function(expr) {
  stopifnot(inherits(tryCatch(expr, error = identity), "error"))
}

# Geometry order, attributes, and unmatched countries survive alignment.
bounds <- data.frame(ISO_A3 = c("AAA", "BBB", "CCC"),
                     NAME_EN = c("A", "B", "C"))
reference <- data.frame(ISO_A3 = c("BBB", "ZZZ", "AAA"),
                        value = c(20, 999, 10))
aligned <- align_basemap_data(bounds, reference)
stopifnot(identical(aligned$value, c(10, 20, NA_real_)),
          identical(aligned$NAME_EN, bounds$NAME_EN),
          identical(class(aligned), class(bounds)),
          identical(aligned, align_basemap_data(bounds, reference[3:1, ])))
expect_error(align_basemap_data(bounds, rbind(reference, reference[1, ])))
expect_error(align_basemap_data(rbind(bounds, bounds[1, ]), reference))
invalid_keys <- reference
invalid_keys$ISO_A3[1] <- NA_character_
expect_error(align_basemap_data(bounds, invalid_keys))
invalid_keys$ISO_A3[1] <- ""
expect_error(align_basemap_data(bounds, invalid_keys))
stopifnot(all(is.na(align_basemap_data(bounds, reference[FALSE, ])$value)))
reference$value <- c(Inf, 999, NaN)
stopifnot(all(is.na(align_basemap_data(bounds, reference)$value)))

# Empty, missing, constant, and tied series must have a defined outcome.
for (values in list(numeric(0), c(NA_real_, NaN, Inf, -Inf))) {
  stopifnot(identical(basemap_breaks(values), numeric(0)))
}
for (values in list(0, rep(7, 10), rep(-2, 5), c(rep(0, 99), 1),
                    1:100, c(NA, -Inf, 0, 1, Inf))) {
  breaks <- basemap_breaks(values)
  finite <- values[is.finite(values)]
  stopifnot(length(breaks) >= 2L, all(diff(breaks) > 0),
            all(!is.na(cut(finite, breaks, include.lowest = TRUE, right = FALSE))))
}

# Exercise every bundled indicator using the actual geometry order.
bundled <- new.env()
if (file.exists("data/bounds.rda")) {
  load("data/bounds.rda", envir = bundled)
  load("data/ref_data.rda", envir = bundled)
} else {
  utils::data(list = c("bounds", "ref_data"), package = "FDPDataAtlas",
              envir = bundled)
}
for (indicator in unique(bundled$ref_data$indicator)) {
  reference <- bundled$ref_data[bundled$ref_data$indicator == indicator, ]
  aligned <- align_basemap_data(bundled$bounds, reference)
  reordered <- align_basemap_data(bundled$bounds, reference[nrow(reference):1, ])
  expected <- reference$value[match(bundled$bounds$ISO_A3, reference$ISO_A3)]
  expected[!is.finite(expected)] <- NA_real_
  stopifnot(identical(aligned$value, expected),
            identical(aligned$value, reordered$value),
            identical(class(aligned), class(bundled$bounds)),
            identical(attr(aligned, "sf_column"), attr(bundled$bounds, "sf_column")),
            identical(aligned[[attr(bundled$bounds, "sf_column")]],
                      bundled$bounds[[attr(bundled$bounds, "sf_column")]]))
  breaks <- basemap_breaks(aligned$value)
  if (any(is.finite(aligned$value))) {
    stopifnot(all(diff(breaks) > 0),
              all(!is.na(cut(aligned$value[is.finite(aligned$value)], breaks,
                            include.lowest = TRUE, right = FALSE))))
  } else {
    stopifnot(length(breaks) == 0L)
  }
}
cat("Basemap regression checks passed for synthetic cases and",
    length(unique(bundled$ref_data$indicator)), "bundled indicators.\n")
