#!/usr/bin/env python3
"""Reproduce the 'Neutron Energy Spectrum Shape' plot from EscapeNeutrons ntuples.

python plot_neutron_energy_spectrum.py build/outputs/proton_100MeV_Vacuum_seed1.root:Vacuum \
    build/outputs/proton_100MeV_Aluminum_seed1.root:Aluminum \
    build/outputs/proton_100MeV_Tungsten_seed1.root:Tungsten \
    build/outputs/proton_100MeV_WGPu_seed1.root:WGPu \
    --ref <old_Vacuum.root>:Vacuum --ref <old_WGPu.root>:WGPu ...   # optional overlay of old runs
    --out neutron_energy_spectrum.png

Needs numpy, matplotlib and uproot (pip install uproot); no ROOT install required.
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np
import uproot

COLORS = {
    "Vacuum": "#9e9e9e",
    "Aluminum": "#4169e1",
    "Tungsten": "#4caf50",
    "WGPu": "#d9413b",
}
REF_COLORS = {  # darker shade of each material for the old/reference runs
    "Vacuum": "#555555",
    "Aluminum": "#1a3a8f",
    "Tungsten": "#1e6b22",
    "WGPu": "#8b1a14",
}

E_MAX_MEV = 20.0
N_BINS = 20  # 1 MeV wide bins


def build_curve(spec: str, bin_edges: np.ndarray, bin_centers: np.ndarray):
    path, label = spec.rsplit(":", 1)
    with uproot.open(path) as f:
        energies = f["EscapeNeutrons"]["escapeE_MeV"].array(library="np")
        n_events = f["Events"].num_entries
    counts, _ = np.histogram(energies, bins=bin_edges)
    counts = counts.astype(float)

    norm = counts[0] if counts[0] > 0 else 1.0
    rel_counts = counts / norm

    keep = rel_counts > 0
    return label, n_events, bin_centers[keep], rel_counts[keep]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="path.root:Label pairs (new runs)")
    ap.add_argument("--ref", action="append", default=[], help="path.root:Label pairs (old runs to overlay)")
    ap.add_argument("--out", default="neutron_energy_spectrum.png")
    args = ap.parse_args()

    bin_edges = np.linspace(0.0, E_MAX_MEV, N_BINS + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    curves = [build_curve(spec, bin_edges, bin_centers) for spec in args.files]
    refs = [build_curve(spec, bin_edges, bin_centers) for spec in args.ref]
    full_events = max(n for _, n, _, _ in curves)

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    for label, n_events, xs, ys in curves:
        color = COLORS.get(label, "black")
        name = label if n_events >= full_events else f"{label} ({n_events} evt, partial)"
        # Dashed line carries the legend entry; dots are drawn separately so the legend shows only the line.
        ax.plot(xs, ys, "--", color=color, lw=2, alpha=0.7, label=name)
        ax.plot(xs, ys, "o", color=color, ms=8)

    ax.set_yscale("log")
    ax.set_xlim(-0.5, E_MAX_MEV + 0.5)
    ax.set_xlabel("Neutron Energy (MeV)", fontsize=16)
    ax.set_ylabel("Relative Counts (E≈0 normalized)", fontsize=16)
    ax.set_title("Neutron Energy Spectrum Shape", fontsize=18)
    ax.tick_params(labelsize=13)
    ax.grid(True, color="#e5e5e5")
    ax.set_axisbelow(True)
    for label, _, xs, ys in refs:
        color = REF_COLORS.get(label, "dimgray")
        ax.plot(xs, ys, "-", color=color, lw=1.5, alpha=0.8, label=f"{label} (old)")
        ax.plot(xs, ys, "s", color=color, ms=6, mfc="none", mew=1.5)

    ax.legend(title="Sphere Material", fontsize=12 if args.ref else 14, title_fontsize=12, handlelength=2.5,
              ncol=2 if args.ref else 1)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
