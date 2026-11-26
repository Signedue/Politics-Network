"""Fælles stil til alle figurer i rapporten. Læg filen i notebooks/ og skriv øverst i en figur-celle:

    import sys; sys.path.append("..")      # notebooks/<mappe>/ -> notebooks/
    from stil import *
"""
import numpy as np
import matplotlib.pyplot as plt

# ---------- Størrelse: rapportens fulde bredde ----------
CM = 1 / 2.54
BREDDE = 17.8 * CM

# ---------- Udseende ----------
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.edgecolor": "#888888", "axes.linewidth": 0.6, "axes.labelcolor": "#444444",
    "xtick.color": "#555555", "ytick.color": "#222222", "ytick.major.size": 0, "xtick.major.width": 0.6,
    "axes.grid": True, "axes.grid.axis": "x", "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "legend.handlelength": 1.0, "legend.handleheight": 0.9, "legend.columnspacing": 1.0,
    "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight", "pdf.fonttype": 42,
})

GRAA, MOERK, ROED = "#9a9a9a", "#3c4650", "#c8102e"

# ---------- Faste farver: samme parti / emne = samme farve i alle figurer ----------
PARTIER = ["S", "V", "M", "SF", "DD", "LA", "KF", "EL", "DF", "RV", "ALT"]
REGERING = {"S", "V", "M"}
PARTI_FARVE = {"S": "#C8102E", "V": "#1B3F6B", "M": "#9B7FC4", "SF": "#D65C8E", "DD": "#5F86C9", "LA": "#2BA3B4",
               "KF": "#4E7A2C", "EL": "#E07B10", "DF": "#E7B416", "RV": "#6A2C78", "ALT": "#2E8B3D"}

EMNE_FARVE = {
    "Economy and tax": "#3B6FB6", "Health and elderly care": "#E08A3C", "Climate and environment": "#4E9F6A",
    "Schools and childcare": "#C9534F", "Refugees and immigrants": "#8A6FB8", "Justice and safety": "#9C7A5B",
    "Defence and security": "#D07BAE", "Pensions and retirement": "#A0A0A0", "Government formation": "#2F2F2F",
}
EMNE_ORDEN = list(EMNE_FARVE)
# Danske kategorinavne (mærkesager) -> de engelske navne ovenfor
EMNE_EN = {
    "Økonomi og skat": "Economy and tax", "Sundhed og ældrepleje": "Health and elderly care",
    "Klima og miljø": "Climate and environment", "Skoler og børnepasning": "Schools and childcare",
    "Flygtninge og indvandrere": "Refugees and immigrants", "Retspolitik og tryghed": "Justice and safety",
    "Forsvar og sikkerhed": "Defence and security", "Pension og tilbagetrækning": "Pensions and retirement",
}


# ---------- Små hjælpere ----------
def titel(fig, fund, check, y=1.0):
    """Fed titel = fundet; grå undertitel = valideringen (null-modellen). check må gerne have flere linjer (\\n)."""
    from matplotlib.transforms import offset_copy
    linjer = check.count("\n") + 1
    fig.text(0.0, y + 0.01, check, fontsize=8, color="#555555", ha="left", va="bottom", transform=fig.transFigure,
             linespacing=1.35)
    fig.text(0.0, y + 0.01, fund, fontsize=10.5, fontweight="bold", ha="left", va="bottom",
             transform=offset_copy(fig.transFigure, fig=fig, y=linjer * 11.5 + 5, units="points"))


def panel(ax, bogstav, x=-0.02, y=1.04):
    """Fed panelbogstav (a, b, c) øverst til venstre."""
    ax.text(x, y, bogstav, transform=ax.transAxes, fontsize=10, fontweight="bold", ha="right", va="bottom")


def p_vaerdi(rigtig, null, retning="hoejere"):
    """Andel blandinger, der er mindst lige så ekstreme som de rigtige data (uge 2)."""
    null = np.asarray(null)
    ekstreme = (null >= rigtig).sum() if retning == "hoejere" else (null <= rigtig).sum()
    return (1 + ekstreme) / (1 + len(null))


def p_tekst(p):
    return f"p = {p:.3f}" if p >= 0.001 else "p < 0.001"


def gem(fig, navn):
    """Gemmer både PDF (til rapporten) og PNG."""
    fig.savefig(f"{navn}.pdf")
    fig.savefig(f"{navn}.png")
