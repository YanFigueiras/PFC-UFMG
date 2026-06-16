import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from drbecm_coro.algorithm import (
    AlgorithmSnapshot,
    BORDER_CLEARANCE,
    COMMUNICATION_RANGE,
    CONNECTIVITY_MARGIN,
    FREE,
    GRID_RESOLUTION,
    MIN_ROBOT_DISTANCE,
    ROBOT_NAMES,
    SENSING_RANGE,
    WORLD_X_MAX,
    WORLD_X_MIN,
    WORLD_Y_MAX,
    WORLD_Y_MIN,
)


# =============================================================================
# Global metrics configuration
# =============================================================================

METRICS_CSV_PATH = "/CrazySim/pfc_ws/cache/drbecm_metrics.csv"


@dataclass
class MetricsSample:
    step: int
    elapsed_sec: float
    coverage_percent: float
    covered_cells: int
    total_cells: int
    new_cells: int
    redundant_observations: int
    total_distance_m: float
    min_robot_distance_m: float
    min_border_distance_m: float
    connectivity_ok: bool
    collision_ok: bool
    border_ok: bool


class MetricsTracker:
    """Runtime metrics inspired by metrics_Flocking_inspired.py.

    This class has no ROS dependency. It receives AlgorithmSnapshot objects and
    writes one CSV row per control step.
    """

    def __init__(self, csv_path: str = METRICS_CSV_PATH) -> None:
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.step = 0
        self.start_time: Optional[float] = None
        self.previous_positions: Optional[List[np.ndarray]] = None
        self.previous_map: Optional[np.ndarray] = None
        self.total_distance_m = 0.0
        self.redundant_observations = 0
        self._write_header()

    def update(self, snapshot: AlgorithmSnapshot, now_sec: float) -> MetricsSample:
        if self.start_time is None:
            self.start_time = now_sec
        elapsed_sec = now_sec - self.start_time

        if self.previous_positions is not None:
            for previous, current in zip(self.previous_positions, snapshot.positions):
                self.total_distance_m += float(np.linalg.norm(current - previous))

        new_cells = 0
        if self.previous_map is not None:
            newly_free = (snapshot.global_map == FREE) & (self.previous_map != FREE)
            new_cells = int(np.count_nonzero(newly_free))
            self.redundant_observations += self._count_redundant_observations(snapshot)

        min_robot_distance = self._min_robot_distance(snapshot.positions)
        min_border_distance = self._min_border_distance(snapshot.positions)
        connectivity_ok = self._connectivity_ok(snapshot)
        collision_ok = min_robot_distance >= MIN_ROBOT_DISTANCE
        border_ok = min_border_distance >= BORDER_CLEARANCE

        sample = MetricsSample(
            step=self.step,
            elapsed_sec=elapsed_sec,
            coverage_percent=snapshot.coverage_percent,
            covered_cells=snapshot.covered_cells,
            total_cells=snapshot.total_cells,
            new_cells=new_cells,
            redundant_observations=self.redundant_observations,
            total_distance_m=self.total_distance_m,
            min_robot_distance_m=min_robot_distance,
            min_border_distance_m=min_border_distance,
            connectivity_ok=connectivity_ok,
            collision_ok=collision_ok,
            border_ok=border_ok,
        )

        self._append_csv(sample)
        self.previous_positions = [p.copy() for p in snapshot.positions]
        self.previous_map = snapshot.global_map.copy()
        self.step += 1
        return sample

    def to_json(self, sample: MetricsSample) -> str:
        return json.dumps(asdict(sample), sort_keys=True)

    def _write_header(self) -> None:
        with self.csv_path.open("w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(MetricsSample.__annotations__.keys()))
            writer.writeheader()

    def _append_csv(self, sample: MetricsSample) -> None:
        with self.csv_path.open("a", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(MetricsSample.__annotations__.keys()))
            writer.writerow(asdict(sample))

    def _count_redundant_observations(self, snapshot: AlgorithmSnapshot) -> int:
        if self.previous_map is None:
            return 0

        redundant = 0
        radius_cells = int(math.ceil(SENSING_RANGE / GRID_RESOLUTION))
        height, width = snapshot.global_map.shape

        for position in snapshot.positions:
            gx = int((float(position[0]) - WORLD_X_MIN) / GRID_RESOLUTION)
            gy = int((float(position[1]) - WORLD_Y_MIN) / GRID_RESOLUTION)
            for yy in range(max(0, gy - radius_cells), min(height, gy + radius_cells + 1)):
                for xx in range(max(0, gx - radius_cells), min(width, gx + radius_cells + 1)):
                    cell_position = np.array([
                        WORLD_X_MIN + (xx + 0.5) * GRID_RESOLUTION,
                        WORLD_Y_MIN + (yy + 0.5) * GRID_RESOLUTION,
                    ])
                    if np.linalg.norm(cell_position - position) <= SENSING_RANGE:
                        if self.previous_map[yy, xx] == FREE:
                            redundant += 1
        return redundant

    def _connectivity_ok(self, snapshot: AlgorithmSnapshot) -> bool:
        connected_supporters = self._connected_supporters(snapshot)
        safe_range = CONNECTIVITY_MARGIN * COMMUNICATION_RANGE

        for idx, role in enumerate(snapshot.roles):
            if role == "supporter":
                if idx not in connected_supporters:
                    return False
                continue

            if np.linalg.norm(snapshot.positions[idx] - snapshot.base) <= safe_range:
                continue
            if any(np.linalg.norm(snapshot.positions[idx] - snapshot.positions[j]) <= safe_range for j in connected_supporters):
                continue
            return False
        return True

    def _connected_supporters(self, snapshot: AlgorithmSnapshot) -> set:
        safe_range = CONNECTIVITY_MARGIN * COMMUNICATION_RANGE
        connected = {
            i for i, role in enumerate(snapshot.roles)
            if role == "supporter" and np.linalg.norm(snapshot.positions[i] - snapshot.base) <= safe_range
        }
        changed = True
        while changed:
            changed = False
            for i, role in enumerate(snapshot.roles):
                if role != "supporter" or i in connected:
                    continue
                if any(np.linalg.norm(snapshot.positions[i] - snapshot.positions[j]) <= safe_range for j in connected):
                    connected.add(i)
                    changed = True
        return connected

    def _min_robot_distance(self, positions: List[np.ndarray]) -> float:
        result = float("inf")
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                result = min(result, float(np.linalg.norm(positions[i] - positions[j])))
        return 0.0 if result == float("inf") else result

    def _min_border_distance(self, positions: List[np.ndarray]) -> float:
        result = float("inf")
        for position in positions:
            result = min(
                result,
                float(position[0] - WORLD_X_MIN),
                float(WORLD_X_MAX - position[0]),
                float(position[1] - WORLD_Y_MIN),
                float(WORLD_Y_MAX - position[1]),
            )
        return result
