"""The search area: a grid of cells grouped into sectors, and geometry helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def to_json(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]


class Grid:
    """A cols x rows grid of square cells, tiled into square sectors.

    Cells are indexed row-major. A set of cells is a Python int used as a
    bitset, so "merge two coverage maps" is a single `|`.
    """

    def __init__(self, cols: int = 64, rows: int = 48, sector: int = 8, cell_m: float = 20.0):
        self.cols, self.rows, self.sector, self.cell_m = cols, rows, sector, cell_m
        self.n_cells = cols * rows
        self.sx = math.ceil(cols / sector)
        self.sy = math.ceil(rows / sector)
        self.n_sectors = self.sx * self.sy
        self.width_m = cols * cell_m
        self.height_m = rows * cell_m
        self.full_mask = (1 << self.n_cells) - 1

        self.sector_cells: list[list[int]] = [[] for _ in range(self.n_sectors)]
        self.cell_sector = [0] * self.n_cells
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                s = (r // sector) * self.sx + c // sector
                self.sector_cells[s].append(i)
                self.cell_sector[i] = s

        self.sector_masks = [0] * self.n_sectors
        self.sector_centers: list[tuple[float, float]] = []
        for s, cells in enumerate(self.sector_cells):
            m = 0
            for i in cells:
                m |= 1 << i
            self.sector_masks[s] = m
            xs = [self.cell_center(i)[0] for i in cells]
            ys = [self.cell_center(i)[1] for i in cells]
            self.sector_centers.append((sum(xs) / len(xs), sum(ys) / len(ys)))

        self.sector_neighbours = []
        for s in range(self.n_sectors):
            x, y = s % self.sx, s // self.sx
            self.sector_neighbours.append([
                (y + dy) * self.sx + (x + dx)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dx or dy) and 0 <= x + dx < self.sx and 0 <= y + dy < self.sy])

        # What a drone's downward camera sees from inside cell i: the 3x3 block.
        self.footprints = [self._footprint(i) for i in range(self.n_cells)]

    def _footprint(self, i: int) -> int:
        c, r = i % self.cols, i // self.cols
        m = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cc, rr = c + dc, r + dr
                if 0 <= cc < self.cols and 0 <= rr < self.rows:
                    m |= 1 << (rr * self.cols + cc)
        return m

    def cell_at(self, x: float, y: float) -> int:
        c = min(self.cols - 1, max(0, int(x // self.cell_m)))
        r = min(self.rows - 1, max(0, int(y // self.cell_m)))
        return r * self.cols + c

    def cell_center(self, i: int) -> tuple[float, float]:
        return ((i % self.cols + 0.5) * self.cell_m, (i // self.cols + 0.5) * self.cell_m)

    def sector_done(self, covered: int, s: int) -> bool:
        m = self.sector_masks[s]
        return covered & m == m

    def to_json(self) -> dict:
        return {
            "cols": self.cols, "rows": self.rows, "sector": self.sector,
            "cell_m": self.cell_m, "width_m": self.width_m, "height_m": self.height_m,
            "sx": self.sx, "sy": self.sy,
        }
