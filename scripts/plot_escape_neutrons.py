#python plot_escape_neutrons.py proton_output_U235_nt_EscapeNeutrons_t0.csv --prefix U235_100MeV_t0


import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plot_style  # noqa: F401  (shared font sizes)

COLS = [
    "eventID", "trackID", "birthRegion",
    "birthE_MeV", "birthT_ns", "creatorCode",
    "escapeE_MeV", "escapeT_ns",
    "dirX", "dirY", "dirZ"
]

def load_escape_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        comment="#",          # ignore the wcsv metadata lines
        header=None,
        names=COLS
    )

    # Basic cleaning
    df = df.dropna()
    for c in ["birthE_MeV", "birthT_ns", "escapeE_MeV", "escapeT_ns"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["birthE_MeV", "birthT_ns", "escapeE_MeV", "escapeT_ns"])

    # Derived: time from "birth" to escape
    df["dt_ns"] = df["escapeT_ns"] - df["birthT_ns"]
    return df

def save_hist_escape_time(df: pd.DataFrame, out_prefix: str):
    t = df["escapeT_ns"].to_numpy()
    t = t[np.isfinite(t) & (t > 0)]

    # 1) Log-binned histogram (shows full dynamic range cleanly)
    tmin = max(np.min(t), 1e-3)     # ns; avoid 0 in log
    tmax = np.max(t)
    bins = np.logspace(np.log10(tmin), np.log10(tmax), 140)

    plt.figure()
    plt.hist(t, bins=bins)
    plt.xscale("log")
    plt.xlabel("escapeT_ns (ns)")
    plt.ylabel("counts")
    plt.title("Histogram: Neutron escape times (log-binned)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_hist_escapeT_logbins.png", dpi=200)
    plt.close()

    # 2) Zoomed linear histogram to capture the bulk (e.g., up to 99.9th percentile)
    p = 99.9
    tcut = np.percentile(t, p)
    t_zoom = t[t <= tcut]

    plt.figure()
    plt.hist(t_zoom, bins=200)
    plt.xlabel("escapeT_ns (ns)")
    plt.ylabel("counts")
    plt.title(f"Histogram: escapeT (linear), up to {p}th percentile (<= {tcut:.1f} ns)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_hist_escapeT_zoom_p{p:.1f}.png", dpi=200)
    plt.close()

    # 3) Tail-only histogram (events beyond the cutoff)
    t_tail = t[t > tcut]
    if len(t_tail) > 0:
        # tail plotted on log x; otherwise it compresses too
        bins_tail = np.logspace(np.log10(max(np.min(t_tail), tcut)), np.log10(np.max(t_tail)), 80)
        plt.figure()
        plt.hist(t_tail, bins=bins_tail)
        plt.xscale("log")
        plt.xlabel("escapeT_ns (ns)")
        plt.ylabel("counts")
        plt.title(f"Tail histogram: escapeT > {p}th percentile (> {tcut:.1f} ns), N={len(t_tail)}")
        plt.tight_layout()
        plt.savefig(f"{out_prefix}_hist_escapeT_tail_p{p:.1f}.png", dpi=200)
        plt.close()


def save_escapeE_vs_escapeT(df: pd.DataFrame, out: str):
    d = df[(df["escapeE_MeV"] > 0) & (df["escapeT_ns"] > 0)].copy()

    plt.figure()
    plt.scatter(d["escapeT_ns"], d["escapeE_MeV"], s=4, alpha=0.15)
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("escapeT_ns (ns)")
    plt.ylabel("escapeE (MeV)")
    plt.title("escapeE vs escapeT (scatter, log-log)")
    plt.tight_layout()
    plt.savefig(out, dpi=200)
    plt.close()

def save_dt_vs_escapeE(df: pd.DataFrame, out: str):
    d = df[(df["escapeE_MeV"] > 0) & (df["dt_ns"] > 0)].copy()

    plt.figure()
    if len(d) > 200_000:
        plt.hexbin(d["escapeE_MeV"], d["dt_ns"], gridsize=200, xscale="log", yscale="log")
        plt.colorbar(label="counts")
    else:
        plt.scatter(d["escapeE_MeV"], d["dt_ns"], s=3, alpha=0.3)
        #plt.xscale("log")
        #plt.yscale("log")

    plt.xlabel("escapeE (MeV)")
    plt.ylabel("dt = escapeT - birthT (ns)")
    plt.title("Travel/processing time after 'birth' vs escape energy (log-log)")
    plt.tight_layout()
    plt.savefig(out, dpi=200)
    plt.close()

import numpy as np

def save_birthT_vs_escapeT(df: pd.DataFrame, out: str, p: float = 99.9):
    d = df[(df["birthT_ns"] >= 0) & (df["escapeT_ns"] >= 0)].copy()

    # Zoom window based on percentiles
    xb = np.percentile(d["birthT_ns"], p)
    yb = np.percentile(d["escapeT_ns"], p)
    z = d[(d["birthT_ns"] <= xb) & (d["escapeT_ns"] <= yb)]

    plt.figure()
    plt.scatter(z["birthT_ns"], z["escapeT_ns"], s=6, alpha=0.2)

    plt.xlabel("birthT_ns (ns)")
    plt.ylabel("escapeT_ns (ns)")
    plt.title(f"birthT vs escapeT (linear, <= {p}th percentile)")
    plt.tight_layout()
    plt.savefig(out, dpi=200)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Path to EscapeNeutrons.csv (wcsv ntuple)")
    ap.add_argument("--prefix", default="escape_neutrons", help="Output file prefix")
    args = ap.parse_args()

    df = load_escape_csv(args.csv)

    print(f"Loaded {len(df):,} rows")
    print(df[["birthE_MeV", "birthT_ns", "escapeE_MeV", "escapeT_ns", "dt_ns", "creatorCode"]].describe())

    save_hist_escape_time(df, args.prefix)
    save_escapeE_vs_escapeT(df, f"{args.prefix}_escapeE_vs_escapeT.png")
    save_dt_vs_escapeE(df, f"{args.prefix}_dt_vs_escapeE.png")
    save_birthT_vs_escapeT(df, f"{args.prefix}_birthT_vs_escapeT.png")

    print("Wrote:")
    print(f"  {args.prefix}_hist_escapeT.png")
    print(f"  {args.prefix}_escapeE_vs_escapeT.png")
    print(f"  {args.prefix}_dt_vs_escapeE.png")
    print(f"  {args.prefix}_birthT_vs_escapeT.png")

if __name__ == "__main__":
    main()
