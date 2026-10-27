# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Geant4 Monte Carlo simulation of a spacecraft bus with an optional special nuclear
material (SNM) payload, tallying neutrons that escape the bus into free space.

The project's actual question: can a satellite-borne detector separate the signal of
SNM aboard another satellite from the ambient space radiation background — cosmic/galactic
rays, Van Allen belt trapped protons, and atmospheric albedo protons/neutrons? This
simulation is a test problem for that broader goal: proving out (in simulation) that the
signal is separable from background is a prerequisite to designing and flying an actual
detection satellite, and being first to demonstrate detection is the point.

The main background source is the Van Allen belt trapped protons, and AP9 shows they are strongly
directional: the flux depends on pitch angle relative to the local magnetic field. At 1000 km it is
close to zero below ~60° (loss cone) and peaks at 90°. The energy spectrum also changes with pitch
angle, so the primary proton source samples energy and direction together from AP9
(`/pmgun/pitchTable`) instead of treating the flux as isotropic or as a fixed mono-energetic beam.

`README_UPDATED.txt` is the authoritative, detailed reference for the geometry, macro
commands, and ntuple schema — read it before making changes to detector/tally logic;
this file only summarizes what spans multiple files.

## Build

```bash
mkdir -p build && cd build
cmake .. -DGeant4_DIR=/path/to/Geant4Config.cmake
cmake --build . -j
```

Geant4 (11.3.2) is installed through nix, and Claude's shell does not load that nix environment,
so Claude cannot configure, build, or run `sim`. The user builds and runs it; Claude can at most
syntax-check against the headers in `/nix/store/*geant4-11.3.2/include/Geant4`.

CMake globs all of `src/*.cc` into the `sim` executable and copies `macros/*.mac` into
`build/`. There is no test suite or linter in this repo.

## Running

```bash
./sim                                          # interactive (G4UIExecutive + vis.mac)
./sim macros/run_spacecraft.mac                # batch mode
./sim macros/run_spacecraft.mac QGSP_INCLXX_HP # choose reference physics list (arg 2)
./sim macros/run_spacecraft.mac FTFP_INCLXX_HP decay  # arg 3 == "decay" registers G4RadioactiveDecayPhysics
```

Physics list defaults to `FTFP_INCLXX_HP` and is selected via `G4PhysListFactory` in
`sim.cc` — there is no separate `PMPhysicsList` class. Output basename/type is set from
the macro (`/analysis/setFileName`, `/analysis/setFileType root`); Geant4 does not create
output directories, so the target dir must exist first.

AP9 exports (`scripts/1000km_<angle>deg_ap9.txt`, flux vs. time at one pitch angle each) are
collapsed into a pitch × energy CSV with `scripts/ap9_pitch_table.py` (kept in `macros/`, e.g.
`macros/ap9_pitch_1000km.csv`), and the gun reads that CSV via `/pmgun/pitchTable`.

`scripts/run_batch.sh` sweeps materials/energies/event-counts by generating temp macros
from `macros/materials.tsv` + `macros/common_beam.mac` and invoking `sim` per combination.

## Architecture

Geant4 sim → per-run ntuples → plotting scripts. `processing/` is not in use: don't read,
edit, move, or reference anything in it, and don't adapt sim changes to it.

**Geant4 sim (`sim.cc`, `src/PM*.cc`)**: standard Geant4 action pattern
(`PMActionInitialization` wires up `PMPrimaryGenerator`/`PMRunAction`/`PMEventAction`/
`PMSteppingAction`). `PMDetectorConstruction` builds a fixed concentric geometry (World →
BusShell → BusEnvelope → SNMSphere → SNMCore, plus electronics boxes) and exposes
dimensions/materials as runtime macro commands (`/det/...`) via `G4GenericMessenger` —
this is how a "vacuum" (background) run vs. an "SNM present" run are the *same* geometry
with `/det/snmMaterial` toggled between `G4_Galactic` and `U235_solid`/`HEU`/
`Pu239_solid`/`WGPu`. All the actual tallying (region classification, neutron birth/escape
recording, event classification as none/primaryHadronic/snmFissionLike) lives in
`PMSteppingAction`, not in a `G4VSensitiveDetector`. `PMRunAction` defines the two output
ntuples, `Events` (one row/event) and `EscapeNeutrons` (one row per neutron crossing into
the world), joined on `eventID`. Region codes (0-5, 99=unknown) and neutron creator codes
(RadioactiveDecay/Deexcitation/Inelastic/Fission/Capture/Elastic) are simulation-wide
conventions defined in `PMSteppingAction` and documented in `README_UPDATED.txt`.

**Per-run outputs** land in `build/outputs/*.root` (or CSV if file type isn't set to
root). `scripts/plot_*.py` reproduce specific figures directly from one or more ROOT/CSV
files (see each script's docstring for its CLI).

## Conventions

- Energies in MeV (kinetic), times in ns (Geant4 global time), counts as integers.
- `/det/...` geometry/material changes must happen before `/run/initialize`.
- When adding a new tallied quantity, it needs a matching column defined in both
  `PMRunAction` (ntuple schema) and the fill call in `PMSteppingAction`.
