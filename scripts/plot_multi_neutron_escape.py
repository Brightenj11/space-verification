#!/usr/bin/env python3
"""Reproduce the multi-neutron escape survival-curve plot from Events ntuples.

python plot_multi_neutron_escape.py build/outputs/proton_100MeV_Vacuum_seed1.root:Vacuum \
    build/outputs/proton_100MeV_Aluminum_seed1.root:Aluminum \
    build/outputs/proton_100MeV_Tungsten_seed1.root:Tungsten \
    build/outputs/proton_100MeV_WGPu_seed1.root:WGPu \
    --ref <old_Vacuum.root>:Vacuum --ref <old_WGPu.root>:WGPu ...   # optional overlay of old runs
    --out multi_neutron_escape.png

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


def survival_curve(n_escaped: np.ndarray, n_max: int) -> tuple[np.ndarray, np.ndarray]:
    total = len(n_escaped)
    ns = np.arange(0, n_max + 1)
    probs = np.array([(n_escaped >= n).sum() / total for n in ns])
    return ns, probs


def build_curve(spec: str):
    path, label = spec.rsplit(":", 1)
    with uproot.open(path) as f:
        n_escaped = f["Events"]["nEscapedTotal"].array(library="np")
    ns, probs = survival_curve(n_escaped, int(n_escaped.max()))
    keep = probs > 0
    return label, len(n_escaped), ns[keep], probs[keep]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="path.root:Label pairs (new runs)")
    ap.add_argument("--ref", action="append", default=[], help="path.root:Label pairs (old runs to overlay)")
    ap.add_argument("--out", default="multi_neutron_escape.png")
    args = ap.parse_args()

    curves = [build_curve(spec) for spec in args.files]
    refs = [build_curve(spec) for spec in args.ref]
    full_events = max(n for _, n, _, _ in curves)
    n_max = max(ns.max() for _, _, ns, _ in curves + refs)

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    for label, n_events, ns, probs in curves:
        color = COLORS.get(label, "black")
        name = label if n_events >= full_events else f"{label} ({n_events} evt, partial)"
        # Dashed line carries the legend entry; dots are drawn separately so the legend shows only the line.
        ax.plot(ns, probs, "--", color=color, lw=2, alpha=0.7, label=name)
        ax.plot(ns, probs, "o", color=color, ms=8)

    ax.set_yscale("log")
    ax.set_ylim(1e-5, 2.0)
    ax.set_xlim(-0.5, n_max + 0.5)
    ax.set_xlabel("Escaping Neutrons (per Proton)", fontsize=16)
    ax.set_ylabel("Probability of ≥ N Escaping Neutrons", fontsize=16)
    ax.set_title("Probability of Multi-Neutron Escapes", fontsize=18)
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
