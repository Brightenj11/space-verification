#!/usr/bin/env bash
set -euo pipefail

# ---- Config you’ll tweak most often ----
PL_DEFAULT="FTFP_INCLXX_HP"           # or pass a different PL as arg
EVENTS_LIST=("1000" "10000")
ENERGIES=("50" "96")
OUTSUBDIR="outputs"                   # under build/

# ---- Resolve paths (prefer build copies of macros if CMake generates them) ----
ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDDIR="${ROOTDIR}/build"
SIMBIN="${BUILDDIR}/sim"

# Where materials.tsv/common_beam.mac live (prefer build/ if present)
MATERIALS_TSV="${BUILDDIR}/materials.tsv"
COMMON_BEAM_MAC="${BUILDDIR}/common_beam.mac"
[[ -f "${MATERIALS_TSV}" ]] || MATERIALS_TSV="${ROOTDIR}/macros/materials.tsv"
[[ -f "${COMMON_BEAM_MAC}" ]] || COMMON_BEAM_MAC="${ROOTDIR}/macros/common_beam.mac"

TMPDIR="${BUILDDIR}/tmp_macros"
LOGDIR="${BUILDDIR}/logs"
OUTDIR="${BUILDDIR}/${OUTSUBDIR}"
mkdir -p "${TMPDIR}" "${LOGDIR}" "${OUTDIR}"

PL="${1:-$PL_DEFAULT}"

# Safety checks
[[ -x "${SIMBIN}" ]] || { echo "!! ${SIMBIN} not found. Build first (cmake .. && make)."; exit 1; }
[[ -f "${MATERIALS_TSV}" ]] || { echo "!! materials.tsv not found in build/ or macros/"; exit 1; }
[[ -f "${COMMON_BEAM_MAC}" ]] || { echo "!! common_beam.mac not found in build/ or macros/"; exit 1; }

# Read materials table (semicolon separated; skip comments/blank)
mapfile -t LINES < <(grep -v '^\s*#' "${MATERIALS_TSV}" | sed '/^\s*$/d')

run_one () {
  local MAT="$1" TMM="$2" SXY="$3" TAG="$4" EVTS="$5" EMEV="$6" PL="$7"
  local MAC="${TMPDIR}/run_${TAG}_${TMM}mm_${EMEV}MeV_${EVTS}e.mac"
  local OUTBASE="proton_output_${TAG}_${TMM}mm_${EMEV}MeV_${EVTS}e_${PL}"
  local LOG="${LOGDIR}/${OUTBASE}.log"

  cat > "${MAC}" <<EOF
/det/material   ${MAT}
/det/thickness  ${TMM} mm
/det/sizeXY     ${SXY} mm
/run/initialize

/gun/energy     ${EMEV} MeV
/control/execute ${COMMON_BEAM_MAC}

/analysis/setFileName ${OUTSUBDIR}/${OUTBASE}
/run/beamOn ${EVTS}
EOF

  echo ">>> ${TAG}: ${TMM}mm, ${EMEV} MeV, ${EVTS} evts, PL=${PL}"
  set +e
  "${SIMBIN}" "${MAC}" "${PL}" > "${LOG}" 2>&1
  local rc=$?; set -e
  if [[ $rc -ne 0 ]]; then echo "!! FAILED: ${OUTBASE} (see ${LOG})"; fi
}

for line in "${LINES[@]}"; do
  IFS=';' read -r MAT TMM SXY TAG <<<"$(echo "${line}" | tr -d '\r' )"
  MAT="$(echo "$MAT" | xargs)"; TMM="$(echo "$TMM" | xargs)"
  SXY="$(echo "$SXY" | xargs)"; TAG="$(echo "$TAG" | xargs)"
  for EMEV in "${ENERGIES[@]}"; do
    for EVTS in "${EVENTS_LIST[@]}"; do
      run_one "${MAT}" "${TMM}" "${SXY}" "${TAG}" "${EVTS}" "${EMEV}" "${PL}"
    done
  done
done

echo "Done. ROOT files → ${OUTDIR}/ ; logs → ${LOGDIR}/"
