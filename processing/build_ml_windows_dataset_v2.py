#!/usr/bin/env python3
"""
build_ml_windows_dataset.py

Build a machine-learning-ready CSV of fixed measurement windows from Geant4
escape-neutron ROOT files.

This script is intentionally derived from the same overall pattern as
build_tier15_profiles_dataset.py and random_seed_variability_qc.py:
- physical run identity comes from RunConfig, NOT the filename
- EscapeNeutrons are projected to a virtual detector plane in Python
- mono-energetic proton runs are mixed with AP9-derived energy weights
- output rows correspond to synthetic detector measurement windows

What this script is for
-----------------------
- Read many ROOT files from a Geant4 output directory
- Understand which physical case each file belongs to (WGPu, W, Al variants, Vacuum, etc.)
- Use the AP9 weighting CSV to convert the mono-energetic library into 10 s windows
- Optionally approximate high-flux / low-flux orbital windows by re-scaling the
  AP9 spectral shape above a user-chosen threshold (default idea: >60 MeV)
- Write one row per synthetic measurement window, plus a library summary CSV
- Optionally assign grouped train / validation / test splits

Important assumptions
---------------------
1) AP9 weighting file:
   If the weighting CSV has band_fluence_cm2, that fluence is converted to an
   average band flux [cm^-2 s^-1] by dividing by --fluence-duration-s
   (default = 7 days = 604800 s).

2) Flux regimes:
   If you pass one or more --flux-regime specs, the script keeps the AP9 energy
   shape but scales the whole spectrum so that the integral flux above the
   requested threshold equals the target value. This is a practical way to
   approximate "high-flux" or "low-flux" orbital windows when you do not yet
   have a time-resolved energy spectrum.

3) Projected source area:
   By default the incident proton normalization uses a circular projected area
   from --target-radius-cm. If you want a more realistic spacecraft projected
   area instead, pass --projected-area-cm2 explicitly.

4) Leakage control:
   The script can assign grouped train / validation / test splits. The default
   grouping is conservative: scenario_id + source_case + flux_regime, stratified
   by class_label. That avoids random row mixing from the same underlying Geant4
   library.

Typical usage
-------------
pip install uproot pandas numpy

python build_ml_windows_dataset_v2.py \
  --root-dir ~/geant4-apps/geant4-11-SPACE/build/outputs \
  --weights-csv ~/geant4-apps/geant4-11-SPACE/processing/AP9_HEO_2k10k_i60_weighting_for_runs_10_15_20_30_50_60_80_100_150_200_300.csv \
  --window-s 10 \
  --samples-per-group 500 \
  --allow-missing-energies \
  --dataset-view ml \
  --write-source-case-csvs \
  --debug-out ~/geant4-apps/geant4-11-SPACE/processing/build_ml_windows_dataset_debug.csv \
  --manifest-out ~/geant4-apps/geant4-11-SPACE/processing/build_ml_windows_dataset_manifest.json \
  --out ~/geant4-apps/geant4-11-SPACE/processing/build_ml_windows_dataset_ml.csv


"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path
import re
import warnings
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import uproot  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "This script requires the 'uproot' package. Install it with:\n"
        "  pip install uproot pandas numpy\n"
        f"Original error: {exc}"
    )


# ---------------------------------------------------------------------
# Physics helpers
# ---------------------------------------------------------------------

C_M_PER_NS = 0.299792458
M_N_MEV = 939.56542052


def neutron_speed_m_per_ns(E_MeV: np.ndarray) -> np.ndarray:
    E = np.asarray(E_MeV, dtype=float)
    gamma = 1.0 + np.maximum(E, 0.0) / M_N_MEV
    beta2 = 1.0 - 1.0 / (gamma * gamma)
    beta2 = np.clip(beta2, 0.0, 1.0)
    beta = np.sqrt(beta2)
    return beta * C_M_PER_NS


# ---------------------------------------------------------------------
# Detector / response / source regime dataclasses
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class DetectorPlaneX:
    x_m: float
    y_center_m: float
    z_center_m: float
    y_size_m: float
    z_size_m: float

    @property
    def area_m2(self) -> float:
        return float(self.y_size_m * self.z_size_m)


@dataclass(frozen=True)
class DetectorResponse:
    eff: float = 1.0
    Eth_MeV: float = 0.1
    sigmaEfrac: float = 0.0
    sigmaT_ns: float = 0.0
    bg_rate_hz: float = 0.0
    bg_E_mean_MeV: float = 2.0
    coinc_ns: float = 500.0


@dataclass(frozen=True)
class FluxRegime:
    name: str
    mode: str  # "average" or "target_above_threshold"
    threshold_MeV: float = 60.0
    target_flux_cm2_s: float | None = None
    duty_fraction: float = 1.0
    notes: str = ""


# ---------------------------------------------------------------------
# Library structures
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioKey:
    snmMaterial: str
    sphereOuterR_mm: float
    sphereInnerR_mm: float
    beamE_MeV: float
    beamDirX: float
    beamDirY: float
    beamDirZ: float
    physicsListName: str

    def scenario_id(self) -> str:
        mat = self.snmMaterial.replace(" ", "")
        return (
            f"mat={mat}|Rout={self.sphereOuterR_mm:g}|Rin={self.sphereInnerR_mm:g}|"
            f"u=({self.beamDirX:g},{self.beamDirY:g},{self.beamDirZ:g})|phys={self.physicsListName}"
        )


@dataclass
class RunChunk:
    source_file: str
    n_events_total: int
    seed_id: str = "UNKNOWN"
    event_templates_E: List[np.ndarray] = field(default_factory=list)
    event_templates_t: List[np.ndarray] = field(default_factory=list)
    n_escape_rows: int = 0
    n_geom_hits: int = 0
    n_events_with_geom_hit: int = 0


@dataclass
class ScenarioLibrary:
    key: ScenarioKey
    run_chunks: List[RunChunk] = field(default_factory=list)

    def add_chunk(self, chunk: RunChunk) -> None:
        self.run_chunks.append(chunk)

    @property
    def n_files(self) -> int:
        return len(self.run_chunks)

    @property
    def n_events_total(self) -> int:
        return int(sum(c.n_events_total for c in self.run_chunks))

    @property
    def n_escape_rows(self) -> int:
        return int(sum(c.n_escape_rows for c in self.run_chunks))

    @property
    def n_geom_hits(self) -> int:
        return int(sum(c.n_geom_hits for c in self.run_chunks))

    @property
    def n_events_with_geom_hit(self) -> int:
        return int(sum(c.n_events_with_geom_hit for c in self.run_chunks))

    @property
    def p_event_geom_hit(self) -> float:
        n = self.n_events_total
        return float(self.n_events_with_geom_hit / n) if n > 0 else 0.0

    @property
    def mean_geom_hits_per_primary(self) -> float:
        n = self.n_events_total
        return float(self.n_geom_hits / n) if n > 0 else 0.0

    @property
    def seed_ids(self) -> List[str]:
        vals = sorted({str(c.seed_id) for c in self.run_chunks})
        return vals

    def all_templates(self) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        E_all: List[np.ndarray] = []
        t_all: List[np.ndarray] = []
        for chunk in self.run_chunks:
            E_all.extend(chunk.event_templates_E)
            t_all.extend(chunk.event_templates_t)
        return E_all, t_all


# ---------------------------------------------------------------------
# Classification / parsing helpers
# ---------------------------------------------------------------------

def parse_conf_label(source_case: object) -> str:
    s = str(source_case)
    if s.endswith(".0"):
        s = s[:-2]
    return s


def material_to_class(material: str) -> str:
    s = (material or "").lower()
    if "wgpu" in s or "heu" in s or "u235" in s or "u-235" in s or "pu239" in s or "pu-239" in s:
        return "SNM"
    if s in {"g4_w", "w", "tungsten"}:
        return "HighZ"
    return "Benign"


def material_variant(material: str, rout_mm: float, rin_mm: float) -> str:
    s = material or "UNKNOWN"
    return f"{s}|Rout={rout_mm:g}|Rin={rin_mm:g}"


def extract_seed_from_filename(stem: str, seed_regex: re.Pattern[str] | None) -> str:
    if seed_regex is None:
        return "UNKNOWN"
    m = seed_regex.search(stem)
    if not m:
        return "UNKNOWN"
    if "seed" in m.groupdict():
        return str(m.group("seed"))
    return str(m.group(1))


def projected_area_cm2(target_radius_cm: float | None, explicit_area_cm2: float | None) -> float:
    if explicit_area_cm2 is not None:
        if explicit_area_cm2 <= 0:
            raise ValueError("--projected-area-cm2 must be positive")
        return float(explicit_area_cm2)
    if target_radius_cm is None or target_radius_cm <= 0:
        raise ValueError("Provide either a positive --target-radius-cm or --projected-area-cm2")
    return float(math.pi * target_radius_cm * target_radius_cm)


# ---------------------------------------------------------------------
# Detector projection / response
# ---------------------------------------------------------------------

def ray_hits_detector_plane_x(
    pos_m: np.ndarray,
    dir_u: np.ndarray,
    det: DetectorPlaneX,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Ray-plane intersection with a rectangle in plane x = det.x_m.
    Returns:
        hit_mask, path_length_m
    """
    x0 = pos_m[:, 0]
    ux = dir_u[:, 0]

    s = np.full(len(pos_m), np.nan, dtype=float)
    valid = np.abs(ux) > 1e-12
    s[valid] = (det.x_m - x0[valid]) / ux[valid]
    forward = s > 0.0
    ok = valid & forward

    y = pos_m[:, 1] + s * dir_u[:, 1]
    z = pos_m[:, 2] + s * dir_u[:, 2]

    y_half = det.y_size_m / 2.0
    z_half = det.z_size_m / 2.0
    in_rect = (
        (np.abs(y - det.y_center_m) <= y_half)
        & (np.abs(z - det.z_center_m) <= z_half)
    )
    hit = ok & in_rect
    return hit, s


def apply_response(
    rng: np.random.Generator,
    E_true: np.ndarray,
    t_true_ns: np.ndarray,
    resp: DetectorResponse,
) -> Tuple[np.ndarray, np.ndarray]:
    if len(E_true) == 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float)

    E = np.asarray(E_true, dtype=float)
    t = np.asarray(t_true_ns, dtype=float)

    above = E >= resp.Eth_MeV
    if not np.any(above):
        return np.empty(0, dtype=float), np.empty(0, dtype=float)

    E = E[above]
    t = t[above]

    eff = max(0.0, min(1.0, resp.eff))
    if eff < 1.0:
        keep = rng.random(len(E)) < eff
        if not np.any(keep):
            return np.empty(0, dtype=float), np.empty(0, dtype=float)
        E = E[keep]
        t = t[keep]

    if resp.sigmaEfrac > 0.0:
        sigmaE = resp.sigmaEfrac * np.maximum(E, 0.0)
        E = E + rng.normal(0.0, sigmaE, size=len(E))
        E = np.clip(E, 0.0, None)

    if resp.sigmaT_ns > 0.0:
        t = t + rng.normal(0.0, resp.sigmaT_ns, size=len(t))

    return E, t


def add_background_hits(
    rng: np.random.Generator,
    resp: DetectorResponse,
    window_s: float,
    Emax_MeV: float,
) -> Tuple[np.ndarray, np.ndarray]:
    if resp.bg_rate_hz <= 0.0 or window_s <= 0.0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float)
    n_bg = int(rng.poisson(resp.bg_rate_hz * window_s))
    if n_bg <= 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float)
    E_bg = rng.exponential(resp.bg_E_mean_MeV, size=n_bg)
    E_bg = np.clip(E_bg, 0.0, Emax_MeV)
    t_bg = rng.uniform(0.0, window_s * 1e9, size=n_bg)
    return E_bg, t_bg


def coincidence_cluster_sizes(t_ns: np.ndarray, coinc_ns: float) -> np.ndarray:
    if len(t_ns) == 0:
        return np.empty(0, dtype=int)
    t = np.sort(np.asarray(t_ns, dtype=float))
    gaps = np.diff(t)
    breaks = np.where(gaps > coinc_ns)[0]
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks + 1, [len(t)]))
    return (ends - starts).astype(int)


# ---------------------------------------------------------------------
# ROOT readers
# ---------------------------------------------------------------------

def _read_single_row_config(root: uproot.ReadOnlyDirectory) -> dict:
    if "RunConfig" not in root:
        raise KeyError("RunConfig TTree not found")
    df = root["RunConfig"].arrays(library="pd")
    if len(df) != 1:
        raise ValueError(f"RunConfig expected 1 row, found {len(df)}")
    return df.iloc[0].to_dict()


def _get_events_count(root: uproot.ReadOnlyDirectory) -> int:
    if "Events" in root:
        return int(root["Events"].num_entries)
    if "EscapeNeutrons" in root:
        arr = root["EscapeNeutrons"].arrays(["eventID"], library="np")
        if len(arr["eventID"]) == 0:
            return 0
        return int(np.max(arr["eventID"]) + 1)
    raise KeyError("Neither Events nor EscapeNeutrons found")


def _read_escape_df(root: uproot.ReadOnlyDirectory) -> pd.DataFrame:
    if "EscapeNeutrons" not in root:
        raise KeyError("EscapeNeutrons TTree not found")
    needed = [
        "eventID",
        "escapeE_MeV",
        "escapeT_ns",
        "dirX",
        "dirY",
        "dirZ",
        "posX_mm",
        "posY_mm",
        "posZ_mm",
    ]
    return root["EscapeNeutrons"].arrays(needed, library="pd")


# ---------------------------------------------------------------------
# AP9 weight handling
# ---------------------------------------------------------------------

def load_weight_table(
    weights_csv: Path,
    fluence_duration_s: float,
    total_flux_cm2_s: float | None = None,
) -> Dict[str, Dict[float, dict]]:
    """
    Returns
    -------
    dict[source_case][beamE_MeV] -> {
        'band_fluence_cm2': float or nan,
        'band_flux_cm2_s': float or nan,
        'weight': float or nan,
    }
    """
    df = pd.read_csv(weights_csv)
    if df.empty:
        raise ValueError(f"Weight CSV is empty: {weights_csv}")

    if "conf_level" in df.columns:
        source_case_col = "conf_level"
    elif "source_case" in df.columns:
        source_case_col = "source_case"
    else:
        df["source_case"] = "default"
        source_case_col = "source_case"

    energy_col = None
    for cand in ["representative_run_MeV", "beamE_MeV", "energy_MeV", "energy"]:
        if cand in df.columns:
            energy_col = cand
            break
    if energy_col is None:
        raise ValueError(
            "Could not identify energy column in weights CSV. Expected one of: "
            "representative_run_MeV, beamE_MeV, energy_MeV, energy"
        )

    has_band_fluence = "band_fluence_cm2" in df.columns
    weight_col = None
    for cand in ["normalized_weight_gt10", "weight", "normalized_weight", "probability"]:
        if cand in df.columns:
            weight_col = cand
            break

    if not has_band_fluence and weight_col is None:
        raise ValueError(
            "Weights CSV must contain either band_fluence_cm2 or a normalized weight column"
        )
    if not has_band_fluence and total_flux_cm2_s is None:
        raise ValueError(
            "Weight CSV only has normalized weights. Also pass --total-flux-cm2-s."
        )

    out: Dict[str, Dict[float, dict]] = {}
    for _, row in df.iterrows():
        source_case = parse_conf_label(row[source_case_col])
        E = float(row[energy_col])
        rec: dict = {}

        if has_band_fluence:
            flu = float(row["band_fluence_cm2"])
            rec["band_fluence_cm2"] = flu
            rec["band_flux_cm2_s"] = flu / fluence_duration_s
        else:
            rec["band_fluence_cm2"] = math.nan
            rec["band_flux_cm2_s"] = math.nan

        if weight_col is not None:
            rec["weight"] = float(row[weight_col])
        else:
            rec["weight"] = math.nan

        out.setdefault(source_case, {})[E] = rec

    for source_case, mapping in out.items():
        have_flux = all(np.isfinite(v["band_flux_cm2_s"]) for v in mapping.values())
        if not have_flux:
            weights = np.array([float(v["weight"]) for v in mapping.values()], dtype=float)
            if np.any(weights < 0):
                raise ValueError(f"Negative weights encountered for source case {source_case}")
            s = weights.sum()
            if s <= 0:
                raise ValueError(f"Weights sum to zero for source case {source_case}")
            for _, rec in mapping.items():
                w = float(rec["weight"]) / s
                rec["weight"] = w
                rec["band_flux_cm2_s"] = w * float(total_flux_cm2_s)
                rec["band_fluence_cm2"] = rec["band_flux_cm2_s"] * fluence_duration_s
    return out


def parse_flux_regime_spec(spec: str) -> FluxRegime:
    """
    Format
    ------
    name:threshold_MeV:target_flux_cm2_s[:duty_fraction]

    Example
    -------
    high_gt60:60:1e5:0.125
    """
    parts = [p.strip() for p in spec.split(":")]
    if len(parts) not in {3, 4}:
        raise ValueError(
            f"Invalid --flux-regime spec '{spec}'. Expected "
            "'name:threshold_MeV:target_flux_cm2_s[:duty_fraction]'."
        )
    name = parts[0]
    threshold = float(parts[1])
    target_flux = float(parts[2])
    duty = float(parts[3]) if len(parts) == 4 else 1.0
    if target_flux <= 0:
        raise ValueError("Target flux in --flux-regime must be positive")
    if duty <= 0:
        raise ValueError("Duty fraction in --flux-regime must be positive")
    return FluxRegime(
        name=name,
        mode="target_above_threshold",
        threshold_MeV=threshold,
        target_flux_cm2_s=target_flux,
        duty_fraction=duty,
        notes=f"Scaled AP9 spectral shape to target >={threshold:g} MeV flux of {target_flux:g} cm^-2 s^-1",
    )


def build_flux_regimes(regime_specs: Sequence[str], include_ap9_average: bool) -> List[FluxRegime]:
    regimes: List[FluxRegime] = []
    if include_ap9_average:
        regimes.append(
            FluxRegime(
                name="ap9_average",
                mode="average",
                threshold_MeV=60.0,
                duty_fraction=1.0,
                notes="Average flux implied directly by the AP9 fluence duration.",
            )
        )
    for spec in regime_specs:
        regimes.append(parse_flux_regime_spec(spec))
    if not regimes:
        raise ValueError("At least one source regime must be defined.")
    return regimes


def scale_source_weights_for_regime(
    source_weights: Dict[float, dict],
    regime: FluxRegime,
) -> Tuple[Dict[float, float], float, float, float, float]:
    """
    Returns
    -------
    full_scaled_flux_map : dict[E] -> scaled band flux [cm^-2 s^-1]
    scale_factor
    base_total_flux_cm2_s
    scaled_total_flux_cm2_s
    scaled_flux_above_threshold_cm2_s
    """
    base_flux_map = {
        float(E): float(rec["band_flux_cm2_s"])
        for E, rec in source_weights.items()
    }
    base_total = float(sum(base_flux_map.values()))

    if regime.mode == "average":
        scale = 1.0
    elif regime.mode == "target_above_threshold":
        thr = float(regime.threshold_MeV)
        base_above = float(sum(v for E, v in base_flux_map.items() if E >= thr))
        if base_above <= 0.0:
            raise ValueError(
                f"Cannot scale source regime '{regime.name}' because AP9 source case has "
                f"no flux above {thr:g} MeV."
            )
        assert regime.target_flux_cm2_s is not None
        scale = float(regime.target_flux_cm2_s) / base_above
    else:
        raise ValueError(f"Unsupported FluxRegime.mode: {regime.mode}")

    scaled = {E: v * scale for E, v in base_flux_map.items()}
    scaled_total = float(sum(scaled.values()))
    scaled_above = float(sum(v for E, v in scaled.items() if E >= regime.threshold_MeV))
    return scaled, scale, base_total, scaled_total, scaled_above


# ---------------------------------------------------------------------
# Library construction
# ---------------------------------------------------------------------

def build_library(
    root_dir: Path,
    det: DetectorPlaneX,
    Eth_MeV: float,
    root_glob: str = "*.root",
    energy_match_decimals: int = 6,
    beam_energies_filter: Sequence[float] | None = None,
    seed_regex: re.Pattern[str] | None = None,
) -> Dict[ScenarioKey, ScenarioLibrary]:
    root_files = sorted(root_dir.glob(root_glob))
    if not root_files:
        raise FileNotFoundError(f"No ROOT files found in {root_dir} matching {root_glob}")

    beam_energies_filter_rounded = None
    if beam_energies_filter:
        beam_energies_filter_rounded = {
            round(float(e), energy_match_decimals) for e in beam_energies_filter
        }

    libraries: Dict[ScenarioKey, ScenarioLibrary] = {}

    for path in root_files:
        with uproot.open(path) as root:
            cfg = _read_single_row_config(root)
            n_events_total = _get_events_count(root)
            esc = _read_escape_df(root)

        beamE_MeV = round(float(cfg.get("beamE_MeV", math.nan)), energy_match_decimals)
        if beam_energies_filter_rounded is not None and beamE_MeV not in beam_energies_filter_rounded:
            continue

        key = ScenarioKey(
            snmMaterial=str(cfg.get("snmMaterial", "UNKNOWN")),
            sphereOuterR_mm=round(float(cfg.get("sphereOuterR_mm", math.nan)), energy_match_decimals),
            sphereInnerR_mm=round(float(cfg.get("sphereInnerR_mm", math.nan)), energy_match_decimals),
            beamE_MeV=beamE_MeV,
            beamDirX=round(float(cfg.get("beamDirX", math.nan)), energy_match_decimals),
            beamDirY=round(float(cfg.get("beamDirY", math.nan)), energy_match_decimals),
            beamDirZ=round(float(cfg.get("beamDirZ", math.nan)), energy_match_decimals),
            physicsListName=str(cfg.get("physicsListName", "UNKNOWN")),
        )

        if key not in libraries:
            libraries[key] = ScenarioLibrary(key=key)

        chunk = RunChunk(
            source_file=path.name,
            n_events_total=n_events_total,
            seed_id=extract_seed_from_filename(path.stem, seed_regex),
        )

        if len(esc) == 0:
            libraries[key].add_chunk(chunk)
            continue

        pos_m = esc[["posX_mm", "posY_mm", "posZ_mm"]].to_numpy(dtype=float) * 1e-3
        dir_u = esc[["dirX", "dirY", "dirZ"]].to_numpy(dtype=float)
        E_true = esc["escapeE_MeV"].to_numpy(dtype=float)
        t_escape = esc["escapeT_ns"].to_numpy(dtype=float)
        event_id = esc["eventID"].to_numpy(dtype=int)

        hit_mask, s_m = ray_hits_detector_plane_x(pos_m, dir_u, det)
        hit_mask &= E_true >= Eth_MeV

        chunk.n_escape_rows = int(len(esc))

        if not np.any(hit_mask):
            libraries[key].add_chunk(chunk)
            continue

        idx = np.where(hit_mask)[0]
        chunk.n_geom_hits = int(len(idx))

        E_h = E_true[idx]
        t_h = t_escape[idx]
        evt_h = event_id[idx]
        s_h = s_m[idx]

        v = np.clip(neutron_speed_m_per_ns(E_h), 1e-9, None)
        t_arrival_rel_ns = t_h + (s_h / v)

        order = np.argsort(evt_h, kind="mergesort")
        evt_h = evt_h[order]
        E_h = E_h[order]
        t_arrival_rel_ns = t_arrival_rel_ns[order]

        unique_evt, starts, counts = np.unique(evt_h, return_index=True, return_counts=True)
        chunk.n_events_with_geom_hit = int(len(unique_evt))

        for st, ct in zip(starts, counts):
            sl = slice(st, st + ct)
            chunk.event_templates_E.append(E_h[sl].copy())
            chunk.event_templates_t.append(t_arrival_rel_ns[sl].copy())

        libraries[key].add_chunk(chunk)

    if not libraries:
        raise FileNotFoundError(
            "No usable ROOT files remained after filtering. "
            "Check --root-dir, --root-glob, and --beam-energies."
        )
    return libraries


def sample_hits_from_library(
    rng: np.random.Generator,
    lib: ScenarioLibrary,
    n_incident: int,
    window_s: float,
    resp: DetectorResponse,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Sample only primaries that produce >=1 geometrically hittable neutron by thinning
    incident primaries using the empirical p(event has geom hit), then bootstrap from
    the nonzero event templates.
    """
    if n_incident <= 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), 0
    if lib.n_events_total <= 0 or lib.n_events_with_geom_hit <= 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), 0

    p = lib.p_event_geom_hit
    if p <= 0.0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), 0

    n_nonzero_events = int(rng.poisson(n_incident * p))
    if n_nonzero_events <= 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), 0

    templates_E, templates_t = lib.all_templates()
    n_templates = len(templates_E)
    if n_templates == 0:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), 0

    chosen = rng.integers(0, n_templates, size=n_nonzero_events)
    t0_all = rng.uniform(0.0, window_s * 1e9, size=n_nonzero_events)

    E_chunks: List[np.ndarray] = []
    t_chunks: List[np.ndarray] = []

    uniq_idx, counts = np.unique(chosen, return_counts=True)
    offset = 0
    for idx, count in zip(uniq_idx, counts):
        E_template = templates_E[int(idx)]
        t_template = templates_t[int(idx)]
        this_t0 = t0_all[offset : offset + count]
        offset += count

        n_hits_evt = len(E_template)
        if n_hits_evt == 0:
            continue

        E_rep = np.tile(E_template, count)
        t_rep = np.concatenate([t0 + t_template for t0 in this_t0])

        E_meas, t_meas = apply_response(rng, E_rep, t_rep, resp)
        if len(E_meas):
            E_chunks.append(E_meas)
            t_chunks.append(t_meas)

    if not E_chunks:
        return np.empty(0, dtype=float), np.empty(0, dtype=float), int(n_nonzero_events)

    return np.concatenate(E_chunks), np.concatenate(t_chunks), int(n_nonzero_events)


def group_libraries_by_scenario(
    libraries: Dict[ScenarioKey, ScenarioLibrary]
) -> Dict[tuple, Dict[float, ScenarioLibrary]]:
    grouped: Dict[tuple, Dict[float, ScenarioLibrary]] = {}
    for key, lib in libraries.items():
        group_key = (
            key.snmMaterial,
            key.sphereOuterR_mm,
            key.sphereInnerR_mm,
            key.beamDirX,
            key.beamDirY,
            key.beamDirZ,
            key.physicsListName,
        )
        grouped.setdefault(group_key, {})[key.beamE_MeV] = lib
    return grouped


def select_self_bg_group(
    grouped: Dict[tuple, Dict[float, ScenarioLibrary]],
    *,
    self_bg_material: str,
    self_bg_rout_mm: float,
    self_bg_rin_mm: float,
    tol: float = 1e-6,
) -> tuple | None:
    matches = []
    for group_key in grouped:
        mat, rout, rin, _ux, _uy, _uz, _phys = group_key
        if str(mat) == str(self_bg_material) and abs(float(rout) - self_bg_rout_mm) <= tol and abs(float(rin) - self_bg_rin_mm) <= tol:
            matches.append(group_key)
    if not matches:
        return None
    if len(matches) > 1:
        warnings.warn(
            f"Multiple self-background groups matched ({len(matches)}). "
            f"Using the first: {matches[0]}"
        )
    return matches[0]


# ---------------------------------------------------------------------
# Feature row construction
# ---------------------------------------------------------------------

def _concat_nonempty(arrs: Sequence[np.ndarray]) -> np.ndarray:
    arrs_use = [a for a in arrs if len(a)]
    if not arrs_use:
        return np.empty(0, dtype=float)
    return np.concatenate(arrs_use)


def _fraction_gt(values: np.ndarray, thr: float) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.mean(np.asarray(values, dtype=float) > thr))


def _safe_ratio(num: float, den: float) -> float:
    if abs(den) < 1e-30:
        return 0.0
    return float(num / den)


def make_feature_row(
    *,
    class_label: str,
    material_exact: str,
    scenario_id: str,
    source_case: str,
    flux_regime: FluxRegime,
    flux_scale_factor: float,
    total_flux_cm2_s: float,
    flux_above_threshold_cm2_s: float,
    panel: DetectorPlaneX,
    response: DetectorResponse,
    window_s: float,
    sample_index: int,
    geant_seed_ids: str,
    key_example: ScenarioKey,
    signal_hits_E: np.ndarray,
    signal_hits_t: np.ndarray,
    self_bg_hits_E: np.ndarray,
    self_bg_hits_t: np.ndarray,
    floor_bg_hits_E: np.ndarray,
    floor_bg_hits_t: np.ndarray,
    E_bins: np.ndarray,
    include_cluster_features: bool,
    include_truth_qc: bool,
    n_incident_total: int,
    n_incident_by_energy: Dict[float, int],
) -> dict:
    E_all = _concat_nonempty([signal_hits_E, self_bg_hits_E, floor_bg_hits_E])
    t_all = _concat_nonempty([signal_hits_t, self_bg_hits_t, floor_bg_hits_t])

    count_total = int(len(E_all))
    E_hist, _ = np.histogram(E_all, bins=E_bins)
    covered = int(E_hist.sum())
    overflow = int(count_total - covered)

    count_gt1 = int(np.sum(E_all > 1.0)) if count_total else 0
    count_gt5 = int(np.sum(E_all > 5.0)) if count_total else 0
    count_gt10 = int(np.sum(E_all > 10.0)) if count_total else 0
    count_gt20 = int(np.sum(E_all > 20.0)) if count_total else 0

    row: dict = {
        # labels
        "class_label": class_label,
        "material_exact": material_exact,

        # grouping / bookkeeping
        "scenario_id": scenario_id,
        "source_case": parse_conf_label(source_case),
        "flux_regime": flux_regime.name,
        "split_group_id": (
            f"{scenario_id}|source={parse_conf_label(source_case)}|regime={flux_regime.name}"
        ),
        "sample_index": int(sample_index),
        "geant_seed_ids": geant_seed_ids,

        # physical metadata
        "snmMaterial": key_example.snmMaterial,
        "sphereOuterR_mm": key_example.sphereOuterR_mm,
        "sphereInnerR_mm": key_example.sphereInnerR_mm,
        "beamDirX": key_example.beamDirX,
        "beamDirY": key_example.beamDirY,
        "beamDirZ": key_example.beamDirZ,
        "physicsListName": key_example.physicsListName,

        # inference-time / configuration context
        "window_s": float(window_s),
        "panel_x_m": panel.x_m,
        "panel_y_center_m": panel.y_center_m,
        "panel_z_center_m": panel.z_center_m,
        "panel_y_size_m": panel.y_size_m,
        "panel_z_size_m": panel.z_size_m,
        "panel_area_m2": panel.area_m2,
        "efficiency": response.eff,
        "threshold_MeV": response.Eth_MeV,
        "sigmaEfrac": response.sigmaEfrac,
        "sigmaT_ns": response.sigmaT_ns,
        "coinc_ns": response.coinc_ns,
        "background_rate_hz": response.bg_rate_hz,
        "flux_regime_mode": flux_regime.mode,
        "flux_regime_threshold_MeV": flux_regime.threshold_MeV,
        "flux_regime_duty_fraction": flux_regime.duty_fraction,
        "flux_regime_scale_factor": flux_scale_factor,
        "source_total_flux_cm2_s": total_flux_cm2_s,
        "source_flux_above_regime_threshold_cm2_s": flux_above_threshold_cm2_s,

        # model-friendly count / spectral features
        "count_total": count_total,
        "count_gt1": count_gt1,
        "count_gt5": count_gt5,
        "count_gt10": count_gt10,
        "count_gt20": count_gt20,
        "frac_gt1": _safe_ratio(count_gt1, count_total),
        "frac_gt5": _safe_ratio(count_gt5, count_total),
        "frac_gt10": _safe_ratio(count_gt10, count_total),
        "frac_gt20": _safe_ratio(count_gt20, count_total),
        "ratio_gt5_to_gt1": _safe_ratio(count_gt5, count_gt1),
        "ratio_gt10_to_gt1": _safe_ratio(count_gt10, count_gt1),
        "ratio_gt20_to_gt5": _safe_ratio(count_gt20, count_gt5),
        "count_meanE_MeV": float(np.mean(E_all)) if count_total else 0.0,
        "count_medianE_MeV": float(np.median(E_all)) if count_total else 0.0,
        "count_energy_hist_covered": covered,
        "count_energy_hist_overflow": overflow,
        "frac_energy_hist_covered": _safe_ratio(covered, count_total) if count_total else 1.0,
    }

    for i, c in enumerate(E_hist):
        row[f"Ebin_{i:03d}"] = int(c)
    row["Ebin_overflow"] = overflow

    if include_cluster_features:
        clusters = coincidence_cluster_sizes(t_all, coinc_ns=response.coinc_ns)
        row["n_clusters"] = int(len(clusters))
        row["max_cluster"] = int(clusters.max()) if len(clusters) else 0
        row["mean_cluster"] = float(clusters.mean()) if len(clusters) else 0.0
        row["n_clusters_ge2"] = int(np.sum(clusters >= 2))
        row["n_clusters_ge3"] = int(np.sum(clusters >= 3))
        row["n_clusters_ge4"] = int(np.sum(clusters >= 4))
        row["n_clusters_ge10"] = int(np.sum(clusters >= 10))

    if include_truth_qc:
        row["qc_count_signal"] = int(len(signal_hits_E))
        row["qc_count_self_bg"] = int(len(self_bg_hits_E))
        row["qc_count_floor_bg"] = int(len(floor_bg_hits_E))
        row["qc_count_signal_fraction"] = _safe_ratio(len(signal_hits_E), count_total)
        row["qc_incident_primaries_total"] = int(n_incident_total)
        for E in sorted(n_incident_by_energy):
            row[f"qc_incident_E{int(round(E)):03d}"] = int(n_incident_by_energy[E])

    return row



# ---------------------------------------------------------------------
# Output view helpers
# ---------------------------------------------------------------------

def _ebin_sort_key(name: str) -> tuple[int, int | str]:
    m = re.fullmatch(r"Ebin_(\d+)", name)
    if m:
        return (0, int(m.group(1)))
    if name == "Ebin_overflow":
        return (1, 0)
    return (2, name)


def select_output_view(df: pd.DataFrame, dataset_view: str) -> pd.DataFrame:
    """
    Reduce the internal full dataset to a user-facing output schema.

    full:
        Keep all columns produced internally (subject to --include-truth-qc).
    ml:
        Keep only labels / minimal provenance and detector-observable features
        that would plausibly be available for downstream ML.
    """
    dataset_view = str(dataset_view).strip().lower()
    if dataset_view == "full":
        return df.copy()
    if dataset_view != "ml":
        raise ValueError(f"Unsupported dataset_view={dataset_view!r}; expected 'full' or 'ml'")

    keep: list[str] = []

    def add(col: str) -> None:
        if col in df.columns and col not in keep:
            keep.append(col)

    # Labels / minimal provenance
    for col in [
        "class_label",
        "snmMaterial",
        "source_case",
        "flux_regime",
        "sample_index",
        "window_s",
        "coinc_ns",
        "background_rate_hz",
        "ml_split",
    ]:
        add(col)

    # Count / hardness features
    for col in [
        "count_total",
        "count_gt1",
        "count_gt5",
        "count_gt10",
        "count_gt20",
        "frac_gt1",
        "frac_gt5",
        "frac_gt10",
        "frac_gt20",
        "ratio_gt5_to_gt1",
        "ratio_gt10_to_gt1",
        "ratio_gt20_to_gt5",
        "count_meanE_MeV",
        "count_medianE_MeV",
    ]:
        add(col)

    # Coincidence / clustering summaries
    for col in [
        "n_clusters",
        "max_cluster",
        "mean_cluster",
        "n_clusters_ge2",
        "n_clusters_ge3",
        "n_clusters_ge4",
        "n_clusters_ge10",
    ]:
        add(col)

    # Histogram features
    ebin_cols = sorted(
        [c for c in df.columns if re.fullmatch(r"Ebin_\d+", c)],
        key=_ebin_sort_key,
    )
    for col in ebin_cols:
        add(col)
    add("Ebin_overflow")

    if not keep:
        raise ValueError("No columns were selected for the requested output view")

    return df.loc[:, keep].copy()


def write_dataset_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_source_case_csvs(
    *,
    df_full: pd.DataFrame,
    out_path: Path,
    dataset_view: str,
    write_split_csvs: bool,
) -> list[Path]:
    if "source_case" not in df_full.columns:
        raise ValueError("Cannot write source-case CSVs because 'source_case' is missing")

    written: list[Path] = []
    for source_case in sorted(df_full["source_case"].astype(str).unique(), key=str):
        mask = df_full["source_case"].astype(str) == str(source_case)
        df_case_full = df_full.loc[mask].copy()
        df_case_out = select_output_view(df_case_full, dataset_view)

        case_path = out_path.with_name(out_path.stem + f"_sourcecase{source_case}.csv")
        write_dataset_csv(df_case_out, case_path)
        written.append(case_path)

        if write_split_csvs and "ml_split" in df_case_full.columns:
            for split_name in ["train", "val", "test"]:
                df_split_full = df_case_full[df_case_full["ml_split"] == split_name].copy()
                if df_split_full.empty:
                    continue
                df_split_out = select_output_view(df_split_full, dataset_view)
                split_path = out_path.with_name(
                    out_path.stem + f"_sourcecase{source_case}_{split_name}.csv"
                )
                write_dataset_csv(df_split_out, split_path)
                written.append(split_path)

    return written


def build_manifest_dict(
    *,
    args: argparse.Namespace,
    panel: DetectorPlaneX,
    response: DetectorResponse,
    E_bins: np.ndarray,
    regimes: Sequence[FluxRegime],
    weights: Dict[str, Dict[float, dict]],
    summary_path: Path,
    dataset_rows: int,
    output_columns: Sequence[str],
) -> dict:
    return {
        "script": "build_ml_windows_dataset.py",
        "dataset_view": str(args.dataset_view),
        "window_s": float(args.window_s),
        "samples_per_group": int(args.samples_per_group),
        "fluence_duration_s": float(args.fluence_duration_s),
        "projected_area_cm2": projected_area_cm2(
            target_radius_cm=args.target_radius_cm,
            explicit_area_cm2=args.projected_area_cm2,
        ),
        "detector_plane": {
            "x_m": float(panel.x_m),
            "y_center_m": float(panel.y_center_m),
            "z_center_m": float(panel.z_center_m),
            "y_size_m": float(panel.y_size_m),
            "z_size_m": float(panel.z_size_m),
            "area_m2": float(panel.area_m2),
        },
        "detector_response": {
            "eff": float(response.eff),
            "Eth_MeV": float(response.Eth_MeV),
            "sigmaEfrac": float(response.sigmaEfrac),
            "sigmaT_ns": float(response.sigmaT_ns),
            "bg_rate_hz": float(response.bg_rate_hz),
            "bg_E_mean_MeV": float(response.bg_E_mean_MeV),
            "coinc_ns": float(response.coinc_ns),
        },
        "energy_histogram": {
            "Emax_MeV": float(args.Emax_MeV),
            "Ebins": int(args.Ebins),
            "bin_edges_MeV": [float(x) for x in E_bins.tolist()],
        },
        "flux_regimes": [
            {
                "name": str(r.name),
                "mode": str(r.mode),
                "threshold_MeV": float(r.threshold_MeV),
                "target_flux_cm2_s": None if r.target_flux_cm2_s is None else float(r.target_flux_cm2_s),
                "duty_fraction": float(r.duty_fraction),
                "notes": str(r.notes),
            }
            for r in regimes
        ],
        "source_cases": sorted(str(k) for k in weights.keys()),
        "summary_csv": str(summary_path),
        "dataset_rows": int(dataset_rows),
        "output_columns": list(output_columns),
        "split_assignment": {
            "enabled": bool(args.assign_splits),
            "group_cols": list(args.split_group_cols),
            "stratify_col": None if not args.split_stratify_col else str(args.split_stratify_col),
            "ratios": [float(x) for x in args.split_ratios],
            "salt": str(args.split_salt),
        },
    }


# ---------------------------------------------------------------------
# Split assignment
# ---------------------------------------------------------------------

def _normalize_ratios(ratios: Sequence[float]) -> Tuple[float, float, float]:
    if len(ratios) != 3:
        raise ValueError("--split-ratios must provide exactly three values: train val test")
    vals = np.asarray(ratios, dtype=float)
    if np.any(vals < 0):
        raise ValueError("--split-ratios must be non-negative")
    s = float(vals.sum())
    if s <= 0:
        raise ValueError("--split-ratios must sum to something positive")
    vals = vals / s
    return float(vals[0]), float(vals[1]), float(vals[2])


def _allocate_counts(n: int, ratios: Sequence[float]) -> Tuple[int, int, int]:
    train_r, val_r, test_r = _normalize_ratios(ratios)
    raw = np.array([train_r, val_r, test_r], dtype=float) * int(n)
    base = np.floor(raw).astype(int)
    remainder = int(n - base.sum())
    frac = raw - base
    order = np.argsort(-frac)
    for idx in order[:remainder]:
        base[idx] += 1
    return int(base[0]), int(base[1]), int(base[2])


def _stable_hash_key(text: str, salt: str) -> str:
    return hashlib.md5((salt + "||" + text).encode("utf-8")).hexdigest()


def assign_grouped_splits(
    df: pd.DataFrame,
    *,
    group_cols: Sequence[str],
    stratify_col: str | None,
    split_ratios: Sequence[float],
    split_salt: str,
) -> pd.DataFrame:
    if df.empty:
        df = df.copy()
        df["ml_split"] = []
        return df

    missing = [c for c in group_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Split group columns not found in DataFrame: {missing}")
    if stratify_col is not None and stratify_col not in df.columns:
        raise ValueError(f"Split stratify column not found in DataFrame: {stratify_col}")

    unique_groups = df[list(group_cols) + ([stratify_col] if stratify_col else [])].drop_duplicates().copy()
    unique_groups["__group_key__"] = unique_groups[list(group_cols)].astype(str).agg("||".join, axis=1)
    unique_groups["__hash__"] = unique_groups["__group_key__"].map(lambda x: _stable_hash_key(x, split_salt))

    if stratify_col is None:
        unique_groups["__stratum__"] = "ALL"
    else:
        unique_groups["__stratum__"] = unique_groups[stratify_col].astype(str)

    assignments: List[pd.DataFrame] = []

    for stratum, g in unique_groups.groupby("__stratum__", sort=True):
        g = g.sort_values("__hash__").reset_index(drop=True)
        n = len(g)
        n_train, n_val, n_test = _allocate_counts(n, split_ratios)

        splits = (
            ["train"] * n_train
            + ["val"] * n_val
            + ["test"] * n_test
        )
        if len(splits) != n:
            raise RuntimeError("Internal split allocation error")

        g = g.copy()
        g["ml_split"] = splits
        assignments.append(g[["__group_key__", "ml_split"]])

        if min(n_train, n_val, n_test) == 0 and n >= 3:
            warnings.warn(
                f"Stratum '{stratum}' has {n} split groups but one split received zero groups. "
                "Consider generating more groups or changing split ratios."
            )

    assign_df = pd.concat(assignments, ignore_index=True)
    out = df.copy()
    out["__group_key__"] = out[list(group_cols)].astype(str).agg("||".join, axis=1)
    out = out.merge(assign_df, on="__group_key__", how="left", validate="many_to_one")
    out = out.drop(columns="__group_key__")
    return out


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--root-dir",
        default="/geant4-apps/geant4-11-SPACE/outputs",
        help="Directory containing ROOT runs",
    )
    ap.add_argument(
        "--root-glob",
        default="*.root",
        help="Glob used inside --root-dir to find ROOT files",
    )
    ap.add_argument(
        "--weights-csv",
        required=True,
        help="AP9-derived weighting CSV",
    )
    ap.add_argument(
        "--fluence-duration-s",
        type=float,
        default=7 * 24 * 3600,
        help="Duration represented by band_fluence_cm2 in the weight file [s]",
    )
    ap.add_argument(
        "--total-flux-cm2-s",
        type=float,
        default=None,
        help="Required only if weights CSV has normalized weights but no band_fluence_cm2",
    )
    ap.add_argument(
        "--source-cases",
        nargs="+",
        default=None,
        help="Optional subset of source cases / confidence levels to use (e.g. 50 75 95)",
    )
    ap.add_argument(
        "--beam-energies",
        nargs="+",
        type=float,
        default=None,
        help="Optional subset of beam energies [MeV] to load from the ROOT directory",
    )

    # Time window / dataset size
    ap.add_argument("--window-s", type=float, default=10.0, help="Measurement window length [s]")
    ap.add_argument(
        "--samples-per-group",
        type=int,
        default=250,
        help="Rows to generate per (scenario, source_case, flux_regime)",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="RNG seed used for synthetic window generation",
    )

    # Incident source normalization
    ap.add_argument(
        "--target-radius-cm",
        type=float,
        default=7.0,
        help="Projected circular radius [cm] used if --projected-area-cm2 is not supplied",
    )
    ap.add_argument(
        "--projected-area-cm2",
        type=float,
        default=None,
        help="Explicit projected source area [cm^2]; overrides --target-radius-cm",
    )

    # Detector geometry / response
    ap.add_argument("--panel-x-m", type=float, default=2.0)
    ap.add_argument("--panel-y-center-m", type=float, default=0.0)
    ap.add_argument("--panel-z-center-m", type=float, default=1.0)
    ap.add_argument("--panel-y-size-m", type=float, default=1.0)
    ap.add_argument("--panel-z-size-m", type=float, default=1.0)

    ap.add_argument("--eff", type=float, default=1.0, help="Detection efficiency")
    ap.add_argument("--Eth-MeV", type=float, default=0.1, help="Energy threshold [MeV]")
    ap.add_argument("--sigmaEfrac", type=float, default=0.0, help="Relative energy resolution sigma/E")
    ap.add_argument("--sigmaT-ns", type=float, default=0.0, help="Time jitter sigma [ns]")
    ap.add_argument("--coinc-ns", type=float, default=500.0, help="Coincidence clustering window [ns]")
    ap.add_argument("--bg-rate-hz", type=float, default=0.0, help="Flat Poisson background rate [Hz]")
    ap.add_argument("--bg-E-mean-MeV", type=float, default=2.0, help="Background exponential mean energy [MeV]")

    # Optional self-background from a benign library scenario
    ap.add_argument("--disable-self-bg", action="store_true", help="Disable library-based self-background")
    ap.add_argument("--self-bg-material", default="G4_Al", help="snmMaterial used for self-background library")
    ap.add_argument("--self-bg-rout-mm", type=float, default=70.0, help="sphereOuterR_mm for self-background library")
    ap.add_argument("--self-bg-rin-mm", type=float, default=65.0, help="sphereInnerR_mm for self-background library")
    ap.add_argument("--self-bg-scale", type=float, default=0.0, help="Scale factor for self-background incident rate")

    # Flux regimes
    ap.add_argument(
        "--no-ap9-average",
        action="store_true",
        help="Do not generate the default 'ap9_average' regime from the 7-day mean flux",
    )
    ap.add_argument(
        "--flux-regime",
        action="append",
        default=[],
        help="Additional flux regime spec: name:threshold_MeV:target_flux_cm2_s[:duty_fraction]",
    )

    # Histogram / features
    ap.add_argument("--Emax-MeV", type=float, default=100.0, help="Energy-histogram max [MeV]")
    ap.add_argument("--Ebins", type=int, default=20, help="Number of energy bins")
    ap.add_argument(
        "--disable-cluster-features",
        action="store_true",
        help="Do not include cluster / coincidence summary features",
    )

    # QC / split / output controls
    ap.add_argument(
        "--include-truth-qc",
        action="store_true",
        help="Include truth-only simulation bookkeeping columns (do not train on them)",
    )
    ap.add_argument(
        "--seed-regex",
        default="",
        help="Optional regex used to extract Geant4 seed from filename. "
             "Must contain named group 'seed' or one capture group.",
    )
    ap.add_argument(
        "--allow-missing-energies",
        action="store_true",
        help="Renormalize source weights over whatever energies are available instead of erroring out",
    )
    ap.add_argument(
        "--assign-splits",
        action="store_true",
        help="Assign grouped train / val / test splits",
    )
    ap.add_argument(
        "--split-group-cols",
        nargs="+",
        default=["scenario_id", "source_case", "flux_regime"],
        help="Columns that define split groups when --assign-splits is used",
    )
    ap.add_argument(
        "--split-stratify-col",
        default="class_label",
        help="Column used to stratify grouped split assignment. Use '' to disable.",
    )
    ap.add_argument(
        "--split-ratios",
        nargs=3,
        type=float,
        default=[0.70, 0.15, 0.15],
        metavar=("TRAIN", "VAL", "TEST"),
        help="Grouped split ratios",
    )
    ap.add_argument(
        "--split-salt",
        default="ml_windows_dataset_v1",
        help="Salt string for deterministic split assignment",
    )
    ap.add_argument(
        "--write-split-csvs",
        action="store_true",
        help="When --assign-splits is used, also write separate *_train.csv, *_val.csv, *_test.csv files",
    )
    ap.add_argument(
        "--dataset-view",
        choices=["full", "ml"],
        default="full",
        help="Output schema: 'full' keeps all per-row metadata, 'ml' keeps only labels + detector-observable features",
    )
    ap.add_argument(
        "--debug-out",
        default="",
        help="Optional full-detail debug CSV path. Useful with --dataset-view ml.",
    )
    ap.add_argument(
        "--write-source-case-csvs",
        action="store_true",
        help="Also write separate CSVs for each source_case / confidence level",
    )
    ap.add_argument(
        "--manifest-out",
        default="",
        help="Optional JSON sidecar describing detector settings, histogram bins, regimes, and output columns",
    )
    ap.add_argument("--summary-out", default="", help="Optional library summary CSV path")
    ap.add_argument("--out", default="ml_windows_dataset.csv", help="Output CSV path")
    return ap.parse_args()


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    rng = np.random.default_rng(args.seed)
    root_dir = Path(args.root_dir)
    weights_csv = Path(args.weights_csv)
    out_path = Path(args.out)

    if not root_dir.exists():
        raise SystemExit(f"Directory does not exist: {root_dir}")
    if not weights_csv.exists():
        raise SystemExit(f"Weights CSV does not exist: {weights_csv}")

    panel = DetectorPlaneX(
        x_m=args.panel_x_m,
        y_center_m=args.panel_y_center_m,
        z_center_m=args.panel_z_center_m,
        y_size_m=args.panel_y_size_m,
        z_size_m=args.panel_z_size_m,
    )
    response = DetectorResponse(
        eff=args.eff,
        Eth_MeV=args.Eth_MeV,
        sigmaEfrac=args.sigmaEfrac,
        sigmaT_ns=args.sigmaT_ns,
        bg_rate_hz=args.bg_rate_hz,
        bg_E_mean_MeV=args.bg_E_mean_MeV,
        coinc_ns=args.coinc_ns,
    )

    if args.window_s <= 0:
        raise SystemExit("--window-s must be positive")
    if args.samples_per_group <= 0:
        raise SystemExit("--samples-per-group must be positive")
    if args.Ebins <= 0:
        raise SystemExit("--Ebins must be positive")
    if args.Emax_MeV <= 0:
        raise SystemExit("--Emax-MeV must be positive")
    if not (0.0 <= response.eff <= 1.0):
        raise SystemExit("--eff must be between 0 and 1")
    if args.self_bg_scale < 0.0:
        raise SystemExit("--self-bg-scale must be non-negative")

    proj_area_cm2 = projected_area_cm2(
        target_radius_cm=args.target_radius_cm,
        explicit_area_cm2=args.projected_area_cm2,
    )
    E_bins = np.linspace(0.0, args.Emax_MeV, args.Ebins + 1)

    seed_regex = re.compile(args.seed_regex) if args.seed_regex else None
    regimes = build_flux_regimes(
        regime_specs=args.flux_regime,
        include_ap9_average=(not args.no_ap9_average),
    )

    weights = load_weight_table(
        weights_csv=weights_csv,
        fluence_duration_s=args.fluence_duration_s,
        total_flux_cm2_s=args.total_flux_cm2_s,
    )
    if args.source_cases is not None:
        want = {parse_conf_label(x) for x in args.source_cases}
        weights = {k: v for k, v in weights.items() if parse_conf_label(k) in want}
        if not weights:
            raise SystemExit(
                f"No source cases from --source-cases matched the weighting CSV. "
                f"Requested: {sorted(want)}"
            )

    print(f"[INFO] Reading ROOT library from: {root_dir}")
    libraries = build_library(
        root_dir=root_dir,
        det=panel,
        Eth_MeV=response.Eth_MeV,
        root_glob=args.root_glob,
        beam_energies_filter=args.beam_energies,
        seed_regex=seed_regex,
    )
    grouped = group_libraries_by_scenario(libraries)

    self_bg_group = None
    if not args.disable_self_bg and args.self_bg_scale > 0.0:
        self_bg_group = select_self_bg_group(
            grouped,
            self_bg_material=args.self_bg_material,
            self_bg_rout_mm=args.self_bg_rout_mm,
            self_bg_rin_mm=args.self_bg_rin_mm,
        )
        if self_bg_group is None:
            warnings.warn(
                "No self-background library matched the requested selector. "
                "Self-background will be disabled."
            )
        else:
            print(f"[INFO] Self-background library selected: {self_bg_group}")

    summary_rows: List[dict] = []
    for key, lib in libraries.items():
        summary_rows.append(
            {
                "scenario_id": key.scenario_id(),
                "class_label": material_to_class(key.snmMaterial),
                "material_exact": material_variant(key.snmMaterial, key.sphereOuterR_mm, key.sphereInnerR_mm),
                "snmMaterial": key.snmMaterial,
                "sphereOuterR_mm": key.sphereOuterR_mm,
                "sphereInnerR_mm": key.sphereInnerR_mm,
                "beamE_MeV": key.beamE_MeV,
                "beamDirX": key.beamDirX,
                "beamDirY": key.beamDirY,
                "beamDirZ": key.beamDirZ,
                "physicsListName": key.physicsListName,
                "source_files": ",".join(sorted(c.source_file for c in lib.run_chunks)),
                "seed_ids": ",".join(lib.seed_ids),
                "n_files": lib.n_files,
                "n_events_total": lib.n_events_total,
                "n_escape_rows": lib.n_escape_rows,
                "n_geom_hits": lib.n_geom_hits,
                "n_events_with_geom_hit": lib.n_events_with_geom_hit,
                "p_event_geom_hit": lib.p_event_geom_hit,
                "mean_geom_hits_per_primary": lib.mean_geom_hits_per_primary,
                "panel_x_m": panel.x_m,
                "panel_area_m2": panel.area_m2,
                "threshold_MeV": response.Eth_MeV,
            }
        )

    rows: List[dict] = []

    for group_key, energy_map in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        mat, rout, rin, ux, uy, uz, phys = group_key
        mclass = material_to_class(mat)
        mexact = material_variant(mat, rout, rin)
        scenario_id = (
            f"mat={mat}|Rout={rout:g}|Rin={rin:g}|u=({ux:g},{uy:g},{uz:g})|phys={phys}"
        )
        available_energies = sorted(energy_map.keys())
        geant_seed_ids = ",".join(sorted({sid for lib in energy_map.values() for sid in lib.seed_ids}))

        print(
            f"[INFO] Scenario={mexact}, dir=({ux:g},{uy:g},{uz:g}), "
            f"energies={available_energies}"
        )

        self_bg_energy_map = grouped[self_bg_group] if self_bg_group is not None else None

        for source_case, source_weights in sorted(weights.items(), key=lambda kv: str(kv[0])):
            available_weighted_energies = [E for E in sorted(source_weights) if E in energy_map]
            missing_energies = [E for E in sorted(source_weights) if E not in energy_map]
            extra_library_energies = [E for E in available_energies if E not in source_weights]

            if extra_library_energies:
                warnings.warn(
                    f"Scenario {mexact}, source case {source_case}: library energies "
                    f"{extra_library_energies} have no AP9 weight and will be unused."
                )

            if missing_energies and not args.allow_missing_energies:
                raise SystemExit(
                    f"Missing required energies for scenario {mexact}, source case {source_case}: {missing_energies}. "
                    "Either add those runs or re-run with --allow-missing-energies."
                )
            if not available_weighted_energies:
                warnings.warn(
                    f"Scenario {mexact} has no energies overlapping source case {source_case}; skipping."
                )
                continue

            for regime in regimes:
                full_scaled_flux_map, flux_scale_factor, base_total_flux, scaled_total_flux, scaled_flux_above = (
                    scale_source_weights_for_regime(source_weights, regime)
                )

                flux_map_available = {
                    E: float(full_scaled_flux_map[E]) for E in available_weighted_energies
                }
                flux_sum_available = float(sum(flux_map_available.values()))
                full_flux_sum = float(sum(full_scaled_flux_map.values()))

                if flux_sum_available <= 0:
                    warnings.warn(
                        f"Scenario {mexact}, source case {source_case}, regime {regime.name}: "
                        "available flux is non-positive; skipping."
                    )
                    continue

                if missing_energies:
                    warnings.warn(
                        f"Scenario {mexact}, source case {source_case}, regime {regime.name}: "
                        f"missing energies {missing_energies}. Available energies will be renormalized."
                    )
                    for E in available_weighted_energies:
                        flux_map_available[E] = (flux_map_available[E] / flux_sum_available) * full_flux_sum

                used_total_flux = float(sum(flux_map_available.values()))
                used_flux_above = float(sum(v for E, v in flux_map_available.items() if E >= regime.threshold_MeV))

                for sample_index in range(args.samples_per_group):
                    signal_E_chunks: List[np.ndarray] = []
                    signal_t_chunks: List[np.ndarray] = []
                    self_bg_E_chunks: List[np.ndarray] = []
                    self_bg_t_chunks: List[np.ndarray] = []

                    n_incident_total = 0
                    n_incident_by_energy: Dict[float, int] = {}

                    for E in available_weighted_energies:
                        lib = energy_map[E]
                        band_flux_cm2_s = flux_map_available[E]

                        lam_incident = band_flux_cm2_s * proj_area_cm2 * args.window_s
                        n_incident = int(rng.poisson(lam_incident))
                        n_incident_total += n_incident
                        n_incident_by_energy[E] = n_incident

                        if n_incident > 0:
                            E_sig, t_sig, _ = sample_hits_from_library(
                                rng=rng,
                                lib=lib,
                                n_incident=n_incident,
                                window_s=args.window_s,
                                resp=response,
                            )
                            if len(E_sig):
                                signal_E_chunks.append(E_sig)
                                signal_t_chunks.append(t_sig)

                        if (
                            self_bg_energy_map is not None
                            and args.self_bg_scale > 0.0
                            and E in self_bg_energy_map
                        ):
                            n_self_incident = int(rng.poisson(lam_incident * args.self_bg_scale))
                            if n_self_incident > 0:
                                E_bg_self, t_bg_self, _ = sample_hits_from_library(
                                    rng=rng,
                                    lib=self_bg_energy_map[E],
                                    n_incident=n_self_incident,
                                    window_s=args.window_s,
                                    resp=response,
                                )
                                if len(E_bg_self):
                                    self_bg_E_chunks.append(E_bg_self)
                                    self_bg_t_chunks.append(t_bg_self)

                    signal_E = _concat_nonempty(signal_E_chunks)
                    signal_t = _concat_nonempty(signal_t_chunks)
                    self_bg_E = _concat_nonempty(self_bg_E_chunks)
                    self_bg_t = _concat_nonempty(self_bg_t_chunks)
                    floor_bg_E, floor_bg_t = add_background_hits(
                        rng=rng,
                        resp=response,
                        window_s=args.window_s,
                        Emax_MeV=args.Emax_MeV,
                    )

                    example_key = energy_map[available_weighted_energies[0]].key

                    rows.append(
                        make_feature_row(
                            class_label=mclass,
                            material_exact=mexact,
                            scenario_id=scenario_id,
                            source_case=str(source_case),
                            flux_regime=regime,
                            flux_scale_factor=flux_scale_factor,
                            total_flux_cm2_s=used_total_flux,
                            flux_above_threshold_cm2_s=used_flux_above,
                            panel=panel,
                            response=response,
                            window_s=float(args.window_s),
                            sample_index=sample_index,
                            geant_seed_ids=geant_seed_ids,
                            key_example=example_key,
                            signal_hits_E=signal_E,
                            signal_hits_t=signal_t,
                            self_bg_hits_E=self_bg_E,
                            self_bg_hits_t=self_bg_t,
                            floor_bg_hits_E=floor_bg_E,
                            floor_bg_hits_t=floor_bg_t,
                            E_bins=E_bins,
                            include_cluster_features=(not args.disable_cluster_features),
                            include_truth_qc=bool(args.include_truth_qc),
                            n_incident_total=n_incident_total,
                            n_incident_by_energy=n_incident_by_energy,
                        )
                    )

    df_out = pd.DataFrame(rows)
    if df_out.empty:
        raise SystemExit("No dataset rows were generated. Check your ROOT coverage and AP9 weights.")

    if args.assign_splits:
        stratify_col = args.split_stratify_col if args.split_stratify_col else None
        df_out = assign_grouped_splits(
            df_out,
            group_cols=args.split_group_cols,
            stratify_col=stratify_col,
            split_ratios=args.split_ratios,
            split_salt=args.split_salt,
        )

    summary_path = Path(args.summary_out) if args.summary_out else out_path.with_name(out_path.stem + "_library_summary.csv")
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

    df_full_out = df_out.copy()
    df_write = select_output_view(df_full_out, args.dataset_view)
    write_dataset_csv(df_write, out_path)

    print(f"\n[OK] Wrote dataset: {len(df_write):,} rows -> {out_path}")
    print(f"[OK] Wrote library summary -> {summary_path}")

    if args.debug_out:
        debug_path = Path(args.debug_out)
        write_dataset_csv(df_full_out, debug_path)
        print(f"[OK] Wrote full-detail debug CSV -> {debug_path}")

    if args.assign_splits and args.write_split_csvs:
        if "ml_split" not in df_full_out.columns:
            raise RuntimeError("Internal error: splits were requested but ml_split column is missing")
        for split_name in ["train", "val", "test"]:
            df_split_full = df_full_out[df_full_out["ml_split"] == split_name].copy()
            if df_split_full.empty:
                continue
            df_split = select_output_view(df_split_full, args.dataset_view)
            split_path = out_path.with_name(out_path.stem + f"_{split_name}.csv")
            write_dataset_csv(df_split, split_path)
            print(f"[OK] Wrote {split_name} split: {len(df_split):,} rows -> {split_path}")

    if args.write_source_case_csvs:
        written_source_case_paths = write_source_case_csvs(
            df_full=df_full_out,
            out_path=out_path,
            dataset_view=args.dataset_view,
            write_split_csvs=(args.assign_splits and args.write_split_csvs),
        )
        for path in written_source_case_paths:
            print(f"[OK] Wrote source-case dataset -> {path}")

    if args.manifest_out:
        manifest_path = Path(args.manifest_out)
        manifest = build_manifest_dict(
            args=args,
            panel=panel,
            response=response,
            E_bins=E_bins,
            regimes=regimes,
            weights=weights,
            summary_path=summary_path,
            dataset_rows=len(df_write),
            output_columns=df_write.columns.tolist(),
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"[OK] Wrote manifest JSON -> {manifest_path}")


if __name__ == "__main__":
    main()
