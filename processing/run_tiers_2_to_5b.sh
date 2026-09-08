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

for sc in 50 75 95; do
  run_dataset "tier2_flatbg2hz_selfbg010_ap9avg" "$sc" \
    --bg-rate-hz 2.0 \
    --bg-E-mean-MeV 2.0 \
    --self-bg-material G4_Al \
    --self-bg-rout-mm 70 \
    --self-bg-rin-mm 65 \
    --self-bg-scale 0.10 \
    --eff 1.0 \
    --Eth-MeV 0.1 \
    --sigmaEfrac 0.0 \
    --sigmaT-ns 0.0 \
    --coinc-ns 500 \
    --panel-x-m 2.0 \
    --panel-y-size-m 1.0 \
    --panel-z-size-m 1.0 \
    --out "$OUTDIR/tier2_flatbg2hz_selfbg010_ap9avg_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier2_flatbg2hz_selfbg010_ap9avg_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier2_flatbg2hz_selfbg010_ap9avg_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier2_flatbg2hz_selfbg010_ap9avg_sc${sc}_manifest.json"
done

for sc in 50 75 95; do
  run_dataset "tier3_resp035_thr05_smear_ap9avg" "$sc" \
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
    --panel-x-m 2.0 \
    --panel-y-size-m 1.0 \
    --panel-z-size-m 1.0 \
    --out "$OUTDIR/tier3_resp035_thr05_smear_ap9avg_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier3_resp035_thr05_smear_ap9avg_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier3_resp035_thr05_smear_ap9avg_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier3_resp035_thr05_smear_ap9avg_sc${sc}_manifest.json"
done

for sc in 50 75 95; do
  run_dataset "tier4a_standoff5m_ap9avg" "$sc" \
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
    --panel-x-m 5.0 \
    --panel-y-size-m 1.0 \
    --panel-z-size-m 1.0 \
    --out "$OUTDIR/tier4a_standoff5m_ap9avg_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier4a_standoff5m_ap9avg_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier4a_standoff5m_ap9avg_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier4a_standoff5m_ap9avg_sc${sc}_manifest.json"
done

for sc in 50 75 95; do
  run_dataset "tier4b_panel0p5m_ap9avg" "$sc" \
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
    --panel-x-m 2.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier4b_panel0p5m_ap9avg_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier4b_panel0p5m_ap9avg_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier4b_panel0p5m_ap9avg_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier4b_panel0p5m_ap9avg_sc${sc}_manifest.json"
done

for sc in 50 75 95; do
  run_dataset "tier4c_standoff5m_panel0p5m_ap9avg" "$sc" \
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
    --panel-x-m 5.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier4c_standoff5m_panel0p5m_ap9avg_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier4c_standoff5m_panel0p5m_ap9avg_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier4c_standoff5m_panel0p5m_ap9avg_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier4c_standoff5m_panel0p5m_ap9avg_sc${sc}_manifest.json"
done

for sc in 50 75 95; do
  run_dataset "tier5a_highgt60_1e4" "$sc" \
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
    --panel-x-m 5.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier5a_highgt60_1e4_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier5a_highgt60_1e4_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier5a_highgt60_1e4_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier5a_highgt60_1e4_sc${sc}_manifest.json"
done

for sc in 50 75 95; do
  run_dataset "tier5b_lowgt60_1e2" "$sc" \
    --no-ap9-average \
    --flux-regime low_gt60:60:1e2:1.0 \
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
    --panel-x-m 5.0 \
    --panel-y-size-m 0.5 \
    --panel-z-size-m 0.5 \
    --out "$OUTDIR/tier5b_lowgt60_1e2_sc${sc}.csv" \
    --debug-out "$OUTDIR/tier5b_lowgt60_1e2_sc${sc}_debug.csv" \
    --summary-out "$OUTDIR/tier5b_lowgt60_1e2_sc${sc}_library_summary.csv" \
    --manifest-out "$OUTDIR/tier5b_lowgt60_1e2_sc${sc}_manifest.json"
done
