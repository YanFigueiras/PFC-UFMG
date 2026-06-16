from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math

import numpy as np


# =============================================================================
# Global configuration: coro.world and DRBECM constants
# =============================================================================

ROBOT_NAMES = ["cf_1", "cf_2", "cf_3", "cf_4"]
ROBOT_LABELS = ["cf0", "cf1", "cf2", "cf3"]

# The article has a fixed base station. In this setup it is placed at the cf0
# start point, near the left side of coro.world.
BASE_POSITION = np.array([-1.5, 1.2], dtype=float)

# Inner porcelain floor limits from coro.world. The marble border is outside
# these bounds, but exploration is intentionally constrained to the floor.
WORLD_X_MIN = -1.8
WORLD_X_MAX = 2.7
WORLD_Y_MIN = -1.5
WORLD_Y_MAX = 1.5

GRID_RESOLUTION = 0.075
SENSING_RANGE = 0.45          # Rs
COMMUNICATION_RANGE = 1.5    # Rc, small enough to force relay behavior
CONNECTIVITY_MARGIN = 0.85    # keep targets inside Rc with room for control error
SUPPORTER_LIMIT_BUFFER = 0.03 # keep relay targets just inside the safe radius

ALPHA = 0.78                  # explorer -> supporter preemptive margin
GAMMA = 0.65                  # supporter flocking blend
BETA_SUPPORTERS = 0.50        # beta1
BETA_EXPLORERS = 0.80         # beta2

# Allow every non-base robot to explore in parallel. The relay chain expands
# dynamically: when frontiers move out of safe reach, the algorithm promotes
# the closest free robots back to supporter so they can act as bridges.

MAX_STEP = 0.10               # max planar target step per update
TARGET_REACHED_DISTANCE = 0.16
FRONTIER_SAMPLE_LIMIT = 220

MIN_ROBOT_DISTANCE = 0.25
AVOID_RANGE = 0.52            # Ravoid
AVOID_GAIN = 0.24             # kavoid
BORDER_CLEARANCE = 0.20
BOUNDARY_MARGIN = 0.28
BOUNDARY_GAIN = 0.20

STAGNATION_STEPS = 28
STAGNATION_DISTANCE = 0.10
RECOVERY_STEP_GAIN = 0.65

UNKNOWN = 0
FREE = 1


@dataclass
class RobotState:
    name: str
    label: str
    position: np.ndarray = field(default_factory=lambda: np.zeros(2))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))
    role: str = "explorer"
    target: Optional[np.ndarray] = None
    history: List[np.ndarray] = field(default_factory=list)
    local_map: np.ndarray = field(default_factory=lambda: np.zeros((1, 1), dtype=np.int8))


@dataclass
class AlgorithmSnapshot:
    positions: List[np.ndarray]
    targets: List[Optional[np.ndarray]]
    roles: List[str]
    rng: List[List[int]]
    frontiers: List[Tuple[int, int]]
    safe_frontiers: Dict[int, List[Tuple[int, int]]]
    global_map: np.ndarray
    base: np.ndarray
    covered_cells: int
    total_cells: int
    coverage_percent: float


class DRBECMAlgorithm:
    """Small implementation of Chaabi and Mitton's DRBECM loop.

    The class deliberately has no ROS dependency. The ROS node owns transport
    and calls update_pose()/step(). This keeps algorithm and visualization
    separable and easy to inspect.
    """

    def __init__(self) -> None:
        self.width = int(math.ceil((WORLD_X_MAX - WORLD_X_MIN) / GRID_RESOLUTION))
        self.height = int(math.ceil((WORLD_Y_MAX - WORLD_Y_MIN) / GRID_RESOLUTION))
        self.robots = [
            RobotState(name=name, label=ROBOT_LABELS[i])
            for i, name in enumerate(ROBOT_NAMES)
        ]
        for robot in self.robots:
            robot.local_map = np.zeros((self.height, self.width), dtype=np.int8)

        # Keep cf0 as the base relay anchor. The other drones start as explorers
        # and can become supporters dynamically.
        self.robots[0].role = "supporter"
        for robot in self.robots[1:]:
            robot.role = "explorer"

        # Counters used to break stagnation by actively sweeping the leaf
        # explorer around the chain tip when no safe frontier is available.
        self._tick = 0
        self._sweep_phase = 0.0

        self.last_snapshot = AlgorithmSnapshot(
            positions=[r.position.copy() for r in self.robots],
            targets=[None for _ in self.robots],
            roles=[r.role for r in self.robots],
            rng=[[] for _ in self.robots],
            frontiers=[],
            safe_frontiers={},
            global_map=np.zeros((self.height, self.width), dtype=np.int8),
            base=BASE_POSITION.copy(),
            covered_cells=0,
            total_cells=self.width * self.height,
            coverage_percent=0.0,
        )

    def update_pose(self, name: str, position: np.ndarray) -> None:
        idx = ROBOT_NAMES.index(name)
        robot = self.robots[idx]
        clipped = self._clip(position)
        robot.velocity = clipped - robot.position
        robot.position = clipped

    def step(self) -> AlgorithmSnapshot:
        self._tick += 1
        for i in range(len(self.robots)):
            self._sense(i)

        rng = self._rng_neighbors()
        self._share_maps(rng)
        global_map = self._global_map()
        frontiers = self._frontiers(global_map)
        safe_frontiers = {
            i: self._safe_frontiers(i, frontiers)
            for i in range(len(self.robots))
        }

        self._update_roles(rng, safe_frontiers, frontiers)
        # Re-evaluate "safe" frontiers after roles changed — promoting a relay
        # makes additional frontiers reachable on the same tick.
        safe_frontiers = {
            i: self._safe_frontiers(i, frontiers)
            for i in range(len(self.robots))
        }
        targets = self._compute_targets(rng, frontiers, safe_frontiers)
        covered_cells = int(np.count_nonzero(global_map == FREE))
        total_cells = self.width * self.height

        self.last_snapshot = AlgorithmSnapshot(
            positions=[r.position.copy() for r in self.robots],
            targets=[None if t is None else t.copy() for t in targets],
            roles=[r.role for r in self.robots],
            rng=rng,
            frontiers=frontiers,
            safe_frontiers=safe_frontiers,
            global_map=global_map.copy(),
            base=BASE_POSITION.copy(),
            covered_cells=covered_cells,
            total_cells=total_cells,
            coverage_percent=100.0 * covered_cells / total_cells,
        )
        return self.last_snapshot

    # ------------------------------------------------------------------
    # Grid conversion and map update
    # ------------------------------------------------------------------

    def world_to_grid(self, xy: np.ndarray) -> Tuple[int, int]:
        gx = int((float(xy[0]) - WORLD_X_MIN) / GRID_RESOLUTION)
        gy = int((float(xy[1]) - WORLD_Y_MIN) / GRID_RESOLUTION)
        return (
            int(np.clip(gx, 0, self.width - 1)),
            int(np.clip(gy, 0, self.height - 1)),
        )

    def grid_to_world(self, cell: Tuple[int, int]) -> np.ndarray:
        gx, gy = cell
        return np.array([
            WORLD_X_MIN + (gx + 0.5) * GRID_RESOLUTION,
            WORLD_Y_MIN + (gy + 0.5) * GRID_RESOLUTION,
        ], dtype=float)

    def _sense(self, idx: int) -> None:
        robot = self.robots[idx]
        gx, gy = self.world_to_grid(robot.position)
        radius_cells = int(math.ceil(SENSING_RANGE / GRID_RESOLUTION))
        for yy in range(max(0, gy - radius_cells), min(self.height, gy + radius_cells + 1)):
            for xx in range(max(0, gx - radius_cells), min(self.width, gx + radius_cells + 1)):
                if np.linalg.norm(self.grid_to_world((xx, yy)) - robot.position) <= SENSING_RANGE:
                    robot.local_map[yy, xx] = FREE

    def _global_map(self) -> np.ndarray:
        merged = np.zeros((self.height, self.width), dtype=np.int8)
        for robot in self.robots:
            merged = np.maximum(merged, robot.local_map)
        return merged

    def _share_maps(self, rng: List[List[int]]) -> None:
        for i, neighbors in enumerate(rng):
            for j in neighbors:
                self.robots[i].local_map = np.maximum(
                    self.robots[i].local_map,
                    self.robots[j].local_map,
                )
        merged = self._global_map()
        for robot in self.robots:
            robot.local_map = merged.copy()

    def _frontiers(self, grid: np.ndarray) -> List[Tuple[int, int]]:
        result: List[Tuple[int, int]] = []
        for yy in range(self.height):
            for xx in range(self.width):
                if grid[yy, xx] != FREE:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = xx + dx, yy + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height and grid[ny, nx] == UNKNOWN:
                        result.append((xx, yy))
                        break
        if len(result) <= FRONTIER_SAMPLE_LIMIT:
            return result
        stride = max(1, len(result) // FRONTIER_SAMPLE_LIMIT)
        return result[::stride]

    # ------------------------------------------------------------------
    # Relative Neighborhood Graph and connectivity
    # ------------------------------------------------------------------

    def _communication_neighbors(self) -> List[List[int]]:
        result = [[] for _ in self.robots]
        for i, ri in enumerate(self.robots):
            for j, rj in enumerate(self.robots):
                if i == j:
                    continue
                if np.linalg.norm(ri.position - rj.position) <= COMMUNICATION_RANGE:
                    result[i].append(j)
        return result

    def _rng_neighbors(self) -> List[List[int]]:
        comm = self._communication_neighbors()
        result = [[] for _ in self.robots]
        for i, neighbors in enumerate(comm):
            for j in neighbors:
                dij = np.linalg.norm(self.robots[i].position - self.robots[j].position)
                keep = True
                for k in set(comm[i]).intersection(comm[j]):
                    if k == i or k == j:
                        continue
                    dik = np.linalg.norm(self.robots[i].position - self.robots[k].position)
                    djk = np.linalg.norm(self.robots[j].position - self.robots[k].position)
                    if dij > max(dik, djk):
                        keep = False
                        break
                if keep:
                    result[i].append(j)
        return result

    def _connected_to_base(self, idx: int, roles: Optional[List[str]] = None) -> bool:
        roles = roles or [robot.role for robot in self.robots]
        if np.linalg.norm(self.robots[idx].position - BASE_POSITION) <= self._rc_safe():
            return True
        connected_supporters = self._connected_supporters(roles=roles)
        if roles[idx] == "supporter":
            return idx in connected_supporters
        return any(
            np.linalg.norm(self.robots[idx].position - self.robots[j].position) <= self._rc_safe()
            for j in connected_supporters
        )

    def _connected_supporters(
        self,
        roles: Optional[List[str]] = None,
        positions: Optional[List[np.ndarray]] = None,
    ) -> set:
        roles = roles or [robot.role for robot in self.robots]
        positions = positions or [robot.position for robot in self.robots]
        connected = {
            i for i, role in enumerate(roles)
            if role == "supporter" and np.linalg.norm(positions[i] - BASE_POSITION) <= self._rc_safe()
        }

        changed = True
        while changed:
            changed = False
            for i, role in enumerate(roles):
                if role != "supporter" or i in connected:
                    continue
                if any(np.linalg.norm(positions[i] - positions[j]) <= self._rc_safe() for j in connected):
                    connected.add(i)
                    changed = True
        return connected

    def _target_keeps_connectivity(self, idx: int, target: np.ndarray) -> bool:
        roles = [robot.role for robot in self.robots]
        positions = [robot.position.copy() for robot in self.robots]
        positions[idx] = target

        connected_supporters = self._connected_supporters(roles=roles, positions=positions)
        if roles[idx] == "supporter":
            return idx in connected_supporters

        if np.linalg.norm(target - BASE_POSITION) <= self._rc_safe():
            return True
        return any(np.linalg.norm(target - positions[j]) <= self._rc_safe() for j in connected_supporters)

    def _rc_safe(self) -> float:
        return CONNECTIVITY_MARGIN * COMMUNICATION_RANGE

    # ------------------------------------------------------------------
    # Role update and target computation
    # ------------------------------------------------------------------

    def _update_roles(
        self,
        rng: List[List[int]],
        safe_frontiers: Dict[int, List[Tuple[int, int]]],
        frontiers: List[Tuple[int, int]],
    ) -> None:
        # Eq. 2 of the article: each robot independently decides its role based
        # on local observations. cf0 is anchored at the base station and never
        # changes role.
        comm = self._communication_neighbors()

        for i in range(1, len(self.robots)):
            robot = self.robots[i]
            in_range = comm[i]
            explorers_in_range = [j for j in in_range if self.robots[j].role == "explorer"]
            supporters_in_range = [j for j in in_range if self.robots[j].role == "supporter"]

            if robot.role == "explorer":
                # Explorer → Supporter (Eq. 2, first branch):
                # has explorer neighbors AND is farther than α·Rc from all
                # supporters and the base station.
                if not explorers_in_range:
                    continue
                dist_to_base = float(np.linalg.norm(robot.position - BASE_POSITION))
                far_from_base = dist_to_base > ALPHA * COMMUNICATION_RANGE
                far_from_all_supporters = all(
                    float(np.linalg.norm(robot.position - self.robots[j].position))
                    > ALPHA * COMMUNICATION_RANGE
                    for j in supporters_in_range
                )
                if far_from_base and far_from_all_supporters:
                    robot.role = "supporter"

            elif robot.role == "supporter":
                # Supporter → Explorer (Eq. 2, second branch):
                # connected to base, no explorer neighbors, exactly one
                # supporter neighbor, all neighbors connected, and there
                # exists a closer supporter to the base (this one is redundant).
                if not self._connected_to_base(i):
                    continue
                if explorers_in_range:
                    continue
                if len(supporters_in_range) != 1:
                    continue
                if not all(self._connected_to_base(j) for j in in_range):
                    continue
                dist_i_base = float(np.linalg.norm(robot.position - BASE_POSITION))
                closer_exists = any(
                    self.robots[k].role == "supporter"
                    and float(np.linalg.norm(self.robots[k].position - BASE_POSITION)) < dist_i_base
                    for k in in_range
                )
                if closer_exists:
                    robot.role = "explorer"

    def _safe_frontiers(
        self,
        idx: int,
        frontiers: List[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        connected_supporters = self._connected_supporters()
        safe = []
        for frontier in frontiers:
            point = self.grid_to_world(frontier)
            if np.linalg.norm(point - BASE_POSITION) <= self._rc_safe():
                safe.append(frontier)
                continue
            if any(np.linalg.norm(point - self.robots[j].position) <= self._rc_safe() for j in connected_supporters):
                safe.append(frontier)
        return safe

    def _compute_targets(
        self,
        rng: List[List[int]],
        frontiers: List[Tuple[int, int]],
        safe_frontiers: Dict[int, List[Tuple[int, int]]],
    ) -> List[Optional[np.ndarray]]:
        targets: List[Optional[np.ndarray]] = [None for _ in self.robots]
        reserved: List[Tuple[int, np.ndarray]] = []

        for i, robot in enumerate(self.robots):
            robot.history.append(robot.position.copy())
            robot.history = robot.history[-STAGNATION_STEPS:]

        for i, robot in enumerate(self.robots):
            if i == 0:
                targets[i] = BASE_POSITION.copy()
                reserved.append((i, targets[i]))
                continue

            if robot.role == "explorer":
                targets[i] = self._explorer_target(
                    i, safe_frontiers.get(i, []), frontiers, reserved
                )
            else:
                targets[i] = self._supporter_flocking_target(i, rng)

            if targets[i] is not None:
                targets[i] = self._safe_target(i, targets[i], rng, reserved)
                reserved.append((i, targets[i]))

        targets = self._repair_target_set(targets)
        for i, robot in enumerate(self.robots):
            robot.target = targets[i]
        return targets

    def _supporter_flocking_target(self, idx: int, rng: List[List[int]]) -> np.ndarray:
        """Flocking-inspired supporter positioning (metrics_Flocking_inspired.py).

        Move toward the mean position of connected explorers, but project the
        target close to the safe communication limit from the nearest connected
        anchor. This places the supporter as a relay instead of letting it chase
        the exploration front directly.
        If no explorers are reachable, move toward the mean of connected
        supporters to maintain the chain; fall back to base if isolated.
        """
        comm = self._communication_neighbors()
        in_range = comm[idx]

        explorers  = [j for j in in_range if self.robots[j].role == "explorer"]
        supporters = [j for j in in_range if self.robots[j].role == "supporter"]

        if explorers:
            explorer_center = np.mean(
                [self.robots[j].position for j in explorers],
                axis=0,
            )
            return self._relay_limit_target(idx, explorer_center)
        if supporters:
            return np.mean([self.robots[j].position for j in supporters], axis=0)
        return BASE_POSITION.copy()

    def _relay_limit_target(self, idx: int, desired: np.ndarray) -> np.ndarray:
        anchor = self._nearest_support_or_base(idx)
        direction = desired - anchor
        distance = float(np.linalg.norm(direction))
        if distance < 1e-9:
            return self.robots[idx].position.copy()

        radius = max(0.0, self._rc_safe() - SUPPORTER_LIMIT_BUFFER)
        return anchor + direction / distance * min(distance, radius)

    def _explorer_target(
        self,
        idx: int,
        safe: List[Tuple[int, int]],
        all_frontiers: List[Tuple[int, int]],
        reserved: List[Tuple[int, np.ndarray]],
    ) -> np.ndarray:
        robot = self.robots[idx]
        if not safe:
            if all_frontiers:
                # No safe frontier but unexplored area still exists: advance
                # toward the nearest frontier anyway (article's self.test=True
                # behaviour). Moving away from supporters triggers the ALPHA
                # condition in _update_roles so another robot becomes a relay,
                # extending the safe zone toward this explorer.
                return self.grid_to_world(
                    min(all_frontiers,
                        key=lambda f: float(np.linalg.norm(
                            self.grid_to_world(f) - robot.position)))
                )
            # Truly no frontiers left: return to base.
            return self._nearest_support_or_base(idx)

        stagnant = self._is_stagnant(idx)

        def score(cell: Tuple[int, int]) -> float:
            point = self.grid_to_world(cell)
            distance = float(np.linalg.norm(point - robot.position))
            reservation_penalty = 0.0
            if reserved:
                nearest_reserved = min(
                    float(np.linalg.norm(point - p)) for _, p in reserved
                )
                reservation_penalty = 0.9 / (0.18 + nearest_reserved)
            information_bonus = 0.22 * float(np.linalg.norm(point - BASE_POSITION))
            history_penalty = 0.0
            if robot.history:
                # Discourage immediate revisits — helps when a frontier sits at
                # the very edge of reach and the robot keeps oscillating.
                history_penalty = 0.35 / (
                    0.18 + min(
                        float(np.linalg.norm(point - h)) for h in robot.history[-12:]
                    )
                )
            base = distance + reservation_penalty + history_penalty - information_bonus
            if stagnant:
                # Flip distance preference: when stuck, jump to the farthest
                # safe frontier rather than the nearest one. The bonuses still
                # spread multiple stagnant explorers apart.
                base = -distance + reservation_penalty - information_bonus
            return base

        return self.grid_to_world(min(safe, key=score))

    # ------------------------------------------------------------------
    # Collision avoidance, stagnation and clipping
    # ------------------------------------------------------------------

    def _safe_target(
        self,
        idx: int,
        target: np.ndarray,
        rng: List[List[int]],
        reserved: List[Tuple[int, np.ndarray]],
    ) -> np.ndarray:
        current = self.robots[idx].position
        candidate = self._bounded_step(idx, target, rng)

        for _ in range(10):
            candidate = self._clip(candidate)
            if not self._target_keeps_connectivity(idx, candidate):
                candidate = self._clip(current + 0.5 * (candidate - current))
                continue

            separation_push = self._separation_push(idx, candidate, reserved)
            if np.linalg.norm(separation_push) > 1e-6:
                candidate = self._limit_from_current(current, candidate + separation_push)
                continue

            return candidate

        hold = self._clip(current)
        if self._target_keeps_connectivity(idx, hold) and not self._target_too_close(idx, hold, reserved):
            return hold
        return self._limit_from_current(current, self._nearest_support_or_base(idx))

    def _bounded_step(self, idx: int, target: np.ndarray, rng: List[List[int]]) -> np.ndarray:
        robot = self.robots[idx]
        desired = self._limit_vector(target - robot.position, MAX_STEP)

        desired += self._avoidance(idx, rng)
        desired += self._boundary_push(robot.position)

        desired = self._limit_vector(desired, MAX_STEP)
        return self._clip(robot.position + desired)

    def _avoidance(self, idx: int, rng: List[List[int]]) -> np.ndarray:
        result = np.zeros(2)
        for j in range(len(self.robots)):
            if j == idx:
                continue
            diff = self.robots[idx].position - self.robots[j].position
            dist = np.linalg.norm(diff)
            if 1e-6 < dist < AVOID_RANGE:
                strength = AVOID_GAIN * ((AVOID_RANGE - dist) / AVOID_RANGE) ** 2
                result += strength * diff / dist
        return result

    def _separation_push(
        self,
        idx: int,
        candidate: np.ndarray,
        reserved: List[Tuple[int, np.ndarray]],
    ) -> np.ndarray:
        push = np.zeros(2)
        other_points = [
            (j, robot.position)
            for j, robot in enumerate(self.robots)
            if j != idx
        ] + reserved

        for j, point in other_points:
            if j == idx:
                continue
            diff = candidate - point
            dist = np.linalg.norm(diff)
            if dist >= MIN_ROBOT_DISTANCE:
                continue
            if dist < 1e-6:
                angle = 2.0 * math.pi * idx / max(1, len(self.robots))
                diff = np.array([math.cos(angle), math.sin(angle)], dtype=float)
                dist = 1.0
            push += ((MIN_ROBOT_DISTANCE - dist) / dist) * diff

        return self._limit_vector(push, MAX_STEP)

    def _target_too_close(
        self,
        idx: int,
        candidate: np.ndarray,
        reserved: List[Tuple[int, np.ndarray]],
    ) -> bool:
        other_points = [
            (j, robot.position)
            for j, robot in enumerate(self.robots)
            if j != idx
        ] + reserved
        return any(
            j != idx and np.linalg.norm(candidate - point) < MIN_ROBOT_DISTANCE
            for j, point in other_points
        )

    def _repair_target_set(self, targets: List[Optional[np.ndarray]]) -> List[Optional[np.ndarray]]:
        repaired = [
            robot.position.copy() if target is None else self._clip(target)
            for robot, target in zip(self.robots, targets)
        ]

        for _ in range(8):
            changed = False
            positions = [target.copy() for target in repaired]

            for i in range(len(repaired)):
                if not self._position_keeps_connectivity(i, positions):
                    fallback = self.robots[i].position.copy()
                    if not self._target_keeps_connectivity(i, fallback):
                        fallback = self._nearest_support_or_base(i)
                    repaired[i] = self._limit_from_current(self.robots[i].position, fallback)
                    positions[i] = repaired[i].copy()
                    changed = True

            for i in range(len(repaired)):
                for j in range(i + 1, len(repaired)):
                    diff = repaired[i] - repaired[j]
                    dist = np.linalg.norm(diff)
                    if dist >= MIN_ROBOT_DISTANCE:
                        continue
                    move_idx = j if j != 0 else i
                    if move_idx == 0:
                        continue
                    if dist < 1e-6:
                        angle = 2.0 * math.pi * move_idx / max(1, len(repaired))
                        diff = np.array([math.cos(angle), math.sin(angle)], dtype=float)
                        dist = 1.0
                    direction = diff / dist if move_idx == i else -diff / dist
                    repaired[move_idx] = self._limit_from_current(
                        self.robots[move_idx].position,
                        repaired[move_idx] + direction * (MIN_ROBOT_DISTANCE - dist),
                    )
                    changed = True

            if not changed:
                break

        return repaired

    def _position_keeps_connectivity(self, idx: int, positions: List[np.ndarray]) -> bool:
        roles = [robot.role for robot in self.robots]
        connected_supporters = self._connected_supporters(roles=roles, positions=positions)
        if roles[idx] == "supporter":
            return idx in connected_supporters
        if np.linalg.norm(positions[idx] - BASE_POSITION) <= self._rc_safe():
            return True
        return any(
            np.linalg.norm(positions[idx] - positions[j]) <= self._rc_safe()
            for j in connected_supporters
        )

    def _boundary_push(self, position: np.ndarray) -> np.ndarray:
        push = np.zeros(2)
        if position[0] - WORLD_X_MIN < BOUNDARY_MARGIN:
            push[0] += BOUNDARY_GAIN
        if WORLD_X_MAX - position[0] < BOUNDARY_MARGIN:
            push[0] -= BOUNDARY_GAIN
        if position[1] - WORLD_Y_MIN < BOUNDARY_MARGIN:
            push[1] += BOUNDARY_GAIN
        if WORLD_Y_MAX - position[1] < BOUNDARY_MARGIN:
            push[1] -= BOUNDARY_GAIN
        return push

    def _is_stagnant(self, idx: int) -> bool:
        history = self.robots[idx].history
        if len(history) < STAGNATION_STEPS:
            return False
        current = history[-1]
        return max(np.linalg.norm(p - current) for p in history[:-1]) <= STAGNATION_DISTANCE

    def _nearest_support_or_base(self, idx: int) -> np.ndarray:
        candidates = [BASE_POSITION]
        connected_supporters = self._connected_supporters()
        for j in connected_supporters:
            if j != idx:
                candidates.append(self.robots[j].position)
        position = self.robots[idx].position
        return min(candidates, key=lambda p: np.linalg.norm(p - position)).copy()

    def _clip(self, xy: np.ndarray) -> np.ndarray:
        return np.array([
            np.clip(float(xy[0]), WORLD_X_MIN + BORDER_CLEARANCE, WORLD_X_MAX - BORDER_CLEARANCE),
            np.clip(float(xy[1]), WORLD_Y_MIN + BORDER_CLEARANCE, WORLD_Y_MAX - BORDER_CLEARANCE),
        ], dtype=float)

    def _limit_from_current(self, current: np.ndarray, target: np.ndarray) -> np.ndarray:
        return self._clip(current + self._limit_vector(target - current, MAX_STEP))

    def _limit_vector(self, vector: np.ndarray, max_norm: float) -> np.ndarray:
        norm = np.linalg.norm(vector)
        if norm > max_norm and norm > 1e-9:
            return vector * (max_norm / norm)
        return vector
