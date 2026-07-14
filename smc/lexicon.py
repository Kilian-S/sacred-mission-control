"""The single source of every human-facing string (REDESIGN.md §1).

Rules enforced here and by tests/test_lexicon.py:
- one metric phrase everywhere: "chance the mission fails", conditioned as
  "against an enemy who has learned your habits";
- newspaper words only in visible strings; codes, metric names and generation
  numbers live in fine print;
- sentence case (product and place names keep their own casing).
"""

from __future__ import annotations

# ---------------------------------------------------------------- the metric

CONDITION = "against an enemy who has learned your habits"


def metric_phrase(objective: str = "mission", threshold_m: int = 1) -> str:
    if objective == "linear":
        return "average share of convoys lost"
    if objective == "threshold":
        return f"chance of losing {threshold_m} or more convoys"
    return "chance the mission fails"


def pct(x: float, decimals: int = 0) -> str:
    """0.206 -> '21%' (human surfaces use percentages, never 0.xxx)."""
    return f"{x * 100:.{decimals}f}%"


GOALPOST_LEFT = "the proven optimum"
GOALPOST_RIGHT = "the best any predictable plan can do"

# ------------------------------------------------------------- strategy names
# arm key -> (name, one-line description). Fine print may add the formal term.

STRATEGIES: dict[str, tuple[str, str]] = {
    "shortest": ("Always the fastest road",
                 "predictable, and predictability is what gets you ambushed"),
    "shortest_path": ("Always the fastest road",
                      "predictable, and predictability is what gets you ambushed"),
    "uniform": ("Pick a road at random",
                "unpredictable but wasteful; ignores which roads are dangerous"),
    "uniform_stack": ("Pick a road at random",
                      "unpredictable but wasteful; ignores which roads are dangerous"),
    "independent_uniform": ("Every convoy rolls its own dice",
                            "no coordination between the convoys"),
    "cost_mixture": ("Random, but favouring fast roads",
                     "still a habit the enemy can learn"),
    "equilibrium": ("The proven-optimal mix",
                    "the mathematically best possible blend of routes"),
    "alns": ("The professional planner",
             "the strongest industry method; always produces the same plan"),
    "alns_forced_stack": ("The professional planner, forced to convoy together",
                          "a fairness check"),
    "forced_stack": ("The professional planner, forced to convoy together",
                     "a fairness check"),
    "sacred": ("SACRED", "the AI trained against an adversary"),
    "vanilla": ("AI trained with no enemy",
                "learns fast routes, not safe ones"),
    "distill": ("AI taught by copying the maths",
                "needs the answer key for every training map"),
    "retrieval": ("Copy the most similar known answer",
                  "needs the answer key for every training map"),
    "dr": ("AI trained against random attacks",
           "sees danger, but never a thinking enemy"),
    "random_init": ("An untrained AI", "fresh out of the box"),
    "human": ("You", "click a road each run"),
    "static_det": ("Always the same road", "the fixed habit"),
    "iid_eq": ("The proven mix, ignoring recent history",
               "safe but blind to the enemy's adaptation"),
    "history_aware": ("SACRED, watching its own recent pattern",
                      "avoids roads it has used lately"),
    "history_opt": ("The perfect history-aware play", "the computable optimum"),
}

ATTACKERS: dict[str, tuple[str, str]] = {
    "oracle_br": ("The enemy knows your strategy",
                  "the worst case: it commits to the single best ambush against your habits"),
    "equilibrium": ("The perfect ambusher",
                    "mixes its ambush spots optimally"),
    "pattern_of_life": ("Watches your last few runs, then strikes",
                        "positions against what you did recently"),
    "empirical_br": ("Studies your whole history, then commits",
                     "punishes any long-term habit"),
}

OBJECTIVES: dict[str, tuple[str, str]] = {
    "mission": ("Any loss means failure",
                "the headline rule: the mission fails if even one convoy is lost"),
    "threshold": ("Failure means losing two or more",
                  "a spread-out fleet can make this outcome impossible"),
    "linear": ("Count average losses",
               "risk-neutral: only the average matters"),
}


def strategy_name(key: str) -> str:
    return STRATEGIES.get(key, (key, ""))[0]


def strategy_blurb(key: str) -> str:
    return STRATEGIES.get(key, ("", ""))[1]


def attacker_name(key: str) -> str:
    return ATTACKERS.get(key, (key, ""))[0]


# ------------------------------------------------------------------ misc copy

BASE_LABEL = "Base"
DESTINATION_LABEL = "Destination"

ERA_TOOLTIP = (
    "On 9 July a project-wide bug was found and fixed. Results from before and "
    "after the fix are never compared or mixed, here or anywhere in the project."
)

RECORD_DISCLOSURE = "From the record"

LEGEND_ITEMS = [
    ("roads", "city roads"),
    ("mixture", "thicker = used more often"),
    ("glow", "where the enemy expects you"),
    ("ambush", "ambush"),
    ("base", "base"),
    ("destination", "destination"),
]

# words that must never appear in the visible lexicon strings (tested)
BANNED_IN_VISIBLE = [
    "exploitab", "TAP", "softmax", "LP ", "minimax", "equilibrium mixture (",
    "N=", "K=", "pre-fix", "post-fix", "checkpoint", "ledger:", "oracle BR",
    "best response", "det/eq", "OD", "gen1", "gen2",
]
