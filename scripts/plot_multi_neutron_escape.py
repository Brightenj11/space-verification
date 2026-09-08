#!/usr/bin/env python3
"""Reproduce the multi-neutron escape survival-curve plot from Events ntuples.

python plot_multi_neutron_escape.py build/outputs/proton_100MeV_Vacuum_seed1.root:Vacuum \
    build/outputs/proton_100MeV_Aluminum_seed1.root:Aluminum \
    build/outputs/proton_100MeV_Tungsten_seed1.root:Tungsten \
    build/outputs/proton_100MeV_WGPu_seed1.root:WGPu \
    --ref processing/root_runs/proton_output_Vacuum_mev100.root:Vacuum \
    --ref processing/root_runs/proton_output_Al_massmatch_mev100.root:Aluminum \
    --ref processing/root_runs/proton_output_W_mev100.root:Tungsten \
    --ref processing/root_runs/proton_output_WGPu_mev100.root:WGPu \
    --out multi_neutron_escape.png
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


def load_n_escaped(path: str) -> np.ndarray:
    f = ROOT.TFile.Open(path)
    tree = f.Get("Events")
    n = tree.GetEntries()
    vals = np.empty(n, dtype=np.int64)
    for i, entry in enumerate(tree):
        vals[i] = entry.nEscapedTotal
    f.Close()
    return vals


def survival_curve(n_escaped: np.ndarray, n_max: int) -> tuple[np.ndarray, np.ndarray]:
    total = len(n_escaped)
    ns = np.arange(0, n_max + 1)
    probs = np.array([(n_escaped >= n).sum() / total for n in ns])
    return ns, probs


def build_curve(spec: str) -> tuple[str, int, np.ndarray, np.ndarray]:
    path, label = spec.rsplit(":", 1)
    n_escaped = load_n_escaped(path)
    n_max = int(n_escaped.max())
    ns, probs = survival_curve(n_escaped, n_max)
    keep = probs > 0
    return label, len(n_escaped), ns[keep].astype(float), probs[keep]


def make_graph(ns_k, probs_k, color, style, marker):
    g = ROOT.TGraph(len(ns_k), ns_k, probs_k)
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
    ap.add_argument("--out", default="multi_neutron_escape.png")
    args = ap.parse_args()

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)

    canvas = ROOT.TCanvas("c", "Probability of Multi-Neutron Escapes", 900, 800)
    canvas.SetLogy()
    canvas.SetGrid()

    legend = ROOT.TLegend(0.58, 0.55, 0.88, 0.88)
    legend.SetHeader("Sphere Material")
    legend.SetBorderSize(0)

    graphs = []  # keep refs alive for the lifetime of the canvas
    sim_curves = [build_curve(spec) for spec in args.files]
    ref_curves = [build_curve(spec) for spec in args.ref]

    full_events = max((n for _, n, _, _ in sim_curves), default=0)
    global_n_max = max(
        [ns_k.max() for _, _, ns_k, _ in sim_curves + ref_curves if len(ns_k)],
        default=0,
    )

    frame = None
    for label, n_events, ns_k, probs_k in sim_curves:
        color = COLORS.get(label, ROOT.kBlack)
        g = make_graph(ns_k, probs_k, color, 2, 20)
        graphs.append(g)
        is_partial = n_events < full_events
        legend_label = f"{label} ({n_events} evt, partial)" if is_partial else label
        legend.AddEntry(g, legend_label, "lp")

        if frame is None:
            frame = g.Clone()
            frame.Draw("APL")
            frame.GetXaxis().SetTitle("Escaping Neutrons (per Proton)")
            frame.GetXaxis().SetLimits(0.0, float(global_n_max))
            frame.GetYaxis().SetTitle("Probability of #geq N Escaping Neutrons")
            frame.GetYaxis().SetRangeUser(1e-5, 2.0)
        else:
            g.Draw("PL SAME")

    if ref_curves:
        legend.AddEntry(0, "Reference (shell geom, full stats)", "")
        for label, n_events, ns_k, probs_k in ref_curves:
            color = REF_COLORS.get(label, ROOT.kBlack)
            g = make_graph(ns_k, probs_k, color, 1, 21)
            graphs.append(g)
            legend.AddEntry(g, f"{label} (ref)", "lp")
            if frame is None:
                frame = g.Clone()
                frame.Draw("APL")
                frame.GetXaxis().SetTitle("Escaping Neutrons (per Proton)")
                frame.GetXaxis().SetLimits(0.0, float(global_n_max))
                frame.GetYaxis().SetTitle("Probability of #geq N Escaping Neutrons")
                frame.GetYaxis().SetRangeUser(1e-5, 2.0)
            else:
                g.Draw("PL SAME")

    legend.Draw()
    canvas.SaveAs(args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
