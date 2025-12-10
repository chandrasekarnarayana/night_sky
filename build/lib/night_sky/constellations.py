"""Constellation helpers for v0.2.

This module loads constellation line definitions from
`data/constellations_lines.csv` and provides helpers to build line
segments between known stars.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict
import csv

from .data_manager import get_data_path


@dataclass
class ConstellationLine:
    name: str
    star_id_1: int
    star_id_2: int


def load_constellation_lines(path: Path | str = 'constellations_lines.csv') -> List[ConstellationLine]:
    """Load constellation line definitions from `data/<path>`.

    The CSV is expected to have columns: `constellation,star_id_1,star_id_2`.
    Raises FileNotFoundError if the CSV is missing.
    """
    p = get_data_path(path) if isinstance(path, str) else Path(path)
    if isinstance(p, Path) and not p.exists():
        raise FileNotFoundError(f"Constellation lines file not found: {p}")

    lines: List[ConstellationLine] = []
    with open(p, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                name = row.get('constellation', '').strip()
                a = int(row['star_id_1'])
                b = int(row['star_id_2'])
            except Exception:
                continue
            lines.append(ConstellationLine(name=name, star_id_1=a, star_id_2=b))
    return lines


def build_constellation_segments(stars: Dict[int, object],
                                lines: List[ConstellationLine]) -> List[Tuple[object, object]]:
    """Return line segments (star1, star2) for which both stars are present.

    `stars` should be a dict mapping star id -> Star-like object (with at least id attribute).
    """
    segments: List[Tuple[object, object]] = []
    for ln in lines:
        s1 = stars.get(ln.star_id_1)
        s2 = stars.get(ln.star_id_2)
        if s1 is not None and s2 is not None:
            segments.append((s1, s2))
    return segments

