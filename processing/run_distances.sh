#!/usr/bin/env bash
set -euo pipefail

PY="${PY:-/home/jmurphy/miniconda3/envs/skopt/bin/python}"
ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)/build/outputs}"
PROC="${PROC:-$(cd "$(dirname "$0")" && pwd)}"
WTS="${WTS:-$PROC/AP9_HEO_2k10k_i60_weighting_for_runs_10_15_20_30_50_60_80_100_150_200_300.csv}"
SCRIPT="${SCRIPT:-$PROC/build_ml_windows_dataset_v2.py}"
OUTDIR="${OUTDIR:-$PROC/ml_datasets}"

mkdir -p "$OUTDIR"

run_dataset() {
  local tier_name="$1"
  local source_case="$2"
  shift 2

  echo "[RUN] ${tier_name} sc${source_case}"
  "$PY" "$SCRIPT" \
    --root-dir "$ROOT" \
    --weights-csv "$WTS" \
    --source-cases "$source_case" \
    --beam-energies 10 15 20 30 50 60 80 100 150 200 300 \
    --window-s 10 \
    --samples-per-group 500 \
    --allow-missing-energies \
    --dataset-view ml \
    "$@"
}

# 6m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_6m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 6.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_6m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_6m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_6m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_6m_sc${sc}_manifest.json"
done

# 8m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_8m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 8.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_8m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_8m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_8m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_8m_sc${sc}_manifest.json"
done

# 10m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_10m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 10.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_10m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_10m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_10m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_10m_sc${sc}_manifest.json"
done

# 15m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_15m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 15.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_15m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_15m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_15m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_15m_sc${sc}_manifest.json"
done

# 20m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_20m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 20.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_20m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_20m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_20m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_20m_sc${sc}_manifest.json"
done

# 30m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_30m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 30.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_30m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_30m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_30m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_30m_sc${sc}_manifest.json"
done

# 40m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_40m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 40.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_40m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_40m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_40m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_40m_sc${sc}_manifest.json"
done

# 50m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_50m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 50.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_50m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_50m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_50m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_50m_sc${sc}_manifest.json"
done

# 75m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_75m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 75.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_75m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_75m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_75m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_75m_sc${sc}_manifest.json"
done

# 100m
for sc in 50 95; do
  run_dataset "tier6_highgt60_dist_100m" "$sc" \
    --no-ap9-average \
    --flux-regime high_gt60:60:1e4:1.0 \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 0.35 \
    --Eth-MeV 0.5 \
    --sigmaEfrac 0.10 \
    --sigmaT-ns 5.0 \
    --coinc-ns 500 \
    --panel-x-m 100.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier6_highgt60_dist_100m_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier6_highgt60_dist_100m_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier6_highgt60_dist_100m_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier6_highgt60_dist_100m_sc${sc}_manifest.json"
done