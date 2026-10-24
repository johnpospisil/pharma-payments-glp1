# HonestDiD relative-magnitudes bounds from a saved universal-base event study
# (DEV-3): explicit search grid, because the default grid (scaled by the SEs) misses the
# interval when estimates are very precise. Usage: Rscript honest.R <cs.json> <out.json>
suppressPackageStartupMessages({library(HonestDiD); library(jsonlite)})
a <- commandArgs(trailingOnly = TRUE)
r <- fromJSON(a[1])
e <- r$event_vcov$e; b <- r$event_vcov$beta; V <- as.matrix(r$event_vcov$V)
keep <- which(e >= -4 & e <= 3 & e != -1)
ek <- e[keep]; npre <- sum(ek < 0); npost <- sum(ek >= 0)
lvec <- rep(1 / npost, npost)
theta <- sum(lvec * b[keep][ek >= 0])
rm <- createSensitivityResults_relativeMagnitudes(
  betahat = b[keep], sigma = V[keep, keep], numPrePeriods = npre, numPostPeriods = npost,
  l_vec = lvec, Mbarvec = seq(0, 2, by = 0.25), gridPoints = 20000,
  grid.lb = theta - 0.5, grid.ub = theta + 0.5)
ok <- !is.na(rm$lb) & !is.na(rm$ub)
covers0 <- ok & rm$lb <= 0 & rm$ub >= 0
bd <- if (any(covers0)) min(rm$Mbar[covers0]) else if (all(ok)) "above 2" else "not established"
# smoothness (Delta^SD), supplementary: M = 0 lets the pre-trend continue linearly
sd <- tryCatch(createSensitivityResults(
  betahat = b[keep], sigma = V[keep, keep], numPrePeriods = npre, numPostPeriods = npost,
  l_vec = lvec, Mvec = c(0, 0.0025, 0.005, 0.01)), error = function(err) NULL)
write_json(list(theta = theta, rm = rm, breakdown_mbar = bd, smoothness = sd), a[2],
           auto_unbox = TRUE, digits = 8, pretty = TRUE)
print(rm); cat("breakdown:", bd, "\n")
