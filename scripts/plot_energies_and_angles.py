import glob
import re
import matplotlib.pyplot as plt
import pandas as pd

""" 
Makes files like angle_flux_coarse.png and angle_flux.png, 
which show the differential fluxes at multiple energies and angles from AP9 
over time. Can specify energies sand angles to plot. 
"""


def parse_header(filepath):
    """Parses header lines from AP9/PLASMA text files to find column names and pitch angle."""
    angle = None
    headers = []

    with open(filepath, "r") as f:
        for line in f:
            if line.startswith("#"):
                # Extract flux direction/angle (e.g., '# flux dir: 90')
                if "flux dir:" in line:
                    angle_match = re.search(r"flux dir:\s*([\d\.]+)", line)
                    if angle_match:
                        angle = angle_match.group(1)
                # Extract header names line: `# Time (min) 'name1' 'name2' ...`
                if "Time (min)" in line:
                    headers = ["Time (min)"] + re.findall(r"'([^']*)'", line)
            else:
                break  # Reached data rows

    return angle, headers


def plot_multi_angle_flux(
    file_pattern="*_Plot_*.txt",
    target_energies=None,
    target_angles=None,
    xlim=None,
    auto_zoom=False,
    zoom_window=100,
    ymin=1e-2,
):
    """Reads multiple angle data files matching file_pattern and plots specified energy columns.

    If auto_zoom is True and xlim isn't given, zooms to +/- zoom_window minutes around the
    time where every plotted series has its highest simultaneous flux (i.e. all target
    energies/angles are "on" together), rather than just the single tallest peak.
    """
    files = glob.glob(file_pattern)

    if not files:
        print(f"No files matched pattern: {file_pattern}")
        return

    # Visual differentiation configurations
    colors = [
        "#ff7f0e",
        "#2ca02c",
        "#1f77b4",
        "#d62728",
        "#9467bd",
        "#8c564b",
    ]  # Palette per angle
    linestyles = [
        "-",
        "--",
        "-.",
        ":",
        (0, (3, 1, 1, 1)),
    ]  # Line styles per energy

    # First pass: load and filter every matching file once, so we can find a
    # shared peak across all of them before drawing anything.
    loaded = []
    for file_idx, filepath in enumerate(sorted(files)):
        angle, headers = parse_header(filepath)

        # Filter files if specific angles requested (e.g. ['0', '90'])
        if target_angles and angle not in target_angles:
            continue

        angle_label = f"{angle}°" if angle else f"File {file_idx+1}"

        # Color by position in target_angles (falls back to file order if
        # target_angles wasn't given).
        angle_idx = target_angles.index(angle) if target_angles else file_idx
        angle_color = colors[angle_idx % len(colors)]

        # Read numerical CSV data starting after header comments
        df = pd.read_csv(filepath, comment="#", header=None)

        if headers and len(headers) == df.shape[1]:
            df.columns = headers
        else:
            # Fallback default naming if headers line isn't parsed
            df.columns = ["Time (min)"] + [
                f"Column_{i}" for i in range(1, df.shape[1])
            ]

        time_col = df.columns[0]
        flux_cols = df.columns[1:]

        # Filter columns if specific energies requested (e.g. ['10.00 MeV', '100.00 MeV'])
        if target_energies:
            flux_cols = [
                c for c in flux_cols if any(e in c for e in target_energies)
            ]

        loaded.append((df, time_col, flux_cols, angle_label, angle_color))

    if auto_zoom and xlim is None:
        # ponytail: assumes every file shares the same Time (min) grid/row index,
        # true for this AP9 export format. Add interpolation if that ever changes.
        all_flux = pd.concat(
            [df[c] for df, _, flux_cols, _, _ in loaded for c in flux_cols], axis=1
        )
        if not all_flux.empty:
            # Time where the *weakest* of the selected series is strongest,
            # i.e. all target energies/angles have simultaneous activity there.
            peak_idx = all_flux.min(axis=1).idxmax()
            peak_time = loaded[0][0][loaded[0][1]].iloc[peak_idx]
            xlim = (peak_time - zoom_window, peak_time + zoom_window)

    fig, ax = plt.subplots(figsize=(14, 6))

    for df, time_col, flux_cols, angle_label, angle_color in loaded:
        for idx, col_name in enumerate(flux_cols):
            # Style by position in target_energies (falls back to column
            # order if target_energies wasn't given).
            if target_energies:
                energy_idx = next(
                    i for i, e in enumerate(target_energies) if e in col_name
                )
            else:
                energy_idx = idx
            ls = linestyles[energy_idx % len(linestyles)]

            # Shorten column label for cleaner legend
            energy_label = (
                col_name.replace("Proton Differential Flux at ", "")
                .replace(" Differential Flux at ", "")
                .strip("'\"")
            )

            label = f"{angle_label} - {energy_label}"

            ax.plot(
                df[time_col],
                df[col_name],
                label=label,
                color=angle_color,
                linestyle=ls,
                linewidth=1.5,
            )

    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Differential Flux (#/cm$^2$/MeV/sec)")
    ax.set_yscale("log")  # Log scale useful for flux profiles
    ax.set_ylim(bottom=ymin)
    if xlim:
        ax.set_xlim(*xlim)
    ax.grid(True, which="both", linestyle=":", alpha=0.6)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", frameon=True)

    plt.tight_layout()
    plt.show()


plot_multi_angle_flux("*.txt", target_energies=["100", "10"], target_angles=["70", "90"])



plot_multi_angle_flux(
    "*.txt",
    target_energies=["100.00 MeV", "300.00 MeV"],
    target_angles=["70", "90"],
    auto_zoom=True,
    ymin=1e-3
)

""" 
plot_multi_angle_flux(
    "*.txt",
    target_energies=["100.00 MeV", "300.00 MeV"],
    target_angles=["70", "90"],
    xlim=(750, 850),
)
""" 