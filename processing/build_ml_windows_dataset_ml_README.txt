README: build_ml_windows_dataset ML-facing CSV

This note explains the ML-facing CSV written by build_ml_windows_dataset_v2.py
when you use --dataset-view ml.

======================================================================
1) WHAT ONE ROW MEANS
======================================================================

Each row is one synthetic detector acquisition window, usually 10 s long.

A row already includes:
  - AP9-weighted mixing of mono-energetic proton Geant4 runs,
  - projection of escape neutrons to the virtual detector plane,
  - detector efficiency / threshold / resolution effects,
  - optional library-based self-background,
  - optional flat detector background.

So this row is designed to resemble a compact feature vector that could be
handed to a baseline classifier.

======================================================================
2) WHY THIS FILE EXISTS
======================================================================

The ML-facing CSV is meant to keep only:
  - the label(s) you need for supervised learning,
  - minimal provenance needed to organize experiments,
  - and detector-like observables from each synthetic window.

Compared with the debug CSV, most of the "how the sausage was made" fields
are deliberately removed.

That makes this the safer file to hand to a model first.

======================================================================
3) COLUMN GROUPS AND PHYSICAL SIGNIFICANCE
======================================================================

A) Labels and metadata  (do not train on these)
------------------------------------------------

class_label
  Ground-truth class to be predicted.

  In the current setup:
    - SNM
    - HighZ
    - Benign

  ML role:
    This is y, not an input feature.

snmMaterial
  Underlying Geant4 material tag such as WGPu, G4_W, G4_Al, or G4_Galactic.

  Physical meaning:
    Metadata describing which material case generated the window.

  ML role:
    Usually keep out of X. It is useful for error analysis and plotting.

source_case
  AP9 confidence case used to define the source environment, typically 50,
  75, or 95.

  Physical meaning:
    Changes the incident proton source spectrum. It is not a detector
    measurement.

  Recommended use:
    Train separate models per source_case unless you are intentionally
    studying cross-case robustness.

flux_regime
  Name of the source regime, such as:
    ap9_average
    high_gt60
    low_gt60

  Physical meaning:
    Indicates which incident-flux environment was used to generate the row.

  ML role:
    Usually metadata only.

sample_index
  Synthetic window index within a scenario/regime combination.

  Physical meaning:
    None by itself. It is bookkeeping, not time ordering.

ml_split  [optional; only if --assign-splits is used]
  Train / validation / test assignment.

  ML role:
    Partitioning only, never an input feature.

B) Measurement settings
-----------------------

These are not truth leaks, but they are also not raw counts. They describe
the acquisition settings under which the row was generated.

window_s
  Acquisition length in seconds.

  Physical meaning:
    Longer windows collect more counts and improve counting statistics.

coinc_ns
  Coincidence clustering gap in ns.

  Physical meaning:
    Sets how hits are grouped into time clusters.

background_rate_hz
  Flat added detector background rate in Hz.

  Physical meaning:
    Tells you how much unstructured floor background was injected into the
    synthetic measurement.

  Recommended use:
    If all rows share the same setting, it can be dropped from X.
    If you intentionally mix difficulty levels, keeping it may help the
    model adapt to changing background conditions.

C) Window-level count and hardness features
-------------------------------------------

These are the first scalar features I would try in a baseline model.

count_total
  Total recorded hits in the window.

  Physical meaning:
    Crude detectability / source-strength feature.

count_gt1, count_gt5, count_gt10, count_gt20
  Counts above fixed measured-energy thresholds.

  Physical meaning:
    Coarse summaries of spectral hardness.

frac_gt1, frac_gt5, frac_gt10, frac_gt20
  Threshold counts normalized by count_total.

  Physical meaning:
    More shape-focused and less sensitive to absolute rate.

ratio_gt5_to_gt1, ratio_gt10_to_gt1, ratio_gt20_to_gt5
  Ratios of threshold counts.

  Physical meaning:
    Compact hardness indicators that help separate "more neutrons" from
    "harder neutrons."

count_meanE_MeV, count_medianE_MeV
  Mean and median measured hit energy.

  Physical meaning:
    Single-number summaries of the measured spectrum.

D) Coincidence / burstiness features
------------------------------------

These are computed from hit times within the window using the clustering
gap coinc_ns.

n_clusters
  Total number of separated hit clusters.

max_cluster
  Largest multiplicity of any one cluster.

mean_cluster
  Average multiplicity per cluster.

n_clusters_ge2, n_clusters_ge3, n_clusters_ge4, n_clusters_ge10
  Number of clusters with multiplicity at least 2, 3, 4, or 10.

  Physical meaning of the group:
    These columns try to capture whether the window looks like many isolated
    singles or contains burst-like multi-hit structure that could reflect
    correlated secondaries.

E) Binned measured-energy spectrum
----------------------------------

Ebin_000 through Ebin_019
  Measured neutron counts in equal-width energy bins.

  Physical meaning:
    This is the coarse reconstructed neutron spectrum seen by the detector in
    one window. This is often the most informative feature family in the
    table because it preserves much more of the spectral signature than the
    threshold counts alone.

  In the current default configuration:
    Emax  = 100 MeV
    Ebins = 20
    Bin width = 5 MeV

  So this is currently a 20-component coarse spectrum spanning
  approximately 0 to 100 MeV.

Ebin_overflow
  Measured hits above the histogram maximum.

  Physical meaning:
    Protects you against losing the high-energy tail when the histogram range
    is capped.

======================================================================
4) PRACTICAL WAY TO BUILD X AND y
======================================================================

A clean first pass is:

  y = class_label

  Drop from X:
    class_label, snmMaterial, source_case, flux_regime, sample_index,
    window_s, coinc_ns, background_rate_hz if present.

  Keep in X:
    count_total,
    count_gt*, frac_gt*, ratio_*,
    n_clusters, max_cluster, mean_cluster, n_clusters_ge*,
    Ebin_*, Ebin_overflow

======================================================================
5) WHAT IS INTENTIONALLY ABSENT FROM THE ML-FACING CSV
======================================================================

Compared with the debug CSV, this view intentionally drops:
  - Geant4 physics-list metadata
  - beam-direction components
  - shell radii and detailed scenario identifiers
  - detector-plane geometry details
  - source-normalization factors
  - source-construction bookkeeping
  - truth / QC decomposition columns

That is why this is the right file to hand to a classifier first.

======================================================================
6) SHORT INTUITION FOR SOMEONE NEW TO THIS PROBLEM
======================================================================

If you only remember one thing, it is this:

  - count_total tells you how many neutron-like hits arrived in the window
  - count_gt*, frac_gt*, ratio_*, count_meanE_MeV, and count_medianE_MeV
    tell you whether that window is relatively soft or hard in energy
  - Ebin_* tells you the coarse shape of the measured neutron spectrum
  - the cluster features tell you whether the window contains isolated hits
    or burst-like multi-hit structure

That is a reasonable detector-facing summary of a proton-induced payload
signature in the current space-verification workflow.

======================================================================
7) EXACT CURRENT COLUMN LIST IN THE EXAMPLE ML-FACING CSV
======================================================================

class_label, snmMaterial, source_case, flux_regime, sample_index, window_s
coinc_ns, background_rate_hz, count_total, count_gt1, count_gt5, count_gt10
count_gt20, frac_gt1, frac_gt5, frac_gt10, frac_gt20, ratio_gt5_to_gt1
ratio_gt10_to_gt1, ratio_gt20_to_gt5, count_meanE_MeV, count_medianE_MeV, n_clusters, max_cluster
mean_cluster, n_clusters_ge2, n_clusters_ge3, n_clusters_ge4, n_clusters_ge10, Ebin_000
Ebin_001, Ebin_002, Ebin_003, Ebin_004, Ebin_005, Ebin_006
Ebin_007, Ebin_008, Ebin_009, Ebin_010, Ebin_011, Ebin_012
Ebin_013, Ebin_014, Ebin_015, Ebin_016, Ebin_017, Ebin_018
Ebin_019, Ebin_overflow
