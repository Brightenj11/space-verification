"""Pie-slice heatmap of the AP9 proton sampling probability over (pitch angle, energy) cells.

Uses the same distribution the Geant4 gun samples from (/pmgun/pitchTable):
weight = j(E, alpha) * sin(alpha) * dE, with j interpolated log-log in E and linear in alpha,
mirrored about 90 deg. Each cell's color is its share of all sampled protons (linear scale).
Pitch angle runs around the slice (90 deg straight up, 60/120 deg at the edges); energy runs
radially, lowest energy nearest the center.

Usage: python scripts/plot_energies_and_angles_heatmap.py macros/ap9_pitch_1000km.csv -o pitch_energy_heatmap.png
"""
import argparse

import matplotlib.pyplot as plt
import plot_style  # noqa: F401  (shared font sizes)
import numpy as np
from matplotlib.colors import BoundaryNorm
from matplotlib.ticker import MaxNLocator

ANGLE_EDGES = np.arange(60, 121, 5)                                       # deg
ENERGY_EDGES = np.array([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000])  # MeV


def read_table(path):
    with open(path) as f:
        energies = np.array(f.readline().strip().split(",")[1:], dtype=float)
    data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    return data[:, 0], energies, data[:, 1:]  # angles, energies, flux[angle][energy]


def flux_at_energy(energies, flux, e):
    """Per-angle flux at energy e: log-log between table energies, linear where one end is 0."""
    k = np.clip(np.searchsorted(energies, e, side="right"), 1, len(energies) - 1)
    e0, e1 = energies[k - 1], energies[k]
    j0, j1 = flux[:, k - 1], flux[:, k]
    with np.errstate(divide="ignore", invalid="ignore"):
        loglog = j0 * (j1 / j0) ** (np.log(e / e0) / np.log(e1 / e0))
    return np.where((j0 > 0) & (j1 > 0), loglog, j0 + (j1 - j0) * (e - e0) / (e1 - e0))


def cell_probabilities(angles, energies, flux, n_fine=40):
    """Integrate j * sin(alpha) over each (angle, energy) cell with a midpoint rule, then normalize."""
    prob = np.zeros((len(ANGLE_EDGES) - 1, len(ENERGY_EDGES) - 1))
    for ie, (elo, ehi) in enumerate(zip(ENERGY_EDGES[:-1], ENERGY_EDGES[1:])):
        e_fine = np.geomspace(elo, ehi, n_fine + 1)
        e_mid, de = np.sqrt(e_fine[:-1] * e_fine[1:]), np.diff(e_fine)
        j_e = np.array([flux_at_energy(energies, flux, e) for e in e_mid])  # [e][table angle]
        for ia, (alo, ahi) in enumerate(zip(ANGLE_EDGES[:-1], ANGLE_EDGES[1:])):
            a_fine = np.linspace(alo, ahi, n_fine + 1)
            a_mid = 0.5 * (a_fine[:-1] + a_fine[1:])
            folded = np.minimum(a_mid, 180 - a_mid)
            j = np.array([np.where(folded < angles[0], 0, np.interp(folded, angles, row)) for row in j_e])
            prob[ia, ie] = np.sum(j * np.sin(np.radians(a_mid)) * de[:, None]) * (ahi - alo) / n_fine
    return prob / prob.sum()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", nargs="?", default="macros/ap9_pitch_1000km.csv")
    p.add_argument("-o", "--out", default="pitch_energy_heatmap.png")
    a = p.parse_args()

    prob = cell_probabilities(*read_table(a.csv))
    assert np.isclose(prob.sum(), 1.0)

    n_e = len(ENERGY_EDGES) - 1
    theta = np.radians(ANGLE_EDGES)
    r = np.arange(n_e + 1)  # energy edge i sits at radius i: low energy at the center

    fs = plot_style.FS
    fig, ax = plt.subplots(figsize=(8, 7), subplot_kw={"projection": "polar"})
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")  # zero-probability cells (e.g. above the spectrum cut-off)
    pct = 100 * prob
    # Discrete linear bins: a stepped colorbar makes neighbouring cells easy to tell apart.
    levels = MaxNLocator(nbins=10).tick_values(0, pct.max())
    mesh = ax.pcolormesh(theta, r, np.ma.masked_equal(pct, 0).T, cmap=cmap, shading="flat",
                         norm=BoundaryNorm(levels, cmap.N))

    ax.set_thetamin(ANGLE_EDGES[0])
    ax.set_thetamax(ANGLE_EDGES[-1])
    ax.set_xticks(np.radians(ANGLE_EDGES[::2]))
    ax.set_xticklabels([f"{d}°" for d in ANGLE_EDGES[::2]], fontsize=fs)
    ax.set_rorigin(-2)  # small hole so the innermost (lowest-energy) ring isn't squeezed to a point
    ax.set_ylim(0, n_e)
    ax.set_yticks(r)
    ax.set_yticklabels([f"{e:g}" for e in ENERGY_EDGES], fontsize=fs)
    # Energy tick labels sit along the 60 deg edge; put the axis label just outside them.
    ax.text(np.radians(ANGLE_EDGES[0] - 14), n_e / 2, "Proton Energy (MeV)", rotation=ANGLE_EDGES[0],
            ha="center", va="center", fontsize=fs + 4)
    # The title slot sits just above the arc's tick labels, so it doubles as the pitch-angle axis label.
    ax.set_title("Pitch Angle (degrees)", fontsize=fs + 4)
    ax.grid(color="white", alpha=0.3)

    cbar = fig.colorbar(mesh, ax=ax, orientation="horizontal", location="bottom", shrink=0.6, pad=-0.05,
                        ticks=levels)
    cbar.set_label("Percentage of sampled protons", fontsize=fs)
    cbar.ax.tick_params(labelsize=fs)
    fig.savefig(a.out, dpi=200, bbox_inches="tight")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
