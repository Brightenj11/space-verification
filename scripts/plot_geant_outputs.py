#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm



# -----------------------------
# Labels
# -----------------------------
CLASS_LABELS: Dict[int, str] = {
    0: "No primary hadronic inelastic vertex",
    1: "Primary inelastic vertex, no SNM fission-like latch",
    2: "SNM fission-like latch occurred (>=1)",
}

REGION_LABELS: Dict[int, str] = {
    0: "World (outside spacecraft)",
    1: "Bus shell (hull material)",
    2: "Bus envelope (internal vacuum)",
    4: "Sphere volume (SNM shell)",
    5: "SNM core (inner void)",
    99: "Unknown / unmapped",
}


# ============================================================
# MANUAL PLOT CONTROLS (edit these whenever you want)
# ============================================================
# Energy histograms (MeV)
E_MAX_MEV = 10.0
E_BIN_WIDTH_MEV = 0.2

# Time histogram (ns)
T_MAX_NS = 100.0
T_BIN_WIDTH_NS = 5.0

# Include unknown region (99) on birth region plot?
INCLUDE_UNKNOWN_REGION = True

# Comparison plot style
COMPARISON_NORMALIZE = False
# If True, energy/time histograms will be plotted as normalized probability densities
# so shapes can be compared independent of total count.


# -----------------------------
# Geant4 wcsv reader
# -----------------------------
def read_geant4_wcsv(path: Path) -> pd.DataFrame:
    colnames: List[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#column"):
                colnames.append(line.strip().split()[-1])
            elif (not line.startswith("#")) and line.strip():
                break
    if not colnames:
        raise ValueError(f"No '#column' definitions found in {path}")
    df = pd.read_csv(path, comment="#", header=None, names=colnames, sep=",", engine="python")
    return df


def infer_case_name(events_file: Path) -> str:
    # proton_output_U235_nt_Events_t0.csv -> proton_output_U235
    return re.sub(r"_nt_Events.*\.csv$", "", events_file.name)


def find_matching_escape_file(events_file: Path) -> Path:
    candidate = Path(str(events_file).replace("nt_Events", "nt_EscapeNeutrons"))
    if candidate.exists():
        return candidate
    case = infer_case_name(events_file)
    matches = sorted(events_file.parent.glob(f"{case}_nt_EscapeNeutrons*.csv"))
    if not matches:
        raise FileNotFoundError(f"Could not find EscapeNeutrons CSV for Events file: {events_file}")
    return matches[0]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def linear_bins(xmax: float, bin_width: float) -> np.ndarray:
    if xmax <= 0 or bin_width <= 0:
        raise ValueError("xmax and bin_width must be > 0")
    n_bins = int(np.ceil(xmax / bin_width))
    return np.linspace(0.0, n_bins * bin_width, n_bins + 1)


# -----------------------------
# Per-case plotters (unchanged)
# -----------------------------
def plot_class_distribution(ev: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    counts = ev["class"].value_counts().to_dict()
    keys = sorted(counts.keys())
    labels = [CLASS_LABELS.get(int(k), f"Unknown class {k}") for k in keys]
    values = [counts[k] for k in keys]

    plt.figure()
    plt.bar(range(len(values)), values)
    plt.xticks(range(len(values)), labels, rotation=20, ha="right")
    plt.ylabel("Number of events")
    plt.title(f"{title_prefix} — Event class distribution")
    plt.tight_layout()
    plt.savefig(outdir / "class_distribution.png", dpi=200)
    plt.close()


def plot_birth_energy_spectrum(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    col = "birthE_MeV"
    bins = linear_bins(E_MAX_MEV, E_BIN_WIDTH_MEV)

    plt.figure()
    plt.hist(es[col].astype(float), bins=bins, color='skyblue', edgecolor='black', linewidth=0.5)
    plt.grid(True, alpha=0.3)
    plt.xlim(0, E_MAX_MEV)
    plt.xlabel("Neutron kinetic energy at birth (MeV)")
    plt.ylabel("Count (escaped neutrons)")
    plt.title(f"{title_prefix} — Birth energy spectrum (escaped neutrons)")
    plt.tight_layout()
    plt.savefig(outdir / "birth_energy_spectrum.png", dpi=200)
    plt.close()


def plot_escape_energy_spectrum(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    col = "escapeE_MeV"
    bins = linear_bins(E_MAX_MEV, E_BIN_WIDTH_MEV)

    plt.figure()
    plt.hist(es[col].astype(float), bins=bins, color='skyblue', edgecolor='black', linewidth=0.5)
    plt.grid(True, alpha=0.3)
    plt.xlim(0, E_MAX_MEV)
    plt.xlabel("Neutron kinetic energy at escape (MeV)")
    plt.ylabel("Count (escaped neutrons)")
    plt.title(f"{title_prefix} — Escape energy spectrum")
    plt.tight_layout()
    plt.savefig(outdir / "escape_energy_spectrum.png", dpi=200)
    plt.close()


def plot_escape_time_spectrum(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    col = "escapeT_ns"
    bins = linear_bins(T_MAX_NS, T_BIN_WIDTH_NS)

    plt.figure()
    plt.hist(es[col].astype(float), bins=bins, color='skyblue', edgecolor='black', linewidth=0.5)
    plt.grid(True, alpha=0.3)
    plt.xlim(0, T_MAX_NS)
    plt.xlabel("Neutron escape time (ns)")
    plt.ylabel("Count (escaped neutrons)")
    plt.title(f"{title_prefix} — Escape time spectrum")
    plt.tight_layout()
    plt.savefig(outdir / "escape_time_spectrum.png", dpi=200)
    plt.close()

def plot_birth_time_spectrum(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    col = "birthT_ns"
    if col not in es.columns:
        print(f"[skip] {title_prefix}: missing column {col}")
        return

    bins = linear_bins(T_MAX_NS, T_BIN_WIDTH_NS)
    data = pd.to_numeric(es[col], errors="coerce").to_numpy()
    data = data[np.isfinite(data)]

    plt.figure()
    plt.hist(data, bins=bins, color="skyblue", edgecolor="black", linewidth=0.5)
    plt.grid(True, alpha=0.3)
    plt.xlim(0, T_MAX_NS)
    plt.yscale("log")
    plt.xlabel("Neutron birth time (ns)")
    plt.ylabel("Count (escaped neutrons)")
    plt.title(f"{title_prefix} — Birth time spectrum (escaped neutrons)")
    plt.tight_layout()
    plt.savefig(outdir / "birth_time_spectrum.png", dpi=200)
    plt.close()

def plot_transport_time_spectrum(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    col = "dt_escape_minus_birth_ns"
    if col not in es.columns:
        print(f"[skip] {title_prefix}: missing column {col} (did you add the Δt column in main?)")
        return

    bins = linear_bins(T_MAX_NS, T_BIN_WIDTH_NS)
    data = pd.to_numeric(es[col], errors="coerce").to_numpy()
    data = data[np.isfinite(data)]
    data = data[data >= 0.0]  # guard against occasional numerical/pathological negatives

    plt.figure()
    plt.hist(data, bins=bins, color="skyblue", edgecolor="black", linewidth=0.5)
    plt.grid(True, alpha=0.3)
    plt.xlim(0, T_MAX_NS)
    plt.xlabel("Δt = escapeT − birthT (ns)")
    plt.ylabel("Count (escaped neutrons)")
    plt.title(f"{title_prefix} — Transport/leakage time spectrum (escaped neutrons)")
    plt.tight_layout()
    plt.savefig(outdir / "transport_time_spectrum_dt_escape_minus_birth.png", dpi=200)
    plt.close()


def plot_birth_region(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    vc = es["birthRegion"].value_counts().to_dict()
    region_keys = [0, 1, 2, 4, 5] + ([99] if INCLUDE_UNKNOWN_REGION else [])
    labels = [REGION_LABELS.get(k, f"Region {k}") for k in region_keys]
    values = [int(vc.get(k, 0)) for k in region_keys]

    plt.figure()
    plt.bar(range(len(values)), values)
    plt.xticks(range(len(values)), labels, rotation=20, ha="right")
    plt.ylabel("Count (escaped neutrons)")
    plt.title(f"{title_prefix} — Birth region of escaped neutrons")
    plt.tight_layout()
    plt.savefig(outdir / "birth_region.png", dpi=200)
    plt.close()
    
def plot_escape_time_vs_escape_energy(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    if "escapeT_ns" not in es.columns or "escapeE_MeV" not in es.columns:
        print(f"[skip] {title_prefix}: missing escapeT_ns and/or escapeE_MeV")
        return

    t = pd.to_numeric(es["escapeT_ns"], errors="coerce").to_numpy()
    e = pd.to_numeric(es["escapeE_MeV"], errors="coerce").to_numpy()

    mask = np.isfinite(t) & np.isfinite(e) & (t >= 0.0) & (e >= 0.0)
    t = t[mask]
    e = e[mask]

    t_bins = linear_bins(T_MAX_NS, T_BIN_WIDTH_NS)
    e_bins = linear_bins(E_MAX_MEV, E_BIN_WIDTH_MEV)

    plt.figure()
    h = plt.hist2d(t, e, bins=[t_bins, e_bins], norm=LogNorm())
    plt.xlabel("Neutron escape time (ns)")
    plt.ylabel("Neutron kinetic energy at escape (MeV)")
    plt.title(f"{title_prefix} — escapeT vs escapeE (escaped neutrons)")
    plt.colorbar(h[3], label="Counts")
    plt.tight_layout()
    plt.savefig(outdir / "escapeT_vs_escapeE_hist2d.png", dpi=200)
    plt.close()
    
def plot_escape_time_by_event_class(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    if "class" not in es.columns or "escapeT_ns" not in es.columns:
        print(f"[skip] {title_prefix}: missing class and/or escapeT_ns (did you merge events->escape?)")
        return

    bins = linear_bins(T_MAX_NS, T_BIN_WIDTH_NS)

    plt.figure()
    classes = sorted(int(c) for c in pd.to_numeric(es["class"], errors="coerce").dropna().unique())

    for c in classes:
        data = pd.to_numeric(es.loc[es["class"] == c, "escapeT_ns"], errors="coerce").to_numpy()
        data = data[np.isfinite(data)]
        if data.size == 0:
            continue
        # Use density=True so shapes are comparable even if counts differ a lot
        plt.hist(data, bins=bins, histtype="step", linewidth=1.5, density=True,
                 label=CLASS_LABELS.get(c, f"class {c}"))

    plt.grid(True, alpha=0.3)
    plt.xlim(0, T_MAX_NS)
    plt.xlabel("Neutron escape time (ns)")
    plt.ylabel("Probability density")
    plt.title(f"{title_prefix} — Escape time spectrum split by event class")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "escape_time_by_event_class.png", dpi=200)
    plt.close()

def plot_transport_time_by_event_class(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    needed = {"class", "dt_escape_minus_birth_ns"}
    if not needed.issubset(es.columns):
        print(f"[skip] {title_prefix}: missing {needed} (merge + Δt required)")
        return

    bins = linear_bins(T_MAX_NS, T_BIN_WIDTH_NS)

    plt.figure()
    classes = sorted(int(c) for c in pd.to_numeric(es["class"], errors="coerce").dropna().unique())

    for c in classes:
        data = pd.to_numeric(es.loc[es["class"] == c, "dt_escape_minus_birth_ns"], errors="coerce").to_numpy()
        data = data[np.isfinite(data)]
        data = data[data >= 0.0]
        if data.size == 0:
            continue
        plt.hist(data, bins=bins, histtype="step", linewidth=1.5, density=True,
                 label=CLASS_LABELS.get(c, f"class {c}"))

    plt.grid(True, alpha=0.3)
    plt.xlim(0, T_MAX_NS)
    plt.xlabel("Δt = escapeT − birthT (ns)")
    plt.ylabel("Probability density")
    plt.title(f"{title_prefix} — Transport time (Δt) split by event class")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "transport_time_dt_by_event_class.png", dpi=200)
    plt.close()

def plot_creatorcode_correlation_with_fission_events(es: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    needed = {"creatorCode", "nFissionsSNM"}
    if not needed.issubset(es.columns):
        print(f"[skip] {title_prefix}: missing {needed} (merge required for nFissionsSNM)")
        return

    cc = pd.to_numeric(es["creatorCode"], errors="coerce")
    nf = pd.to_numeric(es["nFissionsSNM"], errors="coerce").fillna(0.0)
    has_fission_event = (nf > 0.0)

    tmp = pd.DataFrame({"creatorCode": cc, "hasFissionEvent": has_fission_event})
    tmp = tmp.dropna(subset=["creatorCode"])
    tmp["creatorCode"] = tmp["creatorCode"].astype(int)

    # Mean of boolean == fraction of rows in fission events
    frac = tmp.groupby("creatorCode")["hasFissionEvent"].mean().sort_values(ascending=False)
    top = frac.head(15)

    plt.figure()
    plt.bar([str(i) for i in top.index], top.values)
    plt.xticks(rotation=30, ha="right")
    plt.ylim(0, 1)
    plt.ylabel("Fraction of escaped neutrons from events with nFissionsSNM > 0")
    plt.title(f"{title_prefix} — creatorCode correlation with fission events (top 15)")
    plt.tight_layout()
    plt.savefig(outdir / "creatorCode_corr_fission_event_fraction.png", dpi=200)
    plt.close()



# -----------------------------
# Comparison plotters (new)
# -----------------------------
def compare_class_distribution(cases: List[Tuple[str, pd.DataFrame]], outdir: Path) -> None:
    # Build a stable class set across all cases
    all_classes = sorted(set(int(c) for _, ev in cases for c in ev["class"].unique()))
    x = np.arange(len(all_classes))
    width = 0.8 / max(1, len(cases))  # grouped bars

    plt.figure()
    for i, (name, ev) in enumerate(cases):
        counts = ev["class"].value_counts().to_dict()
        vals = np.array([counts.get(c, 0) for c in all_classes], dtype=float)

        # Normalize to fraction of events for comparison
        vals = vals / len(ev) if len(ev) else vals

        plt.bar(x + (i - (len(cases)-1)/2)*width, vals, width, label=name)

    xticklabels = [CLASS_LABELS.get(c, f"Unknown class {c}") for c in all_classes]
    plt.xticks(x, xticklabels, rotation=20, ha="right")
    plt.ylabel("Fraction of events")
    plt.title("Comparison — Event class distribution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "compare_class_distribution.png", dpi=200)
    plt.close()


def compare_birth_region(cases: List[Tuple[str, pd.DataFrame]], outdir: Path) -> None:
    region_keys = [0, 1, 2, 4, 5] + ([99] if INCLUDE_UNKNOWN_REGION else [])
    x = np.arange(len(region_keys))
    width = 0.8 / max(1, len(cases))

    plt.figure()
    for i, (name, es) in enumerate(cases):
        vc = es["birthRegion"].value_counts().to_dict()
        vals = np.array([vc.get(k, 0) for k in region_keys], dtype=float)

        # Normalize to fractions of escaped neutrons (shape comparison)
        vals = vals / vals.sum() if vals.sum() > 0 else vals

        plt.bar(x + (i - (len(cases)-1)/2)*width, vals, width, label=name)

    labels = [REGION_LABELS.get(k, f"Region {k}") for k in region_keys]
    plt.xticks(x, labels, rotation=20, ha="right")
    plt.ylabel("Fraction of escaped neutrons")
    plt.title("Comparison — Birth region of escaped neutrons")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "compare_birth_region.png", dpi=200)
    plt.close()


def compare_histograms(
    cases: List[Tuple[str, pd.DataFrame]],
    column: str,
    xlabel: str,
    title: str,
    outpath: Path,
    xmax: float,
    bin_width: float,
) -> None:
    bins = linear_bins(xmax, bin_width)

    plt.figure()
    for name, df in cases:
        data = df[column].astype(float).to_numpy()
        data = data[np.isfinite(data)]

        if COMPARISON_NORMALIZE:
            # Plot as density (area ~ 1) for shape comparisons
            plt.hist(data, bins=bins, histtype="step", linewidth=1.5, density=True, label=name)
            plt.ylabel("Probability density")
        else:
            plt.hist(data, bins=bins, histtype="step", linewidth=1.5, density=False, label=name)
            plt.ylabel("Count")

    plt.xlim(0, xmax)
    plt.xlabel(xlabel)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()


def make_comparison_plots(
    case_events: Dict[str, pd.DataFrame],
    case_escape: Dict[str, pd.DataFrame],
    outdir: Path,
) -> None:
    ensure_dir(outdir)

    # Class distribution comparison (Events)
    compare_class_distribution(list(case_events.items()), outdir)

    # Birth region comparison (EscapeNeutrons)
    compare_birth_region(list(case_escape.items()), outdir)

    # Energy/time comparisons (EscapeNeutrons)
    compare_histograms(
        list(case_escape.items()),
        column="birthE_MeV",
        xlabel="Neutron kinetic energy at birth (MeV)",
        title="Comparison — Birth energy spectrum (escaped neutrons)",
        outpath=outdir / "compare_birth_energy.png",
        xmax=E_MAX_MEV,
        bin_width=E_BIN_WIDTH_MEV,
    )

    compare_histograms(
        list(case_escape.items()),
        column="escapeE_MeV",
        xlabel="Neutron kinetic energy at escape (MeV)",
        title="Comparison — Escape energy spectrum",
        outpath=outdir / "compare_escape_energy.png",
        xmax=E_MAX_MEV,
        bin_width=E_BIN_WIDTH_MEV,
    )

    compare_histograms(
        list(case_escape.items()),
        column="escapeT_ns",
        xlabel="Neutron escape time (ns)",
        title="Comparison — Escape time spectrum",
        outpath=outdir / "compare_escape_time.png",
        xmax=T_MAX_NS,
        bin_width=T_BIN_WIDTH_NS,
    )
    
    compare_histograms(
        list(case_escape.items()),
        column="birthT_ns",
        xlabel="Neutron birth time (ns)",
        title="Comparison — Birth time spectrum (escaped neutrons)",
        outpath=outdir / "compare_birth_time.png",
        xmax=T_MAX_NS,
        bin_width=T_BIN_WIDTH_NS,
    )
    
    compare_histograms(
        list(case_escape.items()),
        column="dt_escape_minus_birth_ns",
        xlabel="Δt = escapeT − birthT (ns)",
        title="Comparison — Transport/leakage time spectrum",
        outpath=outdir / "compare_transport_time_dt_escape_minus_birth.png",
        xmax=T_MAX_NS,
        bin_width=T_BIN_WIDTH_NS,
    )




# -----------------------------
# Main
# -----------------------------
def main() -> None:
    here = Path(__file__).resolve().parent
    plot_root = here / "plots"
    ensure_dir(plot_root)

    events_files = sorted(here.glob("*_nt_Events_*.csv"))
    if not events_files:
        raise FileNotFoundError("No '*_nt_Events_*.csv' found in this directory.")

    print(f"Found {len(events_files)} Events file(s).")
    print(f"Manual settings: E_MAX_MEV={E_MAX_MEV}, E_BIN_WIDTH_MEV={E_BIN_WIDTH_MEV}, "
          f"T_MAX_NS={T_MAX_NS}, T_BIN_WIDTH_NS={T_BIN_WIDTH_NS}")
    print(f"Comparison normalize: {COMPARISON_NORMALIZE}")

    # Load all cases
    case_events: Dict[str, pd.DataFrame] = {}
    case_escape: Dict[str, pd.DataFrame] = {}

    for ev_path in events_files:
        case_name = infer_case_name(ev_path)
        es_path = find_matching_escape_file(ev_path)

        ev = read_geant4_wcsv(ev_path)
        es = read_geant4_wcsv(es_path)
        
                # ------------------------------------------------------------
        # Enrich escaped-neutron rows with event-level metadata
        # (lets you split escape-time behavior by event class, vtxRegion, etc.)
        # ------------------------------------------------------------
        # Ensure eventID is numeric for a reliable merge
        ev["eventID"] = pd.to_numeric(ev["eventID"], errors="coerce")
        es["eventID"] = pd.to_numeric(es["eventID"], errors="coerce")

        # Keep only event columns that exist (robust across file variants)
        ev_cols_wanted = ["eventID", "class", "vtxRegion", "t_vertex_ns", "nFissionsSNM", "t_firstFission_ns"]
        ev_keep = ev[[c for c in ev_cols_wanted if c in ev.columns]].copy()

        # Merge event-level columns onto each escaped-neutron row
        # validate="many_to_one" is ideal if eventID is unique in ev; remove if it throws.
        es = es.merge(ev_keep, on="eventID", how="left", validate="many_to_one")

        # ------------------------------------------------------------
        # Derived timing decomposition: transport/leakage time
        # Δt = escapeT - birthT
        # ------------------------------------------------------------
        es["dt_escape_minus_birth_ns"] = (
            pd.to_numeric(es.get("escapeT_ns"), errors="coerce")
            - pd.to_numeric(es.get("birthT_ns"), errors="coerce")
        )

        case_events[case_name] = ev
        case_escape[case_name] = es

        # Per-case plots
        outdir = plot_root / case_name
        ensure_dir(outdir)

        plot_class_distribution(ev, outdir, title_prefix=case_name)
        plot_birth_energy_spectrum(es, outdir, title_prefix=case_name)
        plot_escape_energy_spectrum(es, outdir, title_prefix=case_name)
        plot_birth_time_spectrum(es, outdir, title_prefix=case_name)
        plot_escape_time_spectrum(es, outdir, title_prefix=case_name)
        plot_birth_region(es, outdir, title_prefix=case_name)
        plot_transport_time_spectrum(es, outdir, title_prefix=case_name)
        plot_escape_time_vs_escape_energy(es, outdir, title_prefix=case_name)
        plot_escape_time_by_event_class(es, outdir, title_prefix=case_name)
        plot_transport_time_by_event_class(es, outdir, title_prefix=case_name)
        plot_creatorcode_correlation_with_fission_events(es, outdir, title_prefix=case_name)





        print(f"Wrote per-case plots to: {outdir}")

    # Comparison plots across all loaded cases
    comp_dir = plot_root / "_comparisons"
    make_comparison_plots(case_events, case_escape, comp_dir)
    print(f"Wrote comparison plots to: {comp_dir}")

    print(f"Done. Plots are under: {plot_root}")


if __name__ == "__main__":
    main()
