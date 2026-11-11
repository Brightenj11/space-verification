#!/usr/bin/env python3
"""Plot the escaping (or panel-entering, with --panel) neutron energy spectrum as raw counts.

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
import plot_style  # noqa: F401  (shared font sizes)
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

BIN_MEV = 1.0
E_MAX_MEV = 20.0  # above ~20 MeV it's hull background that doesn't depend on the payload; --emax to change


def load_energies(spec: str, panel: str | None = None):
    path, label = spec.rsplit(":", 1)
    with uproot.open(path) as f:
        if panel:
            hits = f["PanelHits"].arrays(["panel", "E_MeV"], library="np")
            energies = hits["E_MeV"][hits["panel"] == {"downstream": 0, "transverse": 1}[panel]]
        else:
            energies = f["EscapeNeutrons"]["escapeE_MeV"].array(library="np")
        n_events = int(f["Events"].num_entries)
    return label, n_events, energies


def histogram(label, n_events, energies, bin_edges, normalize=True):
    """Counts per bin; with normalize, divided by the first (lowest-energy) bin so curves compare by shape."""
    counts, _ = np.histogram(energies, bins=bin_edges)
    centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    keep = counts > 0
    ys = counts / counts[0] if normalize else counts
    return label, n_events, centers[keep], ys[keep]


def plot_ratio(raw, bin_edges, args) -> None:
    """Each material's per-proton counts / the first file's, bin by bin. Bins where either is 0 are skipped."""
    centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    base_label, base_n, base_e = raw[0]
    base = np.histogram(base_e, bins=bin_edges)[0]

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.axhline(1.0, color=COLORS.get(base_label, "black"), lw=1.5, ls=":", label=f"{base_label} (= 1)")
    for label, n, e in raw[1:]:
        c = np.histogram(e, bins=bin_edges)[0]
        ok = (c > 0) & (base > 0)
        r = (c[ok] / n) / (base[ok] / base_n)
        err = r * np.sqrt(1 / c[ok] + 1 / base[ok])  # Poisson errors of both counts, in quadrature
        color = COLORS.get(label, "black")
        ax.errorbar(centers[ok], r, yerr=err, fmt="o--", color=color, ms=6, lw=1.5, capsize=2, alpha=0.8,
                    label=label)

    ax.set_yscale("log")
    ax.set_xlim(bin_edges[0] - 0.5, bin_edges[-1] + 0.5)
    ax.set_xlabel("Neutron Energy (MeV)")
    ax.set_ylabel(f"Counts / {base_label} counts ({args.bin_mev:g} MeV bins)")
    ax.set_title(f"{args.panel.title()} Panel Spectrum Ratio to {base_label}" if args.panel
                 else f"Escaping Neutron Spectrum Ratio to {base_label}")
    ax.grid(True, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.legend(title="Sphere Material", handlelength=2.5)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"Wrote {args.out}")


def plot_excess(raw, bin_edges, args) -> None:
    """Hits per bin of the --excess material minus each other material's."""
    centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    sig = next((r for r in raw if r[0] == args.excess), None)
    if sig is None:
        raise SystemExit(f"--excess {args.excess}: no file with that label")
    s = np.histogram(sig[2], bins=bin_edges)[0]

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.axhline(0.0, color="black", lw=1)
    for label, _, e in raw:
        if label == args.excess:
            continue
        b = np.histogram(e, bins=bin_edges)[0]
        color = COLORS.get(label, "black")
        ax.plot(centers, s - b, "--", color=color, lw=2, alpha=0.7, label=f"{args.excess} − {label}")
        ax.plot(centers, s - b, "o", color=color, ms=8)

    ax.set_xlim(bin_edges[0] - 0.5, bin_edges[-1] + 0.5)
    ax.set_xlabel("Neutron Energy (MeV)")
    ax.set_ylabel(f"Extra {args.excess} counts per {args.bin_mev:g} MeV bin")
    ax.set_title(f"{args.panel.title()} Panel {args.excess} Excess" if args.panel
                 else f"Escaping Neutron {args.excess} Excess")
    ax.grid(True, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.legend(title=f"{sig[1]:,} protons", handlelength=2.5)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"Wrote {args.out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="path.root:Label pairs (new runs)")
    ap.add_argument("--ref", action="append", default=[], help="path.root:Label pairs (old runs to overlay)")
    ap.add_argument("--out", default="neutron_energy_spectrum.png")
    ap.add_argument("--panel", choices=["downstream", "transverse"],
                    help="use neutrons entering this ScoringPanel (downstream=+x behind payload on the beam "
                         "line, transverse=+z at 90 deg to the beam); "
                         "needs runs with a PanelHits ntuple")
    ap.add_argument("--ratio", action="store_true",
                    help="plot each material's counts divided by the FIRST file's (e.g. Vacuum), with sqrt(N) errors")
    ap.add_argument("--counts", action="store_true",
                    help="plot raw counts instead of the shape (each curve divided by its lowest-energy bin)")
    ap.add_argument("--excess", metavar="LABEL",
                    help="plot LABEL's counts minus every other file's, bin by bin (e.g. --excess WGPu)")
    ap.add_argument("--bin-mev", type=float, default=BIN_MEV, help="energy bin width in MeV")
    ap.add_argument("--emax", type=float, default=E_MAX_MEV,
                    help="upper energy cut in MeV (neutrons above it are not plotted); 0 = highest energy in data")
    args = ap.parse_args()

    raw = [load_energies(spec, args.panel) for spec in args.files]
    raw_refs = [load_energies(spec, args.panel) for spec in args.ref]
    bw = args.bin_mev
    e_max = args.emax or np.ceil(max(e.max() for _, _, e in raw + raw_refs if len(e)) / bw) * bw
    bin_edges = np.arange(0.0, e_max + bw / 2, bw)
    if args.ratio:
        plot_ratio(raw, bin_edges, args)
        return
    if args.excess:
        plot_excess(raw, bin_edges, args)
        return
    curves = [histogram(*r, bin_edges, not args.counts) for r in raw]
    refs = [histogram(*r, bin_edges, not args.counts) for r in raw_refs]
    full_events = max(n for _, n, _, _ in curves)

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    for label, n_events, xs, ys in curves:
        color = COLORS.get(label, "black")
        name = label if n_events >= full_events else f"{label} ({n_events} evt, partial)"
        # Dashed line carries the legend entry; dots are drawn separately so the legend shows only the line.
        ax.plot(xs, ys, "--", color=color, lw=2, alpha=0.7, label=name)
        ax.plot(xs, ys, "o", color=color, ms=8)

    ax.set_yscale("log")
    ax.set_xlim(-0.5, e_max + 0.5)
    ax.set_xlabel("Neutron Energy (MeV)")
    ax.set_ylabel(f"Counts per {bw:g} MeV bin ({full_events:,} protons)" if args.counts
                  else "Relative Counts (E≈0 normalized)")
    ax.set_title(f"{args.panel.title()} Panel Neutron Energy Spectrum" if args.panel
                 else "Escaping Neutron Energy Spectrum")
    ax.grid(True, color="#e5e5e5")
    ax.set_axisbelow(True)
    for label, _, xs, ys in refs:
        color = REF_COLORS.get(label, "dimgray")
        ax.plot(xs, ys, "-", color=color, lw=1.5, alpha=0.8, label=f"{label} (old)")
        ax.plot(xs, ys, "s", color=color, ms=6, mfc="none", mew=1.5)

    ax.legend(title="Sphere Material", handlelength=2.5,
              ncol=2 if args.ref else 1)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
