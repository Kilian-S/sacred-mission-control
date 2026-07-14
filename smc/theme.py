"""The single source of visual truth: palette, typography, QSS, matplotlib style.

Light mode only (the app is shown to a professor; macOS dark mode must not
invert it, hence Fusion style + explicit palette). Colours follow the
colour-blind-safe reference palette validated with the dataviz six-checks
validator; categorical hues are assigned to ENTITIES (strategies, arms) in a
fixed order, never cycled.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Ink and surfaces (light mode)
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"        # chart / card surface
PAGE = "#f4f4f1"           # window plane behind cards
INK = "#0b0b0b"            # primary text
INK_SECONDARY = "#52514e"  # secondary text
INK_MUTED = "#898781"      # axis labels, captions
GRID = "#e1e0d9"           # hairline gridlines
BASELINE = "#c3c2b7"       # axis baselines, separators
BORDER = "rgba(11,11,11,0.10)"
SELECTION_BG = "#dcE9fa"   # sidebar selection wash (light blue)

# ---------------------------------------------------------------------------
# Categorical slots (fixed order; light mode values)
# ---------------------------------------------------------------------------
BLUE = "#2a78d6"
AQUA = "#1baf7a"
YELLOW = "#eda100"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"
MAGENTA = "#e87ba4"
ORANGE = "#eb6834"

CATEGORICAL = [BLUE, AQUA, YELLOW, GREEN, VIOLET, RED, MAGENTA, ORANGE]

# ---------------------------------------------------------------------------
# Entity colours: one colour per strategy/arm across the entire app.
# Colour follows the entity, never its rank (dataviz rule).
# ---------------------------------------------------------------------------
STRATEGY_COLOURS = {
    "sacred": BLUE,            # the hero
    "equilibrium": VIOLET,     # computable ground truth
    "shortest_path": RED,      # maximally exploitable default
    "vanilla": YELLOW,         # non-adversarial control
    "alns": AQUA,              # classical metaheuristic
    "alns_forced_stack": "#0e8a5f",  # darker aqua sibling
    "uniform": MAGENTA,        # uncalibrated noise reference
    "attacker": ORANGE,        # interdictor
    "random_init": INK_MUTED,  # untrained reference
    "human": GREEN,            # the player
    "generalist": BLUE,
    "history_aware": BLUE,
    "history_opt": VIOLET,
    "iid_eq": MAGENTA,
    "static_det": RED,
    # Block A controls (identity in compare panels is carried by position + label;
    # colour assignments recorded in DECISIONS.md)
    "distill": GREEN,            # labels-needed amortiser (green family = supervised)
    "retrieval": "#0e8a5f",      # labels-needed amortiser (bar charts only, never flown)
    "dr": ORANGE,                # exposure-without-pressure control
}

# Provenance accents
LIVE_ACCENT = "#0d6e57"    # "computed live" labels (deep teal-green, distinct from series)
LEDGER_GREY = INK_MUTED    # "ledger:" captions

# Vulnerability heat (sequential, one hue light->dark: warm red-browns).
VULN_RAMP = ["#fbe4dc", "#f6c3b3", "#ee9d87", "#e37860", "#d05441", "#b03a2e", "#8c2a22", "#661d18"]

# Era badges
ERA_PREFIX_BG = "#efe5d2"   # pre-fix: warm sand
ERA_PREFIX_FG = "#6b5311"
ERA_POSTFIX_BG = "#d9e9dc"  # post-fix: green tint
ERA_POSTFIX_FG = "#1d5c2e"

FONT_FAMILY = "Helvetica Neue"
MONO_FAMILY = "SF Mono, Menlo, monospace"


def build_qss() -> str:
    """Application stylesheet. Kept in one place so spacing/typography stay consistent."""
    return f"""
    QMainWindow, QDialog {{ background: {PAGE}; }}
    QWidget {{ font-family: "{FONT_FAMILY}"; font-size: 15px; color: {INK}; }}

    QTabWidget::pane {{ border: none; background: {PAGE}; }}
    QTabBar::tab {{
        background: transparent; color: {INK_SECONDARY};
        padding: 7px 18px; margin: 4px 2px 0 2px;
        border: none; border-bottom: 2px solid transparent;
        font-size: 16px;
    }}
    QTabBar::tab:selected {{ color: {INK}; border-bottom: 2px solid {BLUE}; font-weight: 600; }}
    QTabBar::tab:hover:!selected {{ color: {INK}; }}

    QListWidget, QTreeView, QListView {{
        background: {SURFACE}; border: 1px solid {GRID}; border-radius: 12px;
        outline: none; padding: 8px;
    }}
    QListWidget::item, QTreeView::item {{ padding: 8px 10px; border-radius: 8px; }}
    QListWidget::item:selected, QTreeView::item:selected {{
        background: {SELECTION_BG}; color: {INK};
    }}

    QSplitter::handle {{ background: {PAGE}; width: 6px; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {BASELINE}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {BASELINE}; border-radius: 4px; min-width: 30px; }}

    QPushButton {{
        background: transparent; border: 1px solid {GRID}; border-radius: 10px;
        padding: 8px 16px; color: {INK};
    }}
    QPushButton:hover {{ background: {SURFACE}; border-color: {BASELINE}; }}
    QPushButton:pressed {{ background: {SELECTION_BG}; }}
    QPushButton:disabled {{ color: {INK_MUTED}; border-color: {GRID}; }}
    QPushButton[accent="true"] {{
        background: {BLUE}; border: 1px solid {BLUE}; color: white; font-weight: 600;
        padding: 9px 20px;
    }}
    QPushButton[accent="true"]:hover {{ background: #1c5cab; color: white; }}
    QPushButton[quiet="true"] {{
        border: none; color: {INK_SECONDARY}; padding: 4px 8px; text-align: left;
    }}
    QPushButton[quiet="true"]:hover {{ color: {INK}; background: transparent; }}

    QComboBox {{
        background: {SURFACE}; border: 1px solid {BASELINE}; border-radius: 10px;
        padding: 6px 12px;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE}; border: 1px solid {GRID};
        selection-background-color: {SELECTION_BG}; selection-color: {INK};
    }}
    QSlider::groove:horizontal {{ height: 4px; background: {GRID}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
        background: {BLUE}; border: 2px solid {SURFACE};
    }}
    QLineEdit {{
        background: {SURFACE}; border: 1px solid {BASELINE}; border-radius: 7px;
        padding: 5px 10px; selection-background-color: {SELECTION_BG};
    }}
    QToolTip {{
        background: {INK}; color: {SURFACE}; border: none; padding: 5px 8px;
        font-size: 14px;
    }}
    QLabel[caption="true"] {{ color: {INK_MUTED}; font-size: 12px; }}
    QLabel[fineprint="true"] {{ color: {INK_MUTED}; font-size: 12px; }}
    QLabel[h1="true"] {{ font-size: 30px; font-weight: 700; letter-spacing: -0.3px; }}
    QLabel[h2="true"] {{ font-size: 20px; font-weight: 650; }}
    QLabel[h3="true"] {{ font-size: 15px; font-weight: 650; }}
    QLabel[hero="true"] {{ font-size: 40px; font-weight: 700; letter-spacing: -0.5px; }}
    QFrame[card="true"] {{
        background: {SURFACE}; border: 1px solid #eceae4; border-radius: 12px;
    }}
    QStatusBar {{ background: {PAGE}; color: {INK_MUTED}; }}
    QToolButton[disclosure="true"] {{
        border: none; color: {INK_MUTED}; font-size: 12px; padding: 2px 4px;
        text-align: left;
    }}
    QToolButton[disclosure="true"]:hover {{ color: {INK_SECONDARY}; }}
    """


def apply_matplotlib_style() -> None:
    """Publication-quality light style for every embedded figure and export."""
    import matplotlib as mpl

    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 200,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial"],
        "font.size": 13,
        "text.color": INK,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titlesize": 14,
        "axes.titleweight": "semibold",
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "legend.frameon": False,
        "legend.fontsize": 12,
        "lines.linewidth": 2.0,
        "axes.prop_cycle": mpl.cycler(color=CATEGORICAL),
    })
