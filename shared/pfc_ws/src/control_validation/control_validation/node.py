import math
import time
from typing import Optional

import numpy as np
import rclpy
from crazyflie_interfaces.msg import FullState
from crazyflie_interfaces.srv import Arm
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions


FRAME_ID = "world"
ROBOT_NAME = "cf_2"

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


class ControlValidationNode(Node):
    def __init__(self) -> None:
        super().__init__("control_validation_node")
        self.last_pose: Optional[np.ndarray] = None
        self.last_pose_wall = 0.0
        self.hover_point: Optional[np.ndarray] = None

        self.pose_sub = self.create_subscription(
            PoseStamped,
            f"/{ROBOT_NAME}/pose",
            self._pose_cb,
            10,
        )
        self.fullstate_pub = self.create_publisher(
            FullState,
            f"/{ROBOT_NAME}/cmd_full_state",
            1,
        )
        self.arm_client = self.create_client(Arm, "/all/arm")
        self.get_logger().info(
            f"Validador pronto: aguardando /{ROBOT_NAME}/pose"
        )

    def _pose_cb(self, msg: PoseStamped) -> None:
        self.last_pose = np.array(
            [msg.pose.position.x, msg.pose.position.y, msg.pose.position.z],
            dtype=float,
        )
        self.last_pose_wall = time.monotonic()

    def run_mission(self) -> None:
        self._wait_for_pose()
        self._arm()

        start_xy = self.last_pose[:2].copy()
        self.get_logger().info("Decolando por cmd_full_state")
        self._fly_line(
            np.array([start_xy[0], start_xy[1], self.last_pose[2]], dtype=float),
            np.array([start_xy[0], start_xy[1], CONTROL_HEIGHT], dtype=float),
            TAKEOFF_DURATION_SEC,
        )

        circle_start = np.array(
            [start_xy[0] + CIRCLE_RADIUS, start_xy[1], CONTROL_HEIGHT],
            dtype=float,
        )
        self.get_logger().info("Movendo para o início do círculo")
        self._fly_line(
            np.array([start_xy[0], start_xy[1], CONTROL_HEIGHT], dtype=float),
            circle_start,
            self._duration_for_distance(CIRCLE_RADIUS),
        )

        self.get_logger().info("Executando círculo")
        self._fly_circle(start_xy, CIRCLE_RADIUS, CIRCLE_LAPS)

        self.get_logger().info("Executando quadrado")
        self._fly_square(start_xy, SQUARE_SIDE)

        self.hover_point = np.array(
            [start_xy[0], start_xy[1], CONTROL_HEIGHT],
            dtype=float,
        )
        self.get_logger().info("Missão concluída; em hover até Ctrl+C")
        while rclpy.ok():
            self._publish_state(self.hover_point, np.zeros(3))
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(CONTROL_PERIOD)

    def land_with_full_state(self) -> None:
        if self.last_pose is None:
            self.get_logger().info("Sem pose recebida; pouso ignorado")
            return

        start = self.last_pose.copy()
        if self.hover_point is not None:
            start[:2] = self.hover_point[:2]
        end = np.array(
            [start[0], start[1], LANDING_FINAL_HEIGHT],
            dtype=float,
        )

        self.get_logger().info("Ctrl+C recebido: pousando via cmd_full_state")
        self._fly_line(start, end, LANDING_DURATION_SEC)

        for _ in range(max(1, int(LANDING_HOLD_SEC / CONTROL_PERIOD))):
            self._publish_state(end, np.zeros(3))
            time.sleep(CONTROL_PERIOD)

        self.get_logger().info("Pouso por full state finalizado")

    def _wait_for_pose(self) -> None:
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=CONTROL_PERIOD)
            if (
                self.last_pose is not None
                and time.monotonic() - self.last_pose_wall <= POSE_TIMEOUT_SEC
            ):
                return
            self._log_every("pose", f"Aguardando /{ROBOT_NAME}/pose", 2.0)

    def _arm(self) -> None:
        while rclpy.ok() and not self.arm_client.service_is_ready():
            self._log_every("arm_service", "Aguardando /all/arm", 2.0)
            rclpy.spin_once(self, timeout_sec=CONTROL_PERIOD)

        request = Arm.Request()
        request.arm = True
        future = self.arm_client.call_async(request)
        self.get_logger().info("Armando Crazyflie")
        while rclpy.ok() and not future.done():
            rclpy.spin_once(self, timeout_sec=CONTROL_PERIOD)

    def _fly_line(self, start: np.ndarray, end: np.ndarray, duration: float) -> None:
        duration = max(duration, CONTROL_PERIOD)
        steps = max(1, int(duration / CONTROL_PERIOD))
        velocity = (end - start) / duration

        for step in range(steps + 1):
            ratio = step / steps
            point = start + ratio * (end - start)
            self._publish_state(point, velocity)
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(CONTROL_PERIOD)

    def _fly_circle(self, center_xy: np.ndarray, radius: float, laps: int) -> None:
        omega = MAX_SPEED / radius
        duration = laps * 2.0 * math.pi / omega
        steps = max(1, int(duration / CONTROL_PERIOD))

        for step in range(steps + 1):
            theta = 2.0 * math.pi * laps * step / steps
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
            self._publish_state(point, velocity)
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(CONTROL_PERIOD)

    def _fly_square(self, center_xy: np.ndarray, side: float) -> None:
        half = side / 2.0
        z = CONTROL_HEIGHT
        corners = [
            np.array([center_xy[0] + half, center_xy[1], z], dtype=float),
            np.array([center_xy[0] + half, center_xy[1] + half, z], dtype=float),
            np.array([center_xy[0] - half, center_xy[1] + half, z], dtype=float),
            np.array([center_xy[0] - half, center_xy[1] - half, z], dtype=float),
            np.array([center_xy[0] + half, center_xy[1] - half, z], dtype=float),
            np.array([center_xy[0] + half, center_xy[1], z], dtype=float),
            np.array([center_xy[0], center_xy[1], z], dtype=float),
        ]

        for start, end in zip(corners, corners[1:]):
            self._fly_line(start, end, self._duration_for_distance(np.linalg.norm(end - start)))

    def _duration_for_distance(self, distance: float) -> float:
        return max(float(distance) / MAX_SPEED, CONTROL_PERIOD)

    def _publish_state(self, position: np.ndarray, velocity: np.ndarray) -> None:
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
        self.fullstate_pub.publish(msg)

    def _log_every(self, key: str, message: str, period_sec: float) -> None:
        now = time.monotonic()
        attr = f"_last_log_{key}"
        if now - getattr(self, attr, 0.0) >= period_sec:
            setattr(self, attr, now)
            self.get_logger().info(message)


def main(args=None) -> None:
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = ControlValidationNode()
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
