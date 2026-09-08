#!/usr/bin/env python3
"""Reproduce the 'Neutron Energy Spectrum Shape' plot from EscapeNeutrons ntuples.

python plot_neutron_energy_spectrum.py build/outputs/proton_100MeV_Vacuum_seed1.root:Vacuum \
    build/outputs/proton_100MeV_Aluminum_seed1.root:Aluminum \
    build/outputs/proton_100MeV_Tungsten_seed1.root:Tungsten \
    build/outputs/proton_100MeV_WGPu_seed1.root:WGPu \
    --ref processing/root_runs/proton_output_Vacuum_mev100.root:Vacuum \
    --ref processing/root_runs/proton_output_Al_massmatch_mev100.root:Aluminum \
    --ref processing/root_runs/proton_output_W_mev100.root:Tungsten \
    --ref processing/root_runs/proton_output_WGPu_mev100.root:WGPu \
    --out neutron_energy_spectrum.png
"""

import argparse
import numpy as np
import ROOT

COLORS = {
    "Vacuum": ROOT.kGray + 1,
    "Aluminum": ROOT.kBlue + 1,
    "Tungsten": ROOT.kGreen + 2,
    "WGPu": ROOT.kRed + 1,
}
REF_COLORS = {
    "Vacuum": ROOT.kGray + 3,
    "Aluminum": ROOT.kBlue + 3,
    "Tungsten": ROOT.kGreen + 3,
    "WGPu": ROOT.kRed + 3,
}

E_MAX_MEV = 20.0
N_BINS = 20  # 1 MeV wide bins


def load_energies(path: str) -> np.ndarray:
    f = ROOT.TFile.Open(path)
    tree = f.Get("EscapeNeutrons")
    n = tree.GetEntries()
    vals = np.empty(n, dtype=np.float64)
    for i, entry in enumerate(tree):
        vals[i] = entry.escapeE_MeV
    f.Close()
    return vals


def load_n_events(path: str) -> int:
    f = ROOT.TFile.Open(path)
    n = f.Get("Events").GetEntries()
    f.Close()
    return n


def build_curve(spec: str, bin_edges: np.ndarray, bin_centers: np.ndarray) -> tuple[str, int, np.ndarray, np.ndarray]:
    path, label = spec.rsplit(":", 1)
    energies = load_energies(path)
    n_events = load_n_events(path)
    counts, _ = np.histogram(energies, bins=bin_edges)
    counts = counts.astype(float)

    norm = counts[0] if counts[0] > 0 else 1.0
    rel_counts = counts / norm

    keep = rel_counts > 0
    return label, n_events, bin_centers[keep].astype(float), rel_counts[keep]


def make_graph(xs, ys, color, style, marker):
    g = ROOT.TGraph(len(xs), xs, ys)
    g.SetLineColor(color)
    g.SetLineStyle(style)
    g.SetMarkerColor(color)
    g.SetMarkerStyle(marker)
    g.SetMarkerSize(1.0)
    g.SetTitle("")
    return g


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="path.root:Label pairs (simulated data)")
    ap.add_argument("--ref", action="append", default=[], help="path.root:Label pairs (reference/target data)")
    ap.add_argument("--out", default="neutron_energy_spectrum.png")
    args = ap.parse_args()

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)

    canvas = ROOT.TCanvas("c", "Neutron Energy Spectrum Shape", 900, 800)
    canvas.SetLogy()
    canvas.SetGrid()

    legend = ROOT.TLegend(0.58, 0.55, 0.88, 0.88)
    legend.SetHeader("Sphere Material")
    legend.SetBorderSize(0)

    graphs = []  # keep refs alive for the lifetime of the canvas
    bin_edges = np.linspace(0.0, E_MAX_MEV, N_BINS + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    sim_curves = [build_curve(spec, bin_edges, bin_centers) for spec in args.files]
    ref_curves = [build_curve(spec, bin_edges, bin_centers) for spec in args.ref]
    full_events = max((n for _, n, _, _ in sim_curves), default=0)

    frame = None
    for label, n_events, xs, ys in sim_curves:
        color = COLORS.get(label, ROOT.kBlack)
        g = make_graph(xs, ys, color, 2, 20)
        graphs.append(g)
        is_partial = n_events < full_events
        legend_label = f"{label} ({n_events} evt, partial)" if is_partial else label
        legend.AddEntry(g, legend_label, "lp")

        if frame is None:
            frame = g.Clone()
            frame.Draw("APL")
            frame.GetXaxis().SetTitle("Neutron Energy (MeV)")
            frame.GetXaxis().SetLimits(0.0, E_MAX_MEV)
            frame.GetYaxis().SetTitle("Relative Counts (E#approx0 normalized)")
        else:
            g.Draw("PL SAME")

    if ref_curves:
        legend.AddEntry(0, "Reference (shell geom, full stats)", "")
        for label, n_events, xs, ys in ref_curves:
            color = REF_COLORS.get(label, ROOT.kBlack)
            g = make_graph(xs, ys, color, 1, 21)
            graphs.append(g)
            legend.AddEntry(g, f"{label} (ref)", "lp")
            if frame is None:
                frame = g.Clone()
                frame.Draw("APL")
                frame.GetXaxis().SetTitle("Neutron Energy (MeV)")
                frame.GetXaxis().SetLimits(0.0, E_MAX_MEV)
                frame.GetYaxis().SetTitle("Relative Counts (E#approx0 normalized)")
            else:
                g.Draw("PL SAME")

    legend.Draw()
    canvas.SaveAs(args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
