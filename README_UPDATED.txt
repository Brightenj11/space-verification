# Spacecraft + SNM Geant4 Simulation (escape‑neutron tally)

This codebase is a **Geant4** Monte Carlo simulation for studying neutron production and **neutron escape into free space** from a simplified spacecraft bus geometry containing an optional **special nuclear material (SNM) payload**.

The primary data products are two **analysis ntuples** written by `G4AnalysisManager`:

- **`Events`** — one row per Geant4 event (classification + per‑event neutron birth/escape tallies)
- **`EscapeNeutrons`** — one row per neutron track that crosses from the spacecraft into the **world vacuum**

The output is **CSV by default** (Geant4 g4tools `tools::wcsv::ntuple`), but can be switched to ROOT via macro.

---

## Repository layout

Typical source layout:

```
./sim.cc                         # main()
./include/
  PMActionInitialization.hh
  PMDetectorConstruction.hh
  PMEventAction.hh
  PMPrimaryGenerator.hh
  PMRunAction.hh
  PMSteppingAction.hh
./src/
  PMActionInitialization.cc
  PMDetectorConstruction.cc
  PMEventAction.cc
  PMPrimaryGenerator.cc
  PMRunAction.cc
  PMSteppingAction.cc
./*.mac                          # example Geant4 macro(s)
```

---

## Build requirements

- A working **Geant4** installation (built with the physics lists you intend to use; multithreading optional).
- A compiler toolchain compatible with your Geant4 build.

Build system files (e.g., `CMakeLists.txt`) are not shown here, but a standard Geant4 CMake build flow is expected:

```bash
mkdir -p build
cd build
cmake .. -DGeant4_DIR=/path/to/Geant4Config.cmake
cmake --build . -j
```

---

## Running

### Command‑line interface

`sim.cc` supports:

```bash
./sim [macro.mac] [physicsList] [decay]
```

- **Interactive mode:** run with **no arguments**
  - launches `G4UIExecutive`
  - executes `vis.mac` (must be in your run directory)

- **Batch mode:** provide a macro file, e.g.
  ```bash
  ./sim run_spacecraft_x100MeV_200k.mac
  ```

### Physics list selection

The second argument optionally sets a Geant4 **reference physics list** by name (via `G4PhysListFactory`).

- Default (if omitted): `FTFP_INCLXX_HP`
- Examples (commonly used in this codebase):
  - `FTFP_INCLXX_HP`
  - `FTFP_BERT_HP`
  - `QGSP_INCLXX_HP`
  - `QGSP_BIC_HP`

Example:

```bash
./sim run_spacecraft_x100MeV_200k.mac QGSP_INCLXX_HP
```

### Optional radioactive decay

If the **third** argument is exactly `decay`, the run registers `G4RadioactiveDecayPhysics`:

```bash
./sim run_spacecraft_x100MeV_200k.mac FTFP_INCLXX_HP decay
```

---

## Macro‑level controls

### Detector / geometry controls (`/det/…`)

`PMDetectorConstruction` exposes the following via `G4GenericMessenger`:

- Materials
  - `/det/busMaterial <name>`
  - `/det/snmMaterial <name>`

- Dimensions (all **full** dimensions unless stated otherwise)
  - `/det/busOuterRadius <val> mm`
  - `/det/busWallThk <val> mm`
  - `/det/busLength <val> mm`
  - `/det/sphereOuterRadius <val> mm`
  - `/det/sphereInnerRadius <val> mm`

**Important:** Set `/det/...` parameters **before** `/run/initialize` (or re‑initialize after changing them).

### Escape tally controls (`/pm/…`)

`PMSteppingAction` exposes runtime switches:

- `/pm/maxEventTime <val> ns`
  - kills tracks after this global time to bound runtime

- `/pm/killGammas <true|false>`
  - kills gamma tracks immediately (speed/declutter; can change cascade behavior)

- `/pm/killNeutronsAfterRecord <true|false>`
  - **DEBUG ONLY**: kills neutrons at birth record → you will not see escape rows

- `/pm/killNeutronsAfterEscape <true|false>`
  - recommended `true` in vacuum‑world runs (kills neutrons after they are recorded escaping)

### Primary generator controls (`/gun/…`)

The default primary generator is a `G4ParticleGun` (one particle per event). You can override particle, energy, position, and direction using standard Geant4 gun commands in a macro, e.g.:

- `/gun/particle proton`
- `/gun/energy 100 MeV`
- `/gun/position -850 0 0 mm`
- `/gun/direction 1 0 0`

### AP9 pitch-angle source (`/pmgun/…`)

Off by default. Setting a pitch table replaces the fixed gun energy, position and direction each
event; `/gun/energy`, `/gun/position` and `/gun/direction` are ignored while it is set.

- `/pmgun/pitchTable <path.csv>`: table from `scripts/ap9_pitch_table.py` (rows = pitch angle in deg,
  columns = energy in MeV, values = orbit-averaged AP9 directional flux)
  e.g. `/pmgun/pitchTable ../macros/ap9_pitch_1000km.csv` when running `sim` from `build/`
Per event: energy E and pitch angle α are sampled together from j(E, α)·sin α (j interpolated
log-log in E across the table's energy range, linear in α, mirrored about 90°, zero below the
smallest tabulated angle = loss cone). B is taken along the bus axis (+z), so α is measured from
+z. Every proton hits the same hull point, (-busOuterRadius, 0, 0), starting 100 mm back along
its direction; the gyrophase is uniform over the half of the cone that enters the hull there.

### Output controls (`/analysis/…`)

- Set the output basename:
  - `/analysis/setFileName <path/to/basename>`

- You can also switch file type (e.g., ROOT) using standard Geant4 analysis commands if enabled in your Geant4 build:
  - `/analysis/setFileType root`

**Note:** Geant4 generally does **not** create directories for you. If you set:

```
/analysis/setFileName build/outputs/run1
```

then `build/outputs/` must already exist.

### Example macro: `run_spacecraft_x100MeV_200k.mac`

The provided macro demonstrates a typical batch run (100 MeV protons, 200k events, MT enabled) and a convenient output basename:

```tcl
/control/verbose 0
/run/verbose 1
/tracking/verbose 0
/run/numberOfThreads 16

# ---------------- Geometry ----------------
# Choose ONE:
# SNM present:
#/det/snmMaterial U235_solid

# SNM absent:
#/det/snmMaterial G4_Galactic

/run/initialize

# ---------------- PM controls ----------------
/pm/maxEventTime 1e6 ns
/pm/killGammas true
/pm/killNeutronsAfterRecord false
/pm/killNeutronsAfterEscape true

# ---------------- Beam ----------------
/gun/particle proton
/gun/energy   100 MeV
/gun/position -850 0 0 mm
/gun/direction 1 0 0

# ---------------- Run controls ----------------
/control/alias N 200000
/run/printProgress 10000

# ---------------- Output ----------------
/analysis/setFileName build/outputs/run_spacecraft_x100MeV_{N}

/run/beamOn {N}
```

---

## Geometry model (default)

All geometry is centered at the origin.

- **World** (`WorldLV`)
  - `G4Box`, half‑size = 5 m (10 m full side length)
  - material: `G4_Galactic`

- **Bus envelope** (`BusEnvelopeLV`)
  - `G4Tubs`, **vacuum** cylinder that defines “inside the spacecraft bus”
  - outer radius: 0.75 m
  - full length: 2.0 m

- **Bus shell / hull** (`BusShellLV`)
  - cylindrical shell inside the envelope
  - wall thickness: 10 mm
  - material: `/det/busMaterial` (default `G4_Al`)

- **SNM shell** (`SNMSphereLV`)
  - `G4Sphere` at the origin
  - outer radius: 300 mm
  - inner radius: 200 mm (hollow shell)
  - material: `/det/snmMaterial` (default `U235_solid`)

- **SNM inner cavity** (`SNMCoreLV`)
  - only created if `sphereInnerRadius > 0`
  - vacuum sphere of radius `sphereInnerRadius`

---

## Materials

`PMDetectorConstruction` supports:

- **Custom materials defined in code** (via isotopic composition):
  - `U235_solid` (pure U‑235 metal)
  - `HEU` (90% U‑235 / 10% U‑238)
  - `Pu239_solid` (pure Pu‑239)
  - `WGPu` (weapons‑grade Pu mix + 1 wt% Ga; simplified)

- **Any NIST material name** supported by your Geant4 installation (via `G4NistManager::FindOrBuildMaterial`), e.g.:
  - `G4_Galactic`, `G4_Al`, `G4_W`, `G4_Ti`, `G4_Pb`, …

To remove the SNM payload without changing geometry, set the SNM volume material to vacuum:

```
/det/snmMaterial G4_Galactic
```

---

## Output products

### File naming (CSV vs ROOT)

This simulation creates **two ntuples**:

1. `Events` (one row per event)
2. `EscapeNeutrons` (one row per escaping neutron)

The output **basename** is controlled by Geant4 analysis:

- default (if not set in macro): `proton_output`
- set via macro: `/analysis/setFileName <basename>`

With **CSV output** (default), Geant4 g4tools typically writes **one CSV per ntuple**, and in multithreaded builds you may see a thread suffix:

- `<basename>_nt_Events.csv` or `<basename>_nt_Events_t0.csv`
- `<basename>_nt_EscapeNeutrons.csv` or `<basename>_nt_EscapeNeutrons_t0.csv`

`PMRunAction` enables `SetNtupleMerging(true)`, so in MT runs you will often only see the merged `t0` files.

With **ROOT output**, both ntuples are stored in the same file:

- `<basename>.root`

### Table relationship / join key

- `Events.eventID` is the event primary key.
- `EscapeNeutrons.eventID` is a foreign key.

There are **0..N** `EscapeNeutrons` rows per event.

---

## Shared conventions

- Energies: **MeV** (kinetic energy)
- Times: **ns** (Geant4 global time)
- Directions: unitless direction cosines (components in **[-1, +1]**)
- Counts: integers

---

## Region codes

Region codes are derived from the **logical volume name** at a step point:

| Code | Logical volume | Meaning |
|---:|---|---|
| 0 | `WorldLV` | Outside spacecraft (“world”; vacuum) |
| 1 | `BusShellLV` | Spacecraft hull/shell material |
| 2 | `BusEnvelopeLV` | Inside‑bus envelope (vacuum) |
| 4 | `SNMSphereLV` | SNM shell material volume |
| 5 | `SNMCoreLV` | Inner SNM cavity (vacuum), if enabled |
| 99 | (anything else / missing) | Unknown / not mapped |

If you rename logical volumes, this mapping will silently degrade to **99**.

---

## Event classification (`Events.class`)

`class` is computed at end of event:

- **0** (`classLabel = none`): no primary hadronic inelastic vertex latched
- **1** (`classLabel = primaryHadronic`): primary hadronic vertex latched, but no SNM fission‑like latch
- **2** (`classLabel = snmFissionLike`): ≥1 SNM fission‑like latch (`nFissionsSNM > 0`)

### What counts as the “primary hadronic vertex”

Latched only for the **primary proton** (`parentID == 0`) on the *first* step where:

- the post‑step process exists and has `ProcessType == fHadronic`, and
- either the process name contains **`Inelastic`** **OR** the step produced ≥1 secondary.

The latched “vertex region” is the **pre‑step region** (`vtxRegion`). The stored process metadata is taken from `post->GetProcessDefinedStep()`.

### What counts as “SNM fission‑like”

A heuristic latch intended for stratification (not a validated fission tally):

- only steps with `preRegion == 4` (`SNMSphereLV`)
- and the step produces **≥ 2** secondary ions/nuclei with atomic mass **A ≥ 70**

Each qualifying step increments `nFissionsSNM`; `t_firstFission_ns` stores the first latch time.

---

## Neutron creator labeling (`EscapeNeutrons.creatorCode`)

At neutron birth, the code records `track->GetCreatorProcess()` and assigns:

| `creatorCode` | `creatorCategory` | Rule |
|---:|---|---|
| 0 | `Other` / `none` | no creator process or not matched |
| 1 | `RadioactiveDecay` | creator process name == `RadioactiveDecay` |
| 2 | `Deexcitation` | `PhotonEvaporation`, `nuclearDeexcitation`, or name contains `Evaporation`/`Deexcitation` |
| 3 | `Inelastic` | name contains `Inelastic` |
| 4 | `Fission` | name == `nFission` or contains `Fission` |
| 5 | `Capture` | name == `nCapture` or contains `Capture` |
| 6 | `Elastic` | name contains `Elastic` |

Additional creator debug fields are written:

- `creatorProcessName` (sanitized for CSV)
- `creatorProcessType` (`G4ProcessType`, int)
- `creatorProcessSubType` (int)

---

## Ntuple definitions

### Ntuple: `EscapeNeutrons`

One row is written for each neutron that crosses a geometry boundary (`fGeomBoundary`) such that:

- post‑step region is **0** (`WorldLV`), and
- pre‑step region is **1** (`BusShellLV`) **or** **2** (`BusEnvelopeLV`)

A neutron track is only recorded **once per event** (deduplicated by `trackID`).

Columns:

- `eventID` (int): Geant4 event ID
- `trackID` (int): neutron track ID (unique within event)
- `birthRegion` (int): region code where neutron was born (captured at step 1)
- `birthE_MeV` (double): neutron kinetic energy at birth
- `birthT_ns` (double): neutron global time sampled on its first step
- `creatorCode` (int): coarse creator code (see mapping above)
- `escapeE_MeV` (double): neutron kinetic energy at escape boundary
- `escapeT_ns` (double): neutron global time at escape boundary
- `dirX`, `dirY`, `dirZ` (double): momentum direction components at escape
- `creatorProcessName` (string): creator process name
- `creatorCategory` (string): coarse creator category string
- `creatorProcessType` (int)
- `creatorProcessSubType` (int)

### Ntuple: `Events`

Exactly one row per event (written at `EndOfEventAction`).

Columns:

- `eventID` (int)
- `class` (int): 0/1/2 classification
- `vtxRegion` (int): region of latched primary hadronic vertex (or 99)
- `E_p_at_vertex_MeV` (double)
- `t_vertex_ns` (double)
- `nFissionsSNM` (int)
- `t_firstFission_ns` (double; -1 if none)

Neutron birth tallies (region bins 0–5):

- `nBornTotal` (int)
- `nBorn_r0` … `nBorn_r5` (int)

Neutron escape tallies (by **birth** region bins 0–5):

- `nEscapedTotal` (int)
- `nEscBirth_r0` … `nEscBirth_r5` (int)

Debug / validation helpers:

- `hasPrimaryInelastic` (int 0/1)
- `hasSNMFissionLike` (int 0/1)
- `classLabel` (string)
- `vtxRegionName` (string)
- `vtxProcessName` (string)
- `vtxProcessType` (int)
- `vtxProcessSubType` (int)

Source:

- `pitch_deg` (double): primary proton pitch angle relative to the bus axis (+z); -1 when the fixed gun is used
- `hitBus` (int 0/1): 1 if the primary proton entered the bus (regions 1-5); disk-source protons that miss are 0
- `E_primary_MeV` (double): primary proton kinetic energy at generation (sampled per event in pitch-table mode)

---

## Example CSV output (format)

Geant4 g4tools CSV output begins with a self‑describing header. Example for `EscapeNeutrons`:

```text
#class tools::wcsv::ntuple
#title Neutrons crossing into WorldLV
#separator 44
#vector_separator 59
#column int eventID
#column int trackID
#column int birthRegion
#column double birthE_MeV
#column double birthT_ns
#column int creatorCode
#column double escapeE_MeV
#column double escapeT_ns
#column double dirX
#column double dirY
#column double dirZ
#column string creatorProcessName
#column string creatorCategory
#column int creatorProcessType
#column int creatorProcessSubType
6,22,1,1.08662,98.3301,3,1.08662,98.3301,0.527868,0.371668,-0.763687,neutronInelastic,Inelastic,4,121
38,7,4,2.29254,9.65242,3,2.29254,44.9975,0.35496,-0.901832,0.246379,protonInelastic,Inelastic,4,121
38,6,4,2.8032,6.73632,3,2.79707,56.2583,-0.116125,0.608347,0.78513,protonInelastic,Inelastic,4,121
38,5,4,3.00817,6.3643,3,3.00817,35.3373,-0.716823,0.651189,0.249234,protonInelastic,Inelastic,4,121
38,45,3,0.664714,27.2315,3,0.410803,105.68,0.985639,0.0961995,-0.138788,neutronInelastic,Inelastic,4,121
```

Example for the per‑event `Events` ntuple:

```text
#class tools::wcsv::ntuple
#title Per-event summary (escape-focused)
#separator 44
#vector_separator 59
#column int eventID
#column int class
#column int vtxRegion
#column double E_p_at_vertex_MeV
#column double t_vertex_ns
#column int nFissionsSNM
#column double t_firstFission_ns
#column int nBornTotal
#column int nBorn_r0
#column int nBorn_r1
#column int nBorn_r2
#column int nBorn_r4
#column int nBorn_r5
#column int nEscapedTotal
#column int nEscBirth_r0
#column int nEscBirth_r1
#column int nEscBirth_r2
#column int nEscBirth_r4
#column int nEscBirth_r5
#column int hasPrimaryInelastic
#column int hasSNMFissionLike
#column string classLabel
#column string vtxRegionName
#column string vtxProcessName
#column int vtxProcessType
#column int vtxProcessSubType
0,0,99,0,0,0,-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,none,none,none,-1,-1
1,0,99,0,0,0,-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,none,none,none,-1,-1
2,0,99,0,0,0,-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,none,none,none,-1,-1
3,0,99,0,0,0,-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,none,none,none,-1,-1
4,0,99,0,0,0,-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,none,none,none,-1,-1
```

---

## Operational notes / edge cases

- **Escape counting is first‑crossing only.** A neutron track that later re‑enters and escapes again will still only produce one row.
- **Unknown region code = 99.** If a neutron is born in an unmapped logical volume, `birthRegion` will be 99 and it will not contribute to the `r0..r5` binned counts.
- **`killNeutronsAfterRecord` will eliminate escapes.** Leave this `false` for production.
- **`maxEventTime` truncates late‑time physics.** If you care about late thermalization / long tails, increase it.
