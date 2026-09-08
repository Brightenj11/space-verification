Tier progression and output filename guide

This note explains two things:

1. What each dataset tier is trying to represent physically.
2. How the output filename is meant to tell you what changed from one dataset to the next.

--------------------------------------------------
1. What the tier structure is doing
--------------------------------------------------

All of the tiers start from the same basic idea: Geant4 gives us a library of neutrons that could be produced when trapped protons hit different payload materials in orbit. The dataset builder then turns that source library into many synthetic 10-second detector measurements.

The tiers do not change the underlying proton-nuclear interaction physics in the Geant4 runs. Instead, they change how difficult the measurement problem is from the detector’s point of view.

As the tiers go up, we move away from an idealized best-case detector and toward something that behaves more like a real spacecraft instrument: it sees background, misses some neutrons, measures energy imperfectly, and may be farther away or smaller than we would like.

So the ladder is really a progression from:

  easy to measure and easy to classify

  toward

  realistic, noisy, and operationally constrained

Important distinction: source case is not the same thing as tier.

The 50 / 75 / 95 source cases are different assumptions about the proton environment from AP9. They are not difficulty levels by themselves.

- 50%: a more typical or median proton environment
- 75%: a somewhat stronger environment
- 95%: a more intense, conservative environment

The tier tells you how hard the detector problem is.
The source case tells you which radiation environment you assumed.

That is why it makes sense to keep separate CSVs for each source case.

--------------------------------------------------
Tier 0: idealized reference case
--------------------------------------------------

This is the cleanest possible starting point.

In Tier 0, we assume:
- the detector is perfect
- there is no unrelated background
- every neutron that reaches the detector is recorded
- energy and timing are measured perfectly
- the detector is at the nominal geometry we chose
- the source intensity follows the AP9 week-averaged weighting

In plain language, Tier 0 asks:

  If the signal exists, and our detector is perfect, is there enough information in principle to tell these materials apart?

This gives the best performance we could hope for before real detector limitations get involved.

--------------------------------------------------
Tier 1: add a simple external background
--------------------------------------------------

Tier 1 keeps the same source signal, but now we add a flat background rate.

This background represents things like:
- unrelated counts from the surrounding radiation field
- detector noise
- other particles or events that enter the measurement window but are not part of the target-induced neutron signature

In plain language, Tier 1 asks:

  Can we still recognize the signal when the detector is no longer looking at a perfectly clean scene?

--------------------------------------------------
Tier 2: add self-background from the platform or nearby benign structure
--------------------------------------------------

Tier 2 goes beyond a generic flat background and adds a more mission-like nuisance source: neutrons or signal-like events associated with nearby benign material, such as aluminum structure.

This matters because in a real spacecraft setting, the detector is not floating in empty space looking only at the suspicious object. It is attached to a platform, near other mass, shielding, structure, electronics, and support hardware.

So Tier 2 asks:

  Can we still separate the suspicious payload from ordinary spacecraft material that also produces or scatters signal-like events?

--------------------------------------------------
Tier 3: make the detector behave like real hardware
--------------------------------------------------

Tier 3 is where the dataset starts to look much more like what a real instrument would actually report.

Here we introduce detector imperfections such as:
- efficiency less than 100%: the detector misses some neutrons
- energy threshold: very small signals are not recorded
- energy smearing: measured energy is not exact
- timing smearing: measured arrival times are not exact
- coincidence timing constraints: the detector logic only treats certain combinations of events as related

In plain language, Tier 3 asks:

  What would the data look like after it has passed through an actual detector rather than a perfect observer?

--------------------------------------------------
Tier 4: make the geometry less favorable
--------------------------------------------------

Tier 4 changes the measurement geometry rather than mainly changing the detector electronics.

Tier 4A: increase the detector standoff distance

The detector is farther from the source. That means fewer neutrons intersect the detector, because the detector subtends a smaller solid angle from the source’s point of view.

  What happens if we cannot get as close as we want?

Tier 4B: shrink the detector area

The detector is the same distance away, but now its collection area is smaller. That means fewer neutrons are intercepted simply because the detector covers less area.

  What happens if our payload has to be smaller, lighter, or cheaper than the ideal case?

Tier 4C: increase distance and shrink the detector

This combines both penalties:
- the detector is farther away
- the detector is smaller

  What happens if both mission operations and spacecraft design work against us at the same time?

--------------------------------------------------
Tier 5: operational flux conditions
--------------------------------------------------

Tier 5 changes the source environment itself.

Instead of just using the week-averaged AP9 spectrum, Tier 5 uses more mission-like operational periods, where the trapped proton flux is sometimes high and sometimes low.

Tier 5A: high-flux interval

This represents the favorable part of the orbit, where the high-energy proton flux is elevated. That means more source-inducing protons hit the payload, which means more neutron-producing interactions and better counting statistics.

  What does the detector see during the best part of the orbit, when nature helps us?

Tier 5B: low-flux interval

This represents the less favorable part of the orbit, where the proton flux above the relevant threshold is much lower. That means fewer induced neutrons and weaker statistics in each 10-second window.

  What does the detector see during the hard part of the orbit, when the signal source is weak?

One nuance: Tier 5A is not necessarily harder than Tier 4. Tier 5A is better interpreted as a realistic best-case orbital interval, while Tier 5B is the realistic worst-case orbital interval.

--------------------------------------------------
2. How the output filename communicates the change made
--------------------------------------------------

The naming scheme is meant to encode the main change introduced in that dataset, so you can tell what physical assumption was altered without opening the CSV.

General pattern:

  tierX_description_ap9avg_scYY.csv

or for flux-regime cases:

  tier5a_highgt60_1e4_scYY.csv

The key tokens are:

- tier0, tier1, tier2, tier3, tier4a, tier4b, tier4c, tier5a, tier5b
  Which rung of the realism ladder the dataset belongs to.

- sc50, sc75, sc95
  Which AP9 source case was used.
  sc50 = 50% confidence case
  sc75 = 75% confidence case
  sc95 = 95% confidence case

- ap9avg
  Means the source weighting uses the AP9 week-averaged spectrum.
  In other words, this is not a special high-flux or low-flux orbital interval; it is the time-averaged proton environment.

- ideal
  Means the detector was treated as ideal: no background, no inefficiency, no smearing, no threshold penalty beyond the baseline settings.

- flatbg2hz
  Means a flat external background of 2 counts per second was added.
  More generally, flatbgXhz would mean a flat background rate of X Hz.

- selfbg010
  Means self-background was included with a scale factor of 0.10.
  The shorthand 010 is meant to represent 0.10.

- resp035
  Means the detector response efficiency was set to 0.35.
  In the example commands, this comes from --eff 0.35.
  So resp035 is best read as response/efficiency = 35%.

- thr05
  Means the neutron-energy threshold was set to 0.5 MeV.
  In the example commands, this comes from --Eth-MeV 0.5.

- smear
  Means energy and/or timing smearing was turned on.
  In the example commands, this corresponded to values like:
    --sigmaEfrac 0.10
    --sigmaT-ns 5.0
  The filename token itself does not store both exact smearing numbers; it just flags that the detector is no longer ideal.
  The exact values are preserved in the manifest or debug output.

- standoff5m
  Means the detector plane was placed 5 meters from the source instead of the nominal 2 meters.
  This is the geometry-hardening case where the detector is farther away.

- panel0p5m
  Means the detector panel dimensions were reduced to about 0.5 m x 0.5 m.
  The p is being used as a decimal point, so 0p5 means 0.5.

- highgt60_1e4
  Means the dataset uses a high-flux regime in which the integral proton flux above 60 MeV was rescaled to about 1e4 protons / cm^2 / s.
  Read this as:
    high = favorable orbital interval
    gt60 = flux above 60 MeV
    1e4 = target integral flux level above 60 MeV

- lowgt60_1e2
  Means the dataset uses a low-flux regime in which the integral proton flux above 60 MeV was rescaled to about 1e2 protons / cm^2 / s.
  Read this as:
    low = unfavorable orbital interval
    gt60 = flux above 60 MeV
    1e2 = target integral flux level above 60 MeV

--------------------------------------------------
Examples
--------------------------------------------------

1. tier0_ideal_ap9avg_sc50.csv

Read as:
- Tier 0 dataset
- ideal detector assumptions
- AP9 week-averaged source spectrum
- 50% source case

Meaning:
This is the easiest, cleanest reference dataset for the median-like AP9 environment.

2. tier1_flatbg2hz_ap9avg_sc75.csv

Read as:
- Tier 1 dataset
- 2 Hz flat external background added
- AP9 week-averaged source spectrum
- 75% source case

Meaning:
This keeps the average AP9 source but adds a simple noise floor.

3. tier2_flatbg2hz_selfbg010_ap9avg_sc95.csv

Read as:
- Tier 2 dataset
- 2 Hz flat external background
- self-background included at scale 0.10
- AP9 week-averaged source spectrum
- 95% source case

Meaning:
This adds both generic noise and a benign-material nuisance source under the most intense AP9 case.

4. tier3_resp035_thr05_smear_ap9avg_sc50.csv

Read as:
- Tier 3 dataset
- detector efficiency = 0.35
- energy threshold = 0.5 MeV
- detector smearing enabled
- AP9 week-averaged spectrum
- 50% source case

Meaning:
This is the first clearly non-ideal detector dataset under the 50% AP9 source case.

5. tier4a_standoff5m_ap9avg_sc75.csv

Read as:
- Tier 4A dataset
- detector moved to 5 m standoff
- AP9 week-averaged spectrum
- 75% source case

Meaning:
This isolates the effect of being farther from the target.

6. tier4b_panel0p5m_ap9avg_sc75.csv

Read as:
- Tier 4B dataset
- detector panel shrunk to 0.5 m scale
- AP9 week-averaged spectrum
- 75% source case

Meaning:
This isolates the effect of a smaller collection area.

7. tier4c_standoff5m_panel0p5m_ap9avg_sc95.csv

Read as:
- Tier 4C dataset
- detector at 5 m standoff
- detector panel reduced to 0.5 m scale
- 95% source case

Meaning:
This is the combined harder-geometry case in the strongest AP9 environment.

8. tier5a_highgt60_1e4_sc50.csv

Read as:
- Tier 5A dataset
- high-flux orbital regime
- flux above 60 MeV rescaled to about 1e4 protons / cm^2 / s
- 50% source case

Meaning:
This represents a realistic favorable measurement interval within the orbit.

9. tier5b_lowgt60_1e2_sc50.csv

Read as:
- Tier 5B dataset
- low-flux orbital regime
- flux above 60 MeV rescaled to about 1e2 protons / cm^2 / s
- 50% source case

Meaning:
This represents a realistic unfavorable measurement interval within the orbit.

--------------------------------------------------
Short summary of the naming logic
--------------------------------------------------

The filename is supposed to answer four questions at a glance:

1. Which tier is this?
2. What was the main change from the easier case?
3. Is this AP9 week-average or a special orbital flux regime?
4. Which AP9 source case was used?

So, for example, a name like:

  tier3_resp035_thr05_smear_ap9avg_sc75.csv

means:

  Tier 3,
  detector made non-ideal,
  still using week-averaged AP9,
  under the 75% source case.

And a name like:

  tier5a_highgt60_1e4_sc95.csv

means:

  Tier 5A,
  high-flux orbital interval,
  defined by >60 MeV integral flux around 1e4,
  under the 95% source case.

