# Keep reference values in geometry order, independently of source row order.
align_basemap_data <- function(bounds, reference) {
  stopifnot("ISO_A3" %in% names(bounds),
            all(c("ISO_A3", "value") %in% names(reference)),
            is.numeric(reference$value))
  keys <- as.character(reference$ISO_A3)
  if (anyNA(keys) || any(!nzchar(keys)) || anyDuplicated(keys)) {
    stop("Basemap reference data must have one nonempty ISO_A3 per country.")
  }
  if (anyNA(bounds$ISO_A3) || any(!nzchar(as.character(bounds$ISO_A3))) ||
      anyDuplicated(bounds$ISO_A3)) {
    stop("Basemap geometry must have one nonempty ISO_A3 per country.")
  }
  bounds$value <- reference$value[match(as.character(bounds$ISO_A3), keys)]
  bounds$value[!is.finite(bounds$value)] <- NA_real_
  bounds
}

# Quantiles can coincide in sparse series; a constant series needs one bin.
basemap_breaks <- function(values) {
  values <- values[is.finite(values)]
  if (!length(values)) return(numeric(0))
  breaks <- sort(unique(as.numeric(stats::quantile(
    values, probs = seq(0, 1, 0.25), names = FALSE
  ))))
  if (length(breaks) == 1L) {
    padding <- max(0.5, abs(breaks) * 0.01)
    breaks <- c(breaks - padding, breaks + padding)
  }
  breaks
}
