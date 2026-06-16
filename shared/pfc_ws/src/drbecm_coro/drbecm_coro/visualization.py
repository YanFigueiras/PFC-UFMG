from typing import Iterable, List, Tuple
import math

from geometry_msgs.msg import Point, Pose, Vector3
from nav_msgs.msg import MapMetaData, OccupancyGrid
from std_msgs.msg import ColorRGBA, Header
from visualization_msgs.msg import Marker, MarkerArray

from drbecm_coro.algorithm import (
    AlgorithmSnapshot,
    COMMUNICATION_RANGE,
    FREE,
    GRID_RESOLUTION,
    ROBOT_LABELS,
    SENSING_RANGE,
    WORLD_X_MAX,
    WORLD_X_MIN,
    WORLD_Y_MAX,
    WORLD_Y_MIN,
)


Z_MARKERS = 0.04
MAX_FRONTIER_MARKERS = 240

COLOR_EXPLORER = ColorRGBA(r=0.08, g=0.62, b=0.88, a=1.0)
COLOR_SUPPORTER = ColorRGBA(r=0.90, g=0.16, b=0.78, a=1.0)
COLOR_BASE = ColorRGBA(r=1.0, g=0.30, b=0.18, a=1.0)
COLOR_TARGET = ColorRGBA(r=0.08, g=0.92, b=0.42, a=0.95)
COLOR_FRONTIER = ColorRGBA(r=1.0, g=0.84, b=0.08, a=0.78)
COLOR_RNG = ColorRGBA(r=1.0, g=0.12, b=0.08, a=0.72)
COLOR_RANGE = ColorRGBA(r=0.45, g=0.52, b=0.58, a=0.22)
COLOR_TEXT = ColorRGBA(r=0.94, g=0.96, b=0.98, a=1.0)
COLOR_COVERAGE = ColorRGBA(r=0.18, g=1.0, b=0.62, a=1.0)


def make_map(snapshot: AlgorithmSnapshot, stamp, frame_id: str = "world") -> OccupancyGrid:
    grid = snapshot.global_map
    height, width = grid.shape

    msg = OccupancyGrid()
    msg.header = Header(stamp=stamp, frame_id=frame_id)
    msg.info = MapMetaData()
    msg.info.resolution = float(GRID_RESOLUTION)
    msg.info.width = width
    msg.info.height = height
    msg.info.origin = Pose()
    msg.info.origin.position.x = float(WORLD_X_MIN)
    msg.info.origin.position.y = float(WORLD_Y_MIN)
    msg.info.origin.orientation.w = 1.0

    data: List[int] = []
    for yy in range(height):
        for xx in range(width):
            data.append(0 if grid[yy, xx] == FREE else -1)
    msg.data = data
    return msg


def make_markers(snapshot: AlgorithmSnapshot, stamp, frame_id: str = "world") -> MarkerArray:
    markers = MarkerArray()
    markers.markers.append(_delete_all(frame_id, stamp))
    markers.markers.append(_sphere("base", 0, snapshot.base, 0.15, COLOR_BASE, frame_id, stamp))
    markers.markers.append(_text("labels", 0, snapshot.base, "base", 0.16, frame_id, stamp))
    markers.markers.append(_coverage_text(snapshot, frame_id, stamp))
    markers.markers.append(_rng_lines(snapshot, frame_id, stamp))

    frontier_points = [snapshot_to_point(snapshot, cell) for cell in snapshot.frontiers[:MAX_FRONTIER_MARKERS]]
    markers.markers.append(_cube_list("frontiers", 0, frontier_points, 0.045, COLOR_FRONTIER, frame_id, stamp))

    marker_id = 1
    for idx, position in enumerate(snapshot.positions):
        role = snapshot.roles[idx]
        color = COLOR_EXPLORER if role == "explorer" else COLOR_SUPPORTER
        markers.markers.append(_sphere("drones", marker_id, position, 0.105, color, frame_id, stamp))
        markers.markers.append(_text("labels", marker_id, position, f"{ROBOT_LABELS[idx]} {role}", 0.13, frame_id, stamp))
        markers.markers.append(_circle("comm_range", marker_id, position, COMMUNICATION_RANGE, COLOR_RANGE, frame_id, stamp))
        markers.markers.append(_circle("sensor_range", marker_id, position, SENSING_RANGE, color_with_alpha(color, 0.18), frame_id, stamp))
        if snapshot.targets[idx] is not None:
            markers.markers.append(_cube("targets", marker_id, snapshot.targets[idx], 0.08, COLOR_TARGET, frame_id, stamp))
        marker_id += 1

    return markers


def snapshot_to_point(snapshot: AlgorithmSnapshot, cell: Tuple[int, int]) -> Point:
    gx, gy = cell
    point = Point()
    point.x = WORLD_X_MIN + (gx + 0.5) * GRID_RESOLUTION
    point.y = WORLD_Y_MIN + (gy + 0.5) * GRID_RESOLUTION
    point.z = Z_MARKERS
    return point


def color_with_alpha(color: ColorRGBA, alpha: float) -> ColorRGBA:
    return ColorRGBA(r=color.r, g=color.g, b=color.b, a=alpha)


def _delete_all(frame_id: str, stamp) -> Marker:
    marker = Marker()
    marker.header = Header(stamp=stamp, frame_id=frame_id)
    marker.action = Marker.DELETEALL
    return marker


def _base_marker(namespace: str, marker_id: int, frame_id: str, stamp) -> Marker:
    marker = Marker()
    marker.header = Header(stamp=stamp, frame_id=frame_id)
    marker.ns = namespace
    marker.id = marker_id
    marker.action = Marker.ADD
    marker.pose.orientation.w = 1.0
    return marker


def _sphere(namespace: str, marker_id: int, xy, diameter: float, color: ColorRGBA, frame_id: str, stamp) -> Marker:
    marker = _base_marker(namespace, marker_id, frame_id, stamp)
    marker.type = Marker.SPHERE
    marker.pose.position.x = float(xy[0])
    marker.pose.position.y = float(xy[1])
    marker.pose.position.z = Z_MARKERS + 0.04
    marker.scale = Vector3(x=diameter, y=diameter, z=diameter)
    marker.color = color
    return marker


def _cube(namespace: str, marker_id: int, xy, size: float, color: ColorRGBA, frame_id: str, stamp) -> Marker:
    marker = _base_marker(namespace, marker_id, frame_id, stamp)
    marker.type = Marker.CUBE
    marker.pose.position.x = float(xy[0])
    marker.pose.position.y = float(xy[1])
    marker.pose.position.z = Z_MARKERS + 0.025
    marker.scale = Vector3(x=size, y=size, z=0.05)
    marker.color = color
    return marker


def _cube_list(
    namespace: str,
    marker_id: int,
    points: Iterable[Point],
    size: float,
    color: ColorRGBA,
    frame_id: str,
    stamp,
) -> Marker:
    marker = _base_marker(namespace, marker_id, frame_id, stamp)
    marker.type = Marker.CUBE_LIST
    marker.scale = Vector3(x=size, y=size, z=0.025)
    marker.color = color
    marker.points = list(points)
    return marker


def _text(namespace: str, marker_id: int, xy, text: str, height: float, frame_id: str, stamp) -> Marker:
    marker = _base_marker(namespace, marker_id, frame_id, stamp)
    marker.type = Marker.TEXT_VIEW_FACING
    marker.pose.position.x = float(xy[0])
    marker.pose.position.y = float(xy[1])
    marker.pose.position.z = 0.34
    marker.scale.z = height
    marker.color = COLOR_TEXT
    marker.text = text
    return marker


def _coverage_text(snapshot: AlgorithmSnapshot, frame_id: str, stamp) -> Marker:
    marker = _base_marker("coverage", 0, frame_id, stamp)
    marker.type = Marker.TEXT_VIEW_FACING
    marker.pose.position.x = float((WORLD_X_MIN + WORLD_X_MAX) * 0.5)
    marker.pose.position.y = float(WORLD_Y_MAX + 0.32)
    marker.pose.position.z = 0.42
    marker.scale.z = 0.16
    marker.color = COLOR_COVERAGE
    marker.text = f"Cobertura: {snapshot.coverage_percent:.1f}% ({snapshot.covered_cells}/{snapshot.total_cells})"
    return marker


def _rng_lines(snapshot: AlgorithmSnapshot, frame_id: str, stamp) -> Marker:
    marker = _base_marker("rng", 0, frame_id, stamp)
    marker.type = Marker.LINE_LIST
    marker.scale.x = 0.018
    marker.color = COLOR_RNG

    seen = set()
    for i, neighbors in enumerate(snapshot.rng):
        for j in neighbors:
            edge = tuple(sorted((i, j)))
            if edge in seen:
                continue
            seen.add(edge)
            marker.points.append(_point(snapshot.positions[i]))
            marker.points.append(_point(snapshot.positions[j]))
    return marker


def _circle(namespace: str, marker_id: int, xy, radius: float, color: ColorRGBA, frame_id: str, stamp) -> Marker:
    marker = _base_marker(namespace, marker_id, frame_id, stamp)
    marker.type = Marker.LINE_STRIP
    marker.scale.x = 0.01
    marker.color = color
    for k in range(73):
        angle = 2.0 * math.pi * k / 72.0
        marker.points.append(Point(
            x=float(xy[0] + radius * math.cos(angle)),
            y=float(xy[1] + radius * math.sin(angle)),
            z=Z_MARKERS,
        ))
    return marker


def _point(xy) -> Point:
    return Point(x=float(xy[0]), y=float(xy[1]), z=Z_MARKERS + 0.03)
