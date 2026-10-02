"""Collapse AP9 per-pitch-angle time series into one (pitch angle x energy) table.

Each AP9 export (e.g. 1000km_60deg_ap9.txt) is flux vs time at ONE pitch angle
("# flux dir: 60"). This time-averages every file (orbit average, zeros included)
and stacks them into a CSV the Geant4 gun reads via /pm/pitchTable:

    pitch_deg,1.0,10.0,...        <- header: energies in MeV
    60,3.11e+00,6.33e-02,...      <- orbit-averaged flux at that pitch angle

Usage: python scripts/ap9_pitch_table.py 'scripts/1000km_*deg_ap9.txt' -o macros/ap9_pitch_1000km.csv
"""
import argparse
import glob
import re

import numpy as np


def read_ap9(path):
    angle, energies = None, None
    with open(path) as f:
        for line in f:
            if not line.startswith("#"):
                break
            if m := re.search(r"flux dir:\s*([\d.]+)", line):
                angle = float(m.group(1))
            if "Time (min)" in line:
                energies = [float(e) for e in re.findall(r"at ([\d.]+) MeV", line)]
    flux = np.loadtxt(path, delimiter=",", comments="#")[:, 1:]
    assert angle is not None and energies and flux.shape[1] == len(energies), path
    return angle, energies, flux.mean(axis=0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pattern", help="glob of AP9 exports, one per pitch angle")
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args()

    rows = sorted(read_ap9(f) for f in glob.glob(a.pattern))
    assert rows, f"no files match {a.pattern}"
    energies = rows[0][1]
    assert all(r[1] == energies for r in rows), "files must share the same energy grid"
    with open(a.out, "w") as f:
        f.write("pitch_deg," + ",".join(f"{e:g}" for e in energies) + "\n")
        for angle, _, mean in rows:
            f.write(f"{angle:g}," + ",".join(f"{x:.6e}" for x in mean) + "\n")
    print(f"wrote {a.out}: {len(rows)} angles {[r[0] for r in rows]} x {len(energies)} energies")


if __name__ == "__main__":
    main()
