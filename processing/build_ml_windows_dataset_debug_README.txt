README: build_ml_windows_dataset debug / full-detail CSV

This note explains the debug-facing / full-detail CSV written by
build_ml_windows_dataset_v2.py when you use --dataset-view full
(or when you write a --debug-out file while producing an ML-facing CSV).

======================================================================
1) WHAT ONE ROW MEANS
======================================================================

Each row is one synthetic detector measurement window. In your current
workflow that is usually a 10 s acquisition interval.

A row is produced by:
  1. reading one or more Geant4 ROOT files for a specific physical scenario,
  2. projecting escaping neutrons to a virtual detector plane,
  3. applying detector response assumptions such as efficiency, threshold,
     energy smearing, and timing jitter,
  4. optionally adding flat detector background and library-based self-
     background,
  5. mixing mono-energetic proton runs according to AP9-derived weights,
  6. summarizing the resulting detector-facing hits into scalar features
     and an energy histogram.

So a row is NOT:
  - one Geant4 primary event,
  - one raw neutron track,
  - or necessarily a contiguous real orbital time segment.

It is a synthetic detector window drawn from a specified source environment
and detector configuration.

======================================================================
2) HOW TO THINK ABOUT THE DEBUG CSV
======================================================================

The debug CSV contains three kinds of information:

  A. Detector-like observables
     Things a detector could plausibly report in one window, such as total
     counts, threshold counts, cluster summaries, and binned measured energy.

  B. Scenario / provenance metadata
     Things that identify which Geant4 case the row came from, such as
     material, shell radii, beam direction, and physics list.

  C. Truth / QC bookkeeping
     Optional columns that tell you how the final counts decompose into
     signal vs background or how many proton primaries were sampled from each
     mono-energetic run.

That makes the debug CSV excellent for:
  - sanity checks,
  - plots,
  - ablation studies,
  - leakage checks,
  - and understanding why a model works or fails.

It is not the right table to hand directly to a model without dropping
non-observable columns.

======================================================================
3) COLUMN GROUPS AND PHYSICAL SIGNIFICANCE
======================================================================

A) Labels and coarse identity
-----------------------------

class_label
  The coarse target class used for supervised learning.

  In the current script:
    - SNM   = special nuclear material cases such as WGPu-like payloads
    - HighZ = non-SNM high-Z comparison cases such as tungsten
    - Benign = aluminum or vacuum-like comparison cases

  Physical meaning:
    This is the ground-truth label you want the model to predict.

  ML role:
    Use as y, not as an input feature.

snmMaterial
  The Geant4 material tag for the payload case, such as WGPu, G4_W,
  G4_Al, or G4_Galactic.

  Physical meaning:
    This is the underlying material hypothesis used in the Geant4 run.

  ML role:
    Usually metadata only. If you give it to the model as an input, the
    model can learn the material tag directly rather than the neutron
    signature.

material_exact
  A more specific identifier built from material plus shell radii, for
  example:
    G4_Al|Rout=70|Rin=65

  Physical meaning:
    This distinguishes cases that share the same material tag but represent
    different shell constructions, such as your geometry-matched vs
    mass-matched aluminum controls.

  ML role:
    Provenance / debugging only.

B) Row indexing and split bookkeeping
-------------------------------------

sample_index
  Integer index of the synthetic window within a scenario/source-case/regime
  combination.

  Physical meaning:
    None by itself. It simply labels which Monte Carlo window draw this is.

  Important note:
    It does NOT imply true time order along an orbit.

scenario_id
  Compact identifier built from material, shell radii, beam direction, and
  physics list.

  Physical meaning:
    Identifies the underlying Geant4 physics scenario from which the row was
    sampled.

  ML role:
    Grouping / leakage control only.

split_group_id
  Composite grouping key of the form:
    scenario_id | source_case | flux_regime

  Physical meaning:
    None directly. It exists so related rows from the same underlying
    library are not split across train/validation/test by accident.

  ML role:
    Grouping only, never a feature.

geant_seed_ids
  String describing which Geant4 random seed(s) contributed to the scenario
  library.

  Physical meaning:
    Useful for reproducibility and seed-variation QC, but not a detector
    observable.

  In your current files this may be UNKNOWN if no seed was parsed from the
  filename.

ml_split  [optional; only if --assign-splits is used]
  Train/val/test assignment.

  Physical meaning:
    None. Pure ML bookkeeping.

C) Source-environment labels
----------------------------

source_case
  AP9 confidence case used to build the source spectrum, typically 50, 75,
  or 95.

  Physical meaning:
    This is a source-environment assumption, not a detector reading. It
    changes how many incident protons are sampled from each mono-energetic
    library component.

  Recommended use:
    Keep this fixed within a training run unless you are intentionally
    studying robustness to source-case mismatch.

flux_regime
  Name of the source-flux regime used for the row, for example:
    ap9_average
    high_gt60
    low_gt60

  Physical meaning:
    Encodes whether the row came from the 7-day AP9 average spectrum or from
    a user-defined high-flux / low-flux approximation.

flux_regime_mode
  How the regime was defined.

  Typical values:
    average
      Use the week-average AP9 spectrum directly.

    target_above_threshold
      Rescale the spectrum so the integral proton flux above some threshold
      equals a user-requested value.

flux_regime_threshold_MeV
  Energy threshold that defines the special regime, often 60 MeV.

  Physical meaning:
    The regime normalization is set by the incident proton flux above this
    threshold.

flux_regime_duty_fraction
  User-supplied duty fraction for the regime.

  Physical meaning:
    Metadata about how often that regime might occur in an orbit model.
    It does not automatically reweight the dataset unless you do that
    separately.

flux_regime_scale_factor
  Multiplicative factor applied to the baseline AP9 spectrum to realize the
  requested regime.

  Physical meaning:
    Tells you how much the source spectrum was boosted or reduced relative to
    the baseline 7-day mean.

source_total_flux_cm2_s
  Total incident proton flux represented by the source mix, in cm^-2 s^-1.

  Physical meaning:
    This is a source normalization, not a detector count rate.

source_flux_above_regime_threshold_cm2_s
  Incident proton flux above the regime threshold, in cm^-2 s^-1.

  Physical meaning:
    Useful when checking statements like:
    "the >60 MeV proton flux is about 1e4 cm^-2 s^-1 in this regime."

D) Physical scenario metadata from Geant4
-----------------------------------------

sphereOuterR_mm, sphereInnerR_mm
  Outer and inner radii of the spherical shell / cavity used in the Geant4
  target model, in mm.

  Physical meaning:
    These determine shell size and thickness, which in turn affect proton
    interactions, secondary production, moderation, and neutron escape.

beamDirX, beamDirY, beamDirZ
  Unit-vector components of the mono-directional proton beam in the Geant4
  run.

  Physical meaning:
    Illumination direction matters because the escape-neutron field can
    depend on both geometry and orientation.

  ML role:
    Provenance only unless your eventual deployment also knows the beam /
    source direction.

physicsListName
  Name of the Geant4 physics list used for transport and interactions.

  Physical meaning:
    This specifies the interaction models behind the simulated signal.

  ML role:
    Provenance only.

E) Detector and measurement configuration
-----------------------------------------

window_s
  Measurement integration time in seconds.

  Physical meaning:
    Longer windows improve counting statistics but reduce temporal
    resolution.

panel_x_m, panel_y_center_m, panel_z_center_m
  Position of the virtual detector plane in meters.

  Physical meaning:
    These determine projection geometry and therefore acceptance and time of
    flight.

panel_y_size_m, panel_z_size_m, panel_area_m2
  Detector plane dimensions and area.

  Physical meaning:
    Larger panel area increases accepted neutron counts and improves
    statistics.

efficiency
  Detection efficiency applied to accepted hits.

  Physical meaning:
    A lumped probability that a neutron reaching the detector is actually
    recorded.

threshold_MeV
  Energy threshold in MeV applied after detector response.

  Physical meaning:
    Hits below threshold are discarded, changing both count rate and
    spectral shape.

sigmaEfrac
  Relative energy resolution parameter, sigma_E / E.

  Physical meaning:
    Larger values blur the measured spectrum and weaken fine spectral
    features.

sigmaT_ns
  Timing jitter standard deviation in ns.

  Physical meaning:
    Larger values blur coincidence structure and time-based multiplicity
    cues.

coinc_ns
  Coincidence clustering window in ns.

  Physical meaning:
    Hits separated by less than this gap are placed in the same cluster.
    This is a feature-extraction parameter, not necessarily a hardware
    dead time.

background_rate_hz
  Flat Poisson background rate in Hz.

  Physical meaning:
    Detector floor background added in post-processing, independent of the
    Geant4 signal library.

F) Final detector-observable count and hardness features
--------------------------------------------------------

count_total
  Total number of recorded hits in the window after detector response and
  background addition.

  Physical meaning:
    The simplest proxy for detectability / source strength.

count_gt1, count_gt5, count_gt10, count_gt20
  Number of recorded hits with measured energy greater than 1, 5, 10, or
  20 MeV.

  Physical meaning:
    Coarse threshold summaries of spectral hardness.

frac_gt1, frac_gt5, frac_gt10, frac_gt20
  Fraction of count_total above each threshold.

  Physical meaning:
    These normalize out total count level and emphasize spectral shape.

ratio_gt5_to_gt1, ratio_gt10_to_gt1, ratio_gt20_to_gt5
  Ratios of threshold counts.

  Physical meaning:
    Compact hardness descriptors. For example, a larger ratio_gt20_to_gt5
    suggests a relatively harder high-energy tail.

count_meanE_MeV, count_medianE_MeV
  Mean and median measured hit energy in MeV.

  Physical meaning:
    Single-number summaries of the measured neutron spectrum.

G) Energy-histogram bookkeeping
-------------------------------

count_energy_hist_covered
  Number of hits that fall inside the chosen histogram range.

count_energy_hist_overflow
  Number of hits above the histogram maximum.

frac_energy_hist_covered
  Fraction of count_total captured inside the histogram range.

  Physical meaning:
    These help you judge whether the chosen histogram range is wide enough
    for the source and detector assumptions.

  Important note:
    In the current implementation:
      count_total = count_energy_hist_covered + count_energy_hist_overflow
    and count_energy_hist_overflow contains the same information as
    Ebin_overflow.

H) Binned measured-energy spectrum
----------------------------------

Ebin_000 through Ebin_019
  Counts in the measured-energy histogram bins.

  Physical meaning:
    This is the coarse reconstructed neutron spectrum seen by the detector in
    one acquisition window. These are usually the most information-rich
    features in the table.

  In the current default build:
    Emax  = 100 MeV
    Ebins = 20
    Bin width = 5 MeV

  So the current bins are approximately:
    Ebin_000 : 0 to 5 MeV
    Ebin_001 : 5 to 10 MeV
    ...
    Ebin_019 : 95 to 100 MeV

  If you change --Emax-MeV or --Ebins, the physical meaning of the Ebin_*
  columns changes accordingly.

Ebin_overflow
  Number of measured hits above the histogram maximum.

  Physical meaning:
    Captures the part of the spectrum above the chosen histogram range.

I) Coincidence / clustering features
------------------------------------

These are built from hit times after timing jitter and after background has
been added. The script sorts the hit times and starts a new cluster whenever
the gap exceeds coinc_ns.

n_clusters
  Total number of time clusters in the window.

  Physical meaning:
    Roughly the number of separated burst-like episodes.

max_cluster
  Largest cluster multiplicity in the window.

  Physical meaning:
    A large value indicates at least one dense burst of nearly coincident
    hits.

mean_cluster
  Average cluster multiplicity.

  Physical meaning:
    Summarizes how bursty the window is on average.

n_clusters_ge2, n_clusters_ge3, n_clusters_ge4, n_clusters_ge10
  Number of clusters with multiplicity at least 2, 3, 4, or 10.

  Physical meaning:
    These are meant to capture multi-hit burst structure that may help
    separate correlated signal-rich windows from mostly uncorrelated
    background singles.

J) Optional truth / QC columns  [only if --include-truth-qc is used]
---------------------------------------------------------------------

qc_count_signal
  Number of recorded hits in the window that came from the intended signal
  scenario library.

qc_count_self_bg
  Number of recorded hits coming from the optional library-based
  self-background source.

qc_count_floor_bg
  Number of recorded hits coming from the flat Poisson floor background.

qc_count_signal_fraction
  Fraction of count_total attributable to the intended signal component.

  Physical meaning:
    Direct measure of contamination and detectability in the synthetic
    dataset.

qc_incident_primaries_total
  Total number of incident proton primaries sampled across all mono-energetic
  library components to create the window.

qc_incident_E###
  One column per beam energy used in the library, for example:
    qc_incident_E010, qc_incident_E015, ..., qc_incident_E300

  Physical meaning:
    These tell you how many proton primaries from each mono-energetic Geant4
    run contributed to the weighted source realization.

  ML role:
    QC only. These leak the source-construction process directly.

======================================================================
4) WHAT SHOULD AND SHOULD NOT GO INTO AN ML MODEL
======================================================================

Good candidates for X:
  - count_total
  - threshold features: count_gt*, frac_gt*, ratio_*
  - cluster features: n_clusters, max_cluster, mean_cluster, n_clusters_ge*
  - Ebin_* and Ebin_overflow
  - optionally window_s, coinc_ns, background_rate_hz if the model should
    know acquisition settings

Do NOT train on:
  - class_label
  - snmMaterial
  - material_exact
  - scenario_id
  - split_group_id
  - geant_seed_ids
  - source_case
  - flux_regime unless you deliberately want regime-conditioned models
  - physicsListName
  - beamDirX / beamDirY / beamDirZ
  - shell radii
  - any qc_* column

======================================================================
5) EXACT CURRENT COLUMN LIST IN THE EXAMPLE FULL CSV
======================================================================

class_label, material_exact, scenario_id, source_case, flux_regime
split_group_id, sample_index, geant_seed_ids, snmMaterial, sphereOuterR_mm
sphereInnerR_mm, beamDirX, beamDirY, beamDirZ, physicsListName
window_s, panel_x_m, panel_y_center_m, panel_z_center_m, panel_y_size_m
panel_z_size_m, panel_area_m2, efficiency, threshold_MeV, sigmaEfrac
sigmaT_ns, coinc_ns, background_rate_hz, flux_regime_mode, flux_regime_threshold_MeV
flux_regime_duty_fraction, flux_regime_scale_factor, source_total_flux_cm2_s, source_flux_above_regime_threshold_cm2_s, count_total
count_gt1, count_gt5, count_gt10, count_gt20, frac_gt1
frac_gt5, frac_gt10, frac_gt20, ratio_gt5_to_gt1, ratio_gt10_to_gt1
ratio_gt20_to_gt5, count_meanE_MeV, count_medianE_MeV, count_energy_hist_covered, count_energy_hist_overflow
frac_energy_hist_covered, Ebin_000, Ebin_001, Ebin_002, Ebin_003
Ebin_004, Ebin_005, Ebin_006, Ebin_007, Ebin_008
Ebin_009, Ebin_010, Ebin_011, Ebin_012, Ebin_013
Ebin_014, Ebin_015, Ebin_016, Ebin_017, Ebin_018
Ebin_019, Ebin_overflow, n_clusters, max_cluster, mean_cluster
n_clusters_ge2, n_clusters_ge3, n_clusters_ge4, n_clusters_ge10

======================================================================
6) OPTIONAL COLUMNS THAT MAY APPEAR IN FUTURE DEBUG CSVs
======================================================================

These are documented above even if they are absent from your current
79-column example file:
  - ml_split
  - qc_count_signal
  - qc_count_self_bg
  - qc_count_floor_bg
  - qc_count_signal_fraction
  - qc_incident_primaries_total
  - qc_incident_E###  (one per beam energy present in the source library)
