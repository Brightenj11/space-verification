#!/usr/bin/env python3
"""Polar plot of where escaping neutrons go, plus a panel-acceptance sanity check.

python scripts/plot_escape_directions.py \
    build/outputs/proton_100MeV_Vacuum_seed1.root:Vacuum \
    build/outputs/proton_100MeV_WGPu_seed1.root:WGPu ... \
    [--birth snm] --out plots/escape_directions_100MeV.png

Direction angle in the x-z plane: 0 deg = +x downstream panel (directly behind the payload),
90 deg = +z transverse panel (90 deg to the beam), 180 deg = -x where the protons come in, traveling +x.
Radius = % of that material's escaping neutrons per 5 deg bin (each curve sums to 100%).
Shaded wedges = panels as seen from the origin.

Also prints, per file: escapes/proton, the naive A/(4 pi r^2) estimate, a straight-line ray trace
of every escaping neutron onto the panel boxes, and the actual nHitDownstream/nHitTransverse tallies.
Outside the hull is vacuum and the hull is convex, so ray trace and tally should agree.
"""

import argparse

import matplotlib.pyplot as plt
import plot_style  # noqa: F401  (shared font sizes)
import numpy as np
import uproot

COLORS = {"Vacuum": "#9e9e9e", "Al_geo": "#4169e1", "Al_mass": "#7fa7f5", "Aluminum": "#4169e1",
          "W": "#4caf50", "Tungsten": "#4caf50", "WGPu": "#d9413b"}

# ponytail: default geometry hard-coded (both panel near faces 1.75 m from origin, 0.5x1x1 m boxes).
# Read RunConfig if /det/ changes. Runs made before the transverse panel moved had it at z = 2.0 m.
# downstream = +x, behind the payload on the beam line (sim copy 0).
# transverse = +z, 90 deg to the beam (sim copy 1).
PANELS = {  # name: (lo, hi) corners in mm
    "downstream": (np.array([1750., -500., -500.]), np.array([2250., 500., 500.])),
    "transverse": (np.array([-500., -500., 1750.]), np.array([500., 500., 2250.])),
}
NEAR_R = {"downstream": 1750., "transverse": 1750.}  # origin to near face, mm
WEDGE = {"downstream": 0.0, "transverse": np.pi / 2}  # panel direction in plot angle
BINS = np.linspace(-np.pi, np.pi, 73)  # 5 deg


def ray_hits_box(pos, d, lo, hi):
    """Slab test: does the ray pos + t*d (t>0) cross the box?"""
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (lo - pos) / d, (hi - pos) / d
    tmin = np.nanmax(np.minimum(t1, t2), axis=1)
    tmax = np.nanmin(np.maximum(t1, t2), axis=1)
    return (tmax >= np.maximum(tmin, 0)) & np.isfinite(tmin)


def analyze(path, birth):
    cols = ["dirX", "dirY", "dirZ", "posX_mm", "posY_mm", "posZ_mm", "birthRegion"]
    h_xz = np.zeros(len(BINS) - 1)
    n_esc, trace = 0, {k: 0 for k in PANELS}
    with uproot.open(path) as f:
        # ponytail: falls back to pre-rename columns (nHitSide/nHitEnd); drop once old runs are redone.
        cols_ev = ["nHitDownstream", "nHitTransverse"] if "nHitDownstream" in f["Events"] else ["nHitSide", "nHitEnd"]
        ev = dict(zip(["nHitDownstream", "nHitTransverse"], f["Events"].arrays(cols_ev, library="np").values()))
        for c in f["EscapeNeutrons"].iterate(cols, library="np", step_size="200 MB"):
            keep = np.isin(c["birthRegion"], [4, 5]) if birth == "snm" else slice(None)
            d = np.column_stack([c["dirX"], c["dirY"], c["dirZ"]])[keep]
            p = np.column_stack([c["posX_mm"], c["posY_mm"], c["posZ_mm"]])[keep]
            n_esc += len(d)
            h_xz += np.histogram(np.arctan2(d[:, 2], d[:, 0]), BINS)[0]
            for k, (lo, hi) in PANELS.items():
                trace[k] += ray_hits_box(p, d, lo, hi).sum()
    n_evt = len(ev["nHitDownstream"])
    actual = {"downstream": ev["nHitDownstream"].sum(), "transverse": ev["nHitTransverse"].sum()}
    return n_evt, n_esc, h_xz, trace, actual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="path.root:Label pairs")
    ap.add_argument("--birth", choices=["all", "snm"], default="all",
                    help="snm = only neutrons born in the payload (regions 4/5)")
    ap.add_argument("--out", default="escape_directions.png")
    args = ap.parse_args()

    fig, ax = plt.subplots(figsize=(8.5, 6.5), subplot_kw={"projection": "polar"})
    centers = 0.5 * (BINS[1:] + BINS[:-1])
    print(f"{'label':>9} {'esc/p':>8} | {'panel':>10} {'naive':>9} {'raytrace':>9} {'actual':>9}  (per proton)")
    for spec in args.files:
        path, label = spec.rsplit(":", 1)
        n_evt, n_esc, h_xz, trace, actual = analyze(path, args.birth)
        r = np.append(h_xz, h_xz[0]) / n_esc * 100  # % of escaping neutrons per 5 deg bin
        ax.plot(np.append(centers, centers[0] + 2 * np.pi), r, color=COLORS.get(label, "black"), lw=2, label=label)
        for k in PANELS:
            naive = n_esc / n_evt * 1e6 / (4 * np.pi * NEAR_R[k] ** 2)  # 1 m^2 face, point source at origin
            print(f"{label:>9} {n_esc / n_evt:8.4f} | {k:>10} {naive:9.2e} {trace[k] / n_evt:9.2e} "
                  f"{(actual[k] if args.birth == 'all' else np.nan) / n_evt:9.2e}")

    # Panel wedges as seen from the origin.
    top = ax.get_ylim()[1]
    for k in PANELS:
        ax.bar(WEDGE[k], top, width=2 * np.arctan(500 / NEAR_R[k]), color="orange", alpha=0.2, zorder=0)
        ax.text(WEDGE[k] - 0.22, top * 0.88, f"{k}\npanel", ha="center", va="center",
                color="darkorange")
    # Proton arrow outside the circle, just left of the 180 deg label.
    ax.annotate("", xy=(-0.1, 0.5), xytext=(-0.26, 0.5), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="black", lw=1.8), annotation_clip=False)
    ax.text(-0.18, 0.52, "protons", transform=ax.transAxes, ha="center", va="bottom")
    ax.set_rlabel_position(250)  # keep radial tick labels clear of the panel labels
    ax.set_ylim(0, top)
    ax.grid(True, color="#e5e5e5")  # matplotlib default polar: 0 deg = +x right, counterclockwise, +z up
    title = "Percent Neutrons Escaped per 5°" + (" (payload-born)" if args.birth == "snm" else "")
    ax.set_title(title, pad=20)
    ax.legend(title="Sphere Material", loc="upper left", bbox_to_anchor=(1.05, 1.0))
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
