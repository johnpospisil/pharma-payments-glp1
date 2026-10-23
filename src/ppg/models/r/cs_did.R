# Callaway & Sant'Anna event study for one brand (PREREGISTRATION.md §6, DEV-1).
# Usage: Rscript cs_did.R <input.parquet> <output.json> [control_group] [biters]
# Input columns: npi, year, y, g, cluster_id, specialty_group, region, log_dm, log_tot,
#                other_glp1, urban. Output: att_gt, event study, overall ATTs, joint
#                pre-trend Wald test, HonestDiD relative-magnitudes bounds.
suppressPackageStartupMessages({
  library(did); library(arrow); library(jsonlite); library(HonestDiD)
})
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]; out <- args[2]
cg <- ifelse(length(args) >= 3, args[3], "notyettreated")
biters <- ifelse(length(args) >= 4, as.integer(args[4]), 999L)
set.seed(20261023)

d <- as.data.frame(read_parquet(inp))
d$specialty_group <- factor(d$specialty_group)
d$region <- factor(d$region)
balanced <- isTRUE(as.logical(Sys.getenv("PPG_BALANCED", "FALSE")))
base <- Sys.getenv("PPG_BASE", "varying")        # "universal" for HonestDiD (Rambachan & Roth)
xf <- if (isTRUE(as.logical(Sys.getenv("PPG_NOCOV", "FALSE")))) ~1 else
  ~ specialty_group + region + log_dm + log_tot + other_glp1 + urban

t0 <- Sys.time()
a <- att_gt(yname = "y", tname = "year", idname = "npi", gname = "g",
            xformla = xf,
            data = d, panel = TRUE, allow_unbalanced_panel = !balanced,
            control_group = cg, est_method = "dr", base_period = base,
            clustervars = c("npi", "cluster_id"), bstrap = TRUE, cband = TRUE,
            biters = biters, print_details = FALSE)
fit_s <- as.numeric(difftime(Sys.time(), t0, units = "secs"))

es  <- aggte(a, type = "dynamic", na.rm = TRUE, bstrap = TRUE, biters = biters,
             clustervars = c("npi", "cluster_id"))
o03 <- aggte(a, type = "dynamic", min_e = 0, max_e = 3, na.rm = TRUE, biters = biters,
             clustervars = c("npi", "cluster_id"))
o13 <- aggte(a, type = "dynamic", min_e = 1, max_e = 3, na.rm = TRUE, biters = biters,
             clustervars = c("npi", "cluster_id"))

# cluster-robust covariance of the event-time estimates from the influence functions
inf <- es$inf.function$dynamic.inf.func.e
ids <- unique(a$DIDparams$data[[a$DIDparams$idname]])
cl_of <- d$cluster_id[match(ids, d$npi)]
n <- nrow(inf)
stopifnot(n == length(ids))
V <- crossprod(rowsum(inf, cl_of)) / n^2
e <- es$egt
pre <- which(e <= -2)
wald <- NULL
if (length(pre) > 0) {
  b <- es$att.egt[pre]; Vp <- V[pre, pre, drop = FALSE]
  stat <- as.numeric(t(b) %*% solve(Vp) %*% b)
  wald <- list(stat = stat, df = length(pre), p = pchisq(stat, length(pre), lower.tail = FALSE))
}

# HonestDiD (Rambachan & Roth): relative magnitudes, average of e = 0..3
honest <- NULL
keep <- which(e >= -5 & e <= 3 & e != -1)
ek <- e[keep]; npre <- sum(ek < 0); npost <- sum(ek >= 0)
if (npre >= 1 && npost >= 1) {
  lvec <- rep(1 / npost, npost)
  orig <- constructOriginalCS(betahat = es$att.egt[keep], sigma = V[keep, keep],
                              numPrePeriods = npre, numPostPeriods = npost, l_vec = lvec)
  rm <- createSensitivityResults_relativeMagnitudes(
    betahat = es$att.egt[keep], sigma = V[keep, keep], numPrePeriods = npre,
    numPostPeriods = npost, l_vec = lvec, Mbarvec = seq(0, 2, by = 0.25))
  breakdown <- suppressWarnings(min(rm$Mbar[rm$lb <= 0 & rm$ub >= 0]))
  honest <- list(original = as.list(orig), rm = rm, breakdown_mbar = breakdown)
}

gt <- data.frame(group = a$group, t = a$t, att = a$att, se = a$se)
res <- list(
  control_group = cg, balanced = balanced, base_period = base, covariates = deparse(xf), fit_seconds = fit_s, n_units = n,
  n_obs = nrow(d), crit_val_gt = a$c,
  att_gt = gt,
  event = data.frame(e = e, att = es$att.egt, se = es$se.egt,
                     se_cluster_if = sqrt(diag(V))),
  crit_val_event = es$crit.val.egt,
  overall_0_3 = list(att = o03$overall.att, se = o03$overall.se),
  overall_1_3 = list(att = o13$overall.att, se = o13$overall.se),
  pretrend_wald = wald, honestdid = honest,
  cohorts = as.data.frame(table(d$g[!duplicated(d$npi)]))
)
write_json(res, out, auto_unbox = TRUE, digits = 10, pretty = TRUE)
cat(sprintf("done in %.0fs: ATT(0-3) = %.4f (se %.4f)\n", fit_s, o03$overall.att, o03$overall.se))
