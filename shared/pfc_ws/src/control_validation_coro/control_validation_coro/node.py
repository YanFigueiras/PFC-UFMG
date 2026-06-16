import math
import time
from typing import Dict, List, Optional

import numpy as np
import rclpy
from crazyflie_interfaces.msg import FullState
from crazyflie_interfaces.srv import Arm
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions


FRAME_ID = "world"
ROBOT_NAMES = ["cf_1", "cf_2", "cf_3", "cf_4"]
BASE_NAME = "cf_1"
FLYING_ROBOT_NAMES = ["cf_2", "cf_3", "cf_4"]

CONTROL_PERIOD = 0.05
POSE_TIMEOUT_SEC = 2.0

CONTROL_HEIGHT = 1.0
MAX_SPEED = 0.15

TAKEOFF_DURATION_SEC = 5.0
LANDING_DURATION_SEC = 5.0
LANDING_FINAL_HEIGHT = 0.05
LANDING_HOLD_SEC = 0.25

CIRCLE_RADIUS = 0.25
CIRCLE_LAPS = 1
SQUARE_SIDE = 0.25


class ControlValidationCoroNode(Node):
    def __init__(self) -> None:
        super().__init__("control_validation_coro_node")
        self.last_poses: Dict[str, np.ndarray] = {}
        self.last_pose_wall: Dict[str, float] = {}
        self.hover_points: Dict[str, np.ndarray] = {}
        self.last_log_wall: Dict[str, float] = {}

        self.pose_subs = [
            self.create_subscription(
                PoseStamped,
                f"/{name}/pose",
                lambda msg, robot_name=name: self._pose_cb(msg, robot_name),
                10,
            )
            for name in ROBOT_NAMES
        ]
        self.fullstate_pubs = {
            name: self.create_publisher(FullState, f"/{name}/cmd_full_state", 1)
            for name in FLYING_ROBOT_NAMES
        }
        self.arm_client = self.create_client(Arm, "/all/arm")
        self.get_logger().info(
            "Validador CORO pronto: aguardando poses em "
            + ", ".join(f"/{name}/pose" for name in ROBOT_NAMES)
            + f"; {BASE_NAME} ficara no chao"
        )

    def _pose_cb(self, msg: PoseStamped, robot_name: str) -> None:
        self.last_poses[robot_name] = np.array(
            [msg.pose.position.x, msg.pose.position.y, msg.pose.position.z],
            dtype=float,
        )
        self.last_pose_wall[robot_name] = time.monotonic()

    def run_mission(self) -> None:
        self._wait_for_poses()
        self._arm()

        start_poses = {
            name: self.last_poses[name].copy()
            for name in FLYING_ROBOT_NAMES
        }
        start_xy = {
            name: pose[:2].copy()
            for name, pose in start_poses.items()
        }

        self.get_logger().info(
            f"Base {BASE_NAME} mantida no chao; decolando "
            + ", ".join(FLYING_ROBOT_NAMES)
            + " por cmd_full_state"
        )
        self._fly_line(
            start_poses,
            {
                name: np.array([xy[0], xy[1], CONTROL_HEIGHT], dtype=float)
                for name, xy in start_xy.items()
            },
            TAKEOFF_DURATION_SEC,
        )

        self.get_logger().info("Movendo agentes aereos para o inicio dos circulos")
        self._fly_line(
            {
                name: np.array([xy[0], xy[1], CONTROL_HEIGHT], dtype=float)
                for name, xy in start_xy.items()
            },
            {
                name: np.array([xy[0] + CIRCLE_RADIUS, xy[1], CONTROL_HEIGHT], dtype=float)
                for name, xy in start_xy.items()
            },
            self._duration_for_distance(CIRCLE_RADIUS),
        )

        self.get_logger().info("Executando circulos com agentes aereos")
        self._fly_circle(start_xy, CIRCLE_RADIUS, CIRCLE_LAPS)

        self.get_logger().info("Executando quadrados com agentes aereos")
        self._fly_square(start_xy, SQUARE_SIDE)

        self.hover_points = {
            name: np.array([xy[0], xy[1], CONTROL_HEIGHT], dtype=float)
            for name, xy in start_xy.items()
        }
        self.get_logger().info("Missao concluida; agentes aereos em hover ate Ctrl+C")
        while rclpy.ok():
            for name, point in self.hover_points.items():
                self._publish_state(name, point, np.zeros(3))
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(CONTROL_PERIOD)

    def land_with_full_state(self) -> None:
        active_names = [
            name for name in FLYING_ROBOT_NAMES
            if name in self.last_poses
        ]
        if not active_names:
            self.get_logger().info("Sem poses recebidas; pouso ignorado")
            return

        starts = {
            name: self.last_poses[name].copy()
            for name in active_names
        }
        for name, hover_point in self.hover_points.items():
            if name in starts:
                starts[name][:2] = hover_point[:2]

        ends = {
            name: np.array([start[0], start[1], LANDING_FINAL_HEIGHT], dtype=float)
            for name, start in starts.items()
        }

        self.get_logger().info("Ctrl+C recebido: pousando agentes aereos via cmd_full_state")
        self._fly_line(starts, ends, LANDING_DURATION_SEC)

        for _ in range(max(1, int(LANDING_HOLD_SEC / CONTROL_PERIOD))):
            for name, end in ends.items():
                self._publish_state(name, end, np.zeros(3))
            time.sleep(CONTROL_PERIOD)

        self.get_logger().info("Pouso por full state finalizado")

    def _wait_for_poses(self) -> None:
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=CONTROL_PERIOD)
            missing = self._missing_or_stale_poses()
            if not missing:
                return
            self._log_every("poses", f"Aguardando poses dos drones: {missing}", 2.0)

    def _missing_or_stale_poses(self) -> List[str]:
        now = time.monotonic()
        return [
            name for name in ROBOT_NAMES
            if (
                name not in self.last_pose_wall
                or now - self.last_pose_wall[name] > POSE_TIMEOUT_SEC
            )
        ]

    def _arm(self) -> None:
        while rclpy.ok() and not self.arm_client.service_is_ready():
            self._log_every("arm_service", "Aguardando /all/arm", 2.0)
            rclpy.spin_once(self, timeout_sec=CONTROL_PERIOD)

        request = Arm.Request()
        request.arm = True
        future = self.arm_client.call_async(request)
        self.get_logger().info("Armando todos os Crazyflies")
        while rclpy.ok() and not future.done():
            rclpy.spin_once(self, timeout_sec=CONTROL_PERIOD)

    def _fly_line(
        self,
        starts: Dict[str, np.ndarray],
        ends: Dict[str, np.ndarray],
        duration: float,
    ) -> None:
        duration = max(duration, CONTROL_PERIOD)
        steps = max(1, int(duration / CONTROL_PERIOD))
        velocities = {
            name: (ends[name] - start) / duration
            for name, start in starts.items()
            if name in ends
        }

        for step in range(steps + 1):
            ratio = step / steps
            for name, start in starts.items():
                if name not in ends:
                    continue
                point = start + ratio * (ends[name] - start)
                self._publish_state(name, point, velocities[name])
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(CONTROL_PERIOD)

    def _fly_circle(
        self,
        centers_xy: Dict[str, np.ndarray],
        radius: float,
        laps: int,
    ) -> None:
        omega = MAX_SPEED / radius
        duration = laps * 2.0 * math.pi / omega
        steps = max(1, int(duration / CONTROL_PERIOD))

        for step in range(steps + 1):
            theta = 2.0 * math.pi * laps * step / steps
            for name, center_xy in centers_xy.items():
                point = np.array(
                    [
                        center_xy[0] + radius * math.cos(theta),
                        center_xy[1] + radius * math.sin(theta),
                        CONTROL_HEIGHT,
                    ],
                    dtype=float,
                )
                velocity = np.array(
                    [
                        -radius * omega * math.sin(theta),
                        radius * omega * math.cos(theta),
                        0.0,
                    ],
                    dtype=float,
                )
                self._publish_state(name, point, velocity)
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(CONTROL_PERIOD)

    def _fly_square(self, centers_xy: Dict[str, np.ndarray], side: float) -> None:
        half = side / 2.0
        z = CONTROL_HEIGHT
        corners_by_robot = {
            name: [
                np.array([center_xy[0] + half, center_xy[1], z], dtype=float),
                np.array([center_xy[0] + half, center_xy[1] + half, z], dtype=float),
                np.array([center_xy[0] - half, center_xy[1] + half, z], dtype=float),
                np.array([center_xy[0] - half, center_xy[1] - half, z], dtype=float),
                np.array([center_xy[0] + half, center_xy[1] - half, z], dtype=float),
                np.array([center_xy[0] + half, center_xy[1], z], dtype=float),
                np.array([center_xy[0], center_xy[1], z], dtype=float),
            ]
            for name, center_xy in centers_xy.items()
        }

        segment_count = len(next(iter(corners_by_robot.values()))) - 1
        for segment in range(segment_count):
            starts = {
                name: corners[segment]
                for name, corners in corners_by_robot.items()
            }
            ends = {
                name: corners[segment + 1]
                for name, corners in corners_by_robot.items()
            }
            distance = float(np.linalg.norm(next(iter(ends.values())) - next(iter(starts.values()))))
            self._fly_line(starts, ends, self._duration_for_distance(distance))

    def _duration_for_distance(self, distance: float) -> float:
        return max(float(distance) / MAX_SPEED, CONTROL_PERIOD)

    def _publish_state(self, name: str, position: np.ndarray, velocity: np.ndarray) -> None:
        msg = FullState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = FRAME_ID
        msg.pose.position.x = float(position[0])
        msg.pose.position.y = float(position[1])
        msg.pose.position.z = float(position[2])
        msg.pose.orientation.w = 1.0
        msg.twist.linear.x = float(velocity[0])
        msg.twist.linear.y = float(velocity[1])
        msg.twist.linear.z = float(velocity[2])
        self.fullstate_pubs[name].publish(msg)

    def _log_every(self, key: str, message: str, period_sec: float) -> None:
        now = time.monotonic()
        if now - self.last_log_wall.get(key, 0.0) >= period_sec:
            self.last_log_wall[key] = now
            self.get_logger().info(message)


def main(args=None) -> None:
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = ControlValidationCoroNode()
    try:
        node.run_mission()
    except KeyboardInterrupt:
        node.land_with_full_state()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
