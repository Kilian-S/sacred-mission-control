"""City map loading: geojson -> plotting-ready structures + the game graph.

Reads the geojson directly (no sacred import needed) but builds the SAME
nx.Graph the sacred envs build (edge attr w = length/100, min 1.0, string node
ids), so live oracle solves here match the project's own numbers exactly.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from .paths import MAPS_DIR

# Known cities and their file layouts; anything else on disk is auto-detected.
_KNOWN_FILES = {
    "kaliningrad": ("kaliningrad_simplified_30m/kaliningrad_nodes.geojson",
                    "kaliningrad_simplified_30m/kaliningrad_edges.geojson"),
    "gdansk": ("gdansk/nodes.geojson", "gdansk/edges.geojson"),
    "east_london": ("east_london/nodes.geojson", "east_london/edges.geojson"),
    "istanbul": ("istanbul/nodes.geojson", "istanbul/edges.geojson"),
    "kyiv": ("kyiv/nodes.geojson", "kyiv/edges.geojson"),
    "kaliningrad_original": ("kaliningrad_original/kaliningrad_nodes.geojson",
                             "kaliningrad_original/kaliningrad_edges.geojson"),
}

# Cities registered in sacred's CITY_PATHS (train_generalist.py): banked results exist.
REGISTERED_CITIES = ("kaliningrad", "gdansk", "east_london", "istanbul")

CITY_LABELS = {
    "kaliningrad": "Kaliningrad (the training graph, 290 nodes)",
    "gdansk": "Gdansk (gen16 held-out city, 356 nodes)",
    "east_london": "East London (564 nodes)",
    "istanbul": "Istanbul (1266 nodes)",
    "kyiv": "Kyiv (6083 nodes; whole-city zero-shot row banked in gen16)",
    "kaliningrad_original": "Kaliningrad original (A2 held-out graph, 624 nodes)",
}


@dataclass
class CityMap:
    city: str
    nodes: dict[str, tuple[float, float]]          # id -> (lon, lat)
    edges: list[tuple[str, str, float]]            # (u, v, length_m)
    edge_geometry: dict[tuple[str, str], list[tuple[float, float]]] = field(default_factory=dict)

    def graph(self) -> nx.Graph:
        """The game graph, byte-compatible with sacred's env construction."""
        G = nx.Graph()
        for u, v, length_m in self.edges:
            w = max(1.0, round(length_m / 100.0, 1))
            G.add_edge(u, v, w=w)
        return G

    def projected(self) -> dict[str, tuple[float, float]]:
        """Equirectangular projection to metres-ish local coordinates, y-down."""
        if not self.nodes:
            return {}
        lats = [lat for _, lat in self.nodes.values()]
        lons = [lon for lon, _ in self.nodes.values()]
        lat0 = sum(lats) / len(lats)
        lon0 = sum(lons) / len(lons)
        kx = 111_320.0 * math.cos(math.radians(lat0))
        ky = 110_540.0
        return {
            nid: ((lon - lon0) * kx, -(lat - lat0) * ky)
            for nid, (lon, lat) in self.nodes.items()
        }


def available_cities() -> list[str]:
    """Known cities present on disk, then any unknown map directories."""
    cities = []
    for name, (nfile, _) in _KNOWN_FILES.items():
        if (MAPS_DIR / nfile).is_file():
            cities.append(name)
    if MAPS_DIR.is_dir():
        for d in sorted(MAPS_DIR.iterdir()):
            if not d.is_dir() or d.name in {"kaliningrad_simplified_30m", "kaliningrad_original",
                                            "kaliningrad_original_curvy"}:
                continue
            if d.name in cities:
                continue
            if (d / "nodes.geojson").is_file() and (d / "edges.geojson").is_file():
                cities.append(d.name)
                _KNOWN_FILES.setdefault(d.name, (f"{d.name}/nodes.geojson", f"{d.name}/edges.geojson"))
    return cities


def load_city(city: str) -> CityMap:
    nfile, efile = _KNOWN_FILES[city]
    nodes_raw = json.loads((MAPS_DIR / nfile).read_text(encoding="utf-8"))
    edges_raw = json.loads((MAPS_DIR / efile).read_text(encoding="utf-8"))

    nodes: dict[str, tuple[float, float]] = {}
    for feat in nodes_raw.get("features", []):
        props = feat.get("properties", {})
        nid = str(props.get("osmid"))
        coords = feat.get("geometry", {}).get("coordinates", None)
        if nid and coords and len(coords) >= 2:
            nodes[nid] = (float(coords[0]), float(coords[1]))

    # sacred's loader iterates every feature and nx.Graph lets the LAST duplicate
    # (u,v)/(v,u) feature win; replicate that exactly so live LP values match.
    lengths: dict[tuple[str, str], float] = {}
    geometry: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for feat in edges_raw.get("features", []):
        props = feat.get("properties", {})
        u, v = str(props.get("u")), str(props.get("v"))
        if u not in nodes or v not in nodes:
            continue
        key = (u, v) if u <= v else (v, u)
        length = props.get("length")
        if length is None:
            length = 100.0  # sacred's loader default for maps without length
        lengths[key] = float(length)
        coords = feat.get("geometry", {}).get("coordinates", [])
        if coords:
            geometry[key] = [(float(c[0]), float(c[1])) for c in coords]

    edges = [(u, v, l) for (u, v), l in lengths.items()]
    return CityMap(city=city, nodes=nodes, edges=edges, edge_geometry=geometry)
