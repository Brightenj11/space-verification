"""Shared font sizes so every figure matches the pitch/energy heatmap. `import plot_style` before plotting."""
import matplotlib.pyplot as plt

FS = 12  # ticks, legend, annotations; titles and axis labels are FS + 4

plt.rcParams.update({
    "font.size": FS,
    "axes.titlesize": FS + 4,
    "axes.labelsize": FS + 4,
    "xtick.labelsize": FS,
    "ytick.labelsize": FS,
    "legend.fontsize": FS,
    "legend.title_fontsize": FS,
})
