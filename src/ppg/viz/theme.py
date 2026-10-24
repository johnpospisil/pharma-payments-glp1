"""One visual system for every published figure (P21): light and dark, colour-blind safe.

Tokens follow the dataviz reference palette. The six brand slots are validated in this order with
scripts/validate_palette (adjacent pairs; light: CVD dE >= 9.1, normal-vision >= 19.6; dark: CVD
>= 8.4, normal-vision >= 19.3, all >= 3:1). In light mode three slots (aqua, yellow, magenta) sit
under 3:1 contrast, so their marks are always direct-labelled and every chart has its data table
in report/qa. Colour follows the brand everywhere; non-brand series (statins, controls, single
series) use neutral ink, never a seventh hue.

    with use("dark") as t:
        fig = draw(t)
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402

BRANDS = ["Ozempic", "Trulicity", "Mounjaro", "Victoza", "Rybelsus", "Bydureon"]


@dataclass(frozen=True)
class Theme:
    mode: str
    surface: str
    ink: str
    ink2: str
    muted: str
    grid: str
    axis: str
    slots: tuple
    seq: tuple  # sequential blue, low -> high magnitude (reversed in dark: low recedes)
    masked: str  # cells withheld for disclosure
    other: str = field(default="#a8a69c")

    def brand(self, name: str) -> str:
        return self.slots[BRANDS.index(name)] if name in BRANDS else self.other

    def tint(self, color: str, amount: float = 0.45) -> str:
        """`color` mixed toward the surface: a lighter step of the same hue (stack levels)."""
        c, s = to_rgb(color), to_rgb(self.surface)
        return matplotlib.colors.to_hex([s[i] + amount * (c[i] - s[i]) for i in range(3)])

    def cmap(self) -> LinearSegmentedColormap:
        return LinearSegmentedColormap.from_list(f"seq_{self.mode}", self.seq)


SEQ = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
LIGHT = Theme(
    mode="light", surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
    grid="#e1e0d9", axis="#c3c2b7",
    slots=("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"),
    seq=SEQ, masked="#ecebe6", other="#a8a69c",
)  # fmt: skip
DARK = Theme(
    mode="dark", surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781",
    grid="#2c2c2a", axis="#383835",
    slots=("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"),
    seq=SEQ[::-1], masked="#2c2c2a", other="#6f6d66",
)  # fmt: skip
THEMES = {"light": LIGHT, "dark": DARK}
FONTS = ["Arial", "Helvetica Neue", "DejaVu Sans"]


@contextlib.contextmanager
def use(mode: str, scale: float = 1.0):
    t = THEMES[mode]
    rc = {
        "font.family": "sans-serif", "font.sans-serif": FONTS, "font.size": 9.5 * scale,
        "axes.titlesize": 10 * scale, "axes.labelsize": 9 * scale,
        "xtick.labelsize": 8.5 * scale, "ytick.labelsize": 8.5 * scale,
        "legend.fontsize": 8.5 * scale, "text.color": t.ink, "axes.labelcolor": t.ink2,
        "xtick.color": t.ink2, "ytick.color": t.ink2, "axes.edgecolor": t.axis,
        "axes.titlecolor": t.ink, "figure.facecolor": t.surface, "axes.facecolor": t.surface,
        "savefig.facecolor": t.surface, "axes.linewidth": 0.8, "lines.linewidth": 2,
        "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 5,
        "ytick.major.pad": 5, "legend.frameon": False, "svg.fonttype": "none",
        "svg.hashsalt": "ppg", "text.parse_math": False,  # "$" is currency, not mathtext
    }  # fmt: skip
    with plt.rc_context(rc):
        yield t


def axes(ax, t: Theme, grid: str = "y") -> None:
    """Recessive chrome: hairline solid grid one step off the surface, baseline only."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(grid != "y")
    ax.spines["bottom"].set_color(t.axis)
    ax.spines["left"].set_color(t.axis)
    if grid:
        ax.grid(axis=grid, color=t.grid, lw=0.8, zorder=0)
        ax.set_axisbelow(True)


def heading(fig, t: Theme, title: str, subtitle: str = "", top: float = 0.97) -> None:
    fig.text(0.012, top, title, fontsize=plt.rcParams["font.size"] * 1.32, color=t.ink,
             fontweight="bold", va="top")  # fmt: skip
    if subtitle:
        fig.text(0.012, top - 0.055 * (5.6 / fig.get_figheight()), subtitle, color=t.ink2,
                 fontsize=plt.rcParams["font.size"] * 1.02, va="top")  # fmt: skip


def footnote(fig, t: Theme, text: str, width: int | None = None) -> float:
    """Muted note at the bottom-left; returns its height as a fraction of the figure."""
    import textwrap

    size = plt.rcParams["font.size"] * 0.78
    width = width or int(fig.get_figwidth() * 72 / (size * 0.52))
    body = "\n".join(textwrap.fill(p, width) for p in text.split("\n"))
    fig.text(0.012, 0.014, body, fontsize=size, color=t.muted, va="bottom", linespacing=1.35)
    return 0.014 + (body.count("\n") + 1) * size * 1.35 / 72 / fig.get_figheight()


def dot(ax, x, y, color, t: Theme, size: float = 30, hollow: bool = False, z: int = 4):
    """Marker >= 8px with a 2px surface ring (legible where it crosses a line)."""
    return ax.scatter(x, y, s=size, color=t.surface if hollow else color, ec=color if hollow
                      else t.surface, lw=1.8 if hollow else 1.6, zorder=z)  # fmt: skip
