import time
from typing import Dict, List, Optional

import numpy as np
import rclpy
from builtin_interfaces.msg import Duration
from crazyflie_interfaces.msg import FullState
from crazyflie_interfaces.srv import Arm, Takeoff
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import String
from visualization_msgs.msg import MarkerArray

from drbecm_coro.algorithm import BASE_POSITION, DRBECMAlgorithm, ROBOT_NAMES
from drbecm_coro.metrics import MetricsTracker
from drbecm_coro.visualization import make_map, make_markers


# =============================================================================
# Global ROS/control configuration
# =============================================================================

FRAME_ID = "world"

CONTROL_HEIGHT = 1.00
PLANNING_PERIOD = 0.20     # 5 Hz planning
CONTROL_PERIOD = 0.05      # 20 Hz control
POSE_TIMEOUT_SEC = 2.0

AUTO_ARM_AND_TAKEOFF = True
TAKEOFF_DURATION_SEC = 4
TAKEOFF_HOLD_SEC = 4.0
LANDING_DURATION_SEC = 4.0
LANDING_FINAL_HEIGHT = 0.05
LANDING_HOLD_SEC = 0.75

MAX_SPEED = 0.15           # m/s
MAX_ACCELERATION = 0.05    # m/s²

BASE_ROBOT_INDEX = 0
BASE_ROBOT_NAME = ROBOT_NAMES[BASE_ROBOT_INDEX]


class DRBECMNode(Node):
    """ROS 2 adapter for the DRBECM algorithm.

    Algorithm state is kept in DRBECMAlgorithm. This node only does transport:
    pose subscriptions, Crazyflie publishers and visualization publications.
    """

    def __init__(self) -> None:
        super().__init__("drbecm_node")

        self.algorithm = DRBECMAlgorithm()
        self.metrics = MetricsTracker()
        self.last_pose_wall: Dict[str, float] = {}
        self.last_pose_xyz: Dict[str, np.ndarray] = {}
        self.phase = "WAIT_FOR_POSES"
        self.phase_started_wall = time.monotonic()
        self.arm_future = None
        self.takeoff_future = None
        self.last_log_wall: Dict[str, float] = {}

        self._last_targets: List[Optional[np.ndarray]] = [None] * len(ROBOT_NAMES)
        self._last_positions: List[Optional[np.ndarray]] = [None] * len(ROBOT_NAMES)
        self._velocities: Dict[str, np.ndarray] = {
            name: np.zeros(2) for name in ROBOT_NAMES
        }
        self._planning_wall = 0.0

        self.pose_subs = [
            self.create_subscription(
                PoseStamped,
                f"/{name}/pose",
                lambda msg, robot_name=name: self._pose_cb(msg, robot_name),
                10,
            )
            for name in ROBOT_NAMES
        ]

        self.arm_client = self.create_client(Arm, "/all/arm")
        self.takeoff_client = self.create_client(Takeoff, "/all/takeoff")
        self.fullstate_pubs = {
            name: self.create_publisher(FullState, f"/{name}/cmd_full_state", 1)
            for name in ROBOT_NAMES
        }

        self.map_pub = self.create_publisher(OccupancyGrid, "/drbecm/map", 1)
        self.markers_pub = self.create_publisher(MarkerArray, "/drbecm/markers", 1)
        self.metrics_pub = self.create_publisher(String, "/drbecm/metrics", 1)

        self.create_timer(CONTROL_PERIOD, self._loop)
        self.get_logger().info(
            "DRBECM pronto: aguardando poses em "
            + ", ".join(f"/{name}/pose" for name in ROBOT_NAMES)
            + f"; base {BASE_ROBOT_NAME} com alvo fixo em "
            + f"({BASE_POSITION[0]:.2f}, {BASE_POSITION[1]:.2f})"
        )

    def _pose_cb(self, msg: PoseStamped, robot_name: str) -> None:
        xy = np.array([msg.pose.position.x, msg.pose.position.y], dtype=float)
        xyz = np.array(
            [msg.pose.position.x, msg.pose.position.y, msg.pose.position.z],
            dtype=float,
        )
        self.algorithm.update_pose(robot_name, xy)
        self.last_pose_xyz[robot_name] = xyz
        self.last_pose_wall[robot_name] = time.monotonic()

    def _loop(self) -> None:
        stamp = self.get_clock().now().to_msg()
        now = time.monotonic()

        if not self._poses_ready():
            self._publish_snapshot(stamp, self.algorithm.last_snapshot)
            missing = [name for name in ROBOT_NAMES if name not in self.last_pose_wall]
            self._log_every("poses", f"Aguardando poses dos drones: {missing}", 3.0)
            return

        # Planning tick at lower frequency
        if now - self._planning_wall >= PLANNING_PERIOD:
            self._planning_wall = now
            snapshot = self.algorithm.step()
            self._publish_snapshot(stamp, snapshot)
            self._last_targets = list(snapshot.targets)
            self._last_positions = list(snapshot.positions)

            if AUTO_ARM_AND_TAKEOFF and self.phase != "EXPLORING":
                self._startup_sequence()
                return

            self.phase = "EXPLORING"
        elif AUTO_ARM_AND_TAKEOFF and self.phase != "EXPLORING":
            self._startup_sequence()
            return

        if self.phase == "EXPLORING":
            self._send_targets(self._last_targets, self._last_positions)

    def _startup_sequence(self) -> None:
        now = time.monotonic()

        if self.phase == "WAIT_FOR_POSES":
            self.phase = "ARMING"
            self.phase_started_wall = now

        if self.phase == "ARMING":
            if not self.arm_client.service_is_ready():
                self._log_every("arm_service", "Aguardando /all/arm", 3.0)
                return
            if self.arm_future is None:
                request = Arm.Request()
                request.arm = True
                self.arm_future = self.arm_client.call_async(request)
                self.get_logger().info("Armando todos os Crazyflies")
                return
            if not self.arm_future.done():
                return
            self.phase = "TAKING_OFF"
            self.phase_started_wall = now

        if self.phase == "TAKING_OFF":
            if not self.takeoff_client.service_is_ready():
                self._log_every("takeoff_service", "Aguardando /all/takeoff", 3.0)
                return
            if self.takeoff_future is None:
                request = Takeoff.Request()
                request.group_mask = 0
                request.height = float(CONTROL_HEIGHT)
                request.duration = _duration(TAKEOFF_DURATION_SEC)
                self.takeoff_future = self.takeoff_client.call_async(request)
                self.get_logger().info(f"Decolando para {CONTROL_HEIGHT:.2f} m")
                return
            if not self.takeoff_future.done():
                return
            self.phase = "HOLDING"
            self.phase_started_wall = now

        if self.phase == "HOLDING":
            if now - self.phase_started_wall < TAKEOFF_HOLD_SEC:
                self._log_every("holding", "Estabilizando antes de explorar", 2.0)
                return
            self.phase = "EXPLORING"
            self.get_logger().info("Iniciando exploração DRBECM")

    def _send_targets(
        self,
        targets: List[Optional[np.ndarray]],
        positions: List[Optional[np.ndarray]],
    ) -> None:
        dt = CONTROL_PERIOD
        for index, (target, position) in enumerate(zip(targets, positions)):
            if position is None:
                continue

            name = ROBOT_NAMES[index]
            if index == BASE_ROBOT_INDEX:
                target = BASE_POSITION.copy()
            elif target is None:
                continue

            diff = np.array([target[0] - position[0], target[1] - position[1]])
            dist = float(np.linalg.norm(diff))

            if dist > 1e-6:
                desired_vel = diff / dist * min(MAX_SPEED, dist)
            else:
                desired_vel = np.zeros(2)

            # Acceleration-limited velocity update (same model as metrics_Flocking_inspired.py)
            v = self._velocities[name]
            accel = (desired_vel - v) / dt
            accel_norm = float(np.linalg.norm(accel))
            if accel_norm > MAX_ACCELERATION:
                accel = accel / accel_norm * MAX_ACCELERATION
            v = v + accel * dt
            v_norm = float(np.linalg.norm(v))
            if v_norm > MAX_SPEED:
                v = v / v_norm * MAX_SPEED
            self._velocities[name] = v

            msg = FullState()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = FRAME_ID
            msg.pose.position.x = float(target[0])
            msg.pose.position.y = float(target[1])
            msg.pose.position.z = float(CONTROL_HEIGHT)
            msg.pose.orientation.w = 1.0
            msg.twist.linear.x = float(v[0])
            msg.twist.linear.y = float(v[1])
            msg.twist.linear.z = 0.0
            self.fullstate_pubs[name].publish(msg)

    def land_with_full_state(self) -> None:
        active_names = [
            name for name in ROBOT_NAMES
            if name in self.last_pose_xyz
        ]
        if not active_names:
            self.get_logger().info("Sem poses recebidas; pouso por full state ignorado")
            return

        self.phase = "LANDING"
        self.get_logger().info("Ctrl+C recebido: pousando via cmd_full_state")

        start_poses = {
            name: self.last_pose_xyz[name].copy()
            for name in active_names
        }
        period = CONTROL_PERIOD
        steps = max(1, int(LANDING_DURATION_SEC / period))

        for step in range(steps + 1):
            ratio = step / steps
            for name in active_names:
                start = start_poses[name]
                start_z = max(float(start[2]), LANDING_FINAL_HEIGHT)
                z = start_z + ratio * (LANDING_FINAL_HEIGHT - start_z)
                vz = (LANDING_FINAL_HEIGHT - start_z) / LANDING_DURATION_SEC
                self.fullstate_pubs[name].publish(
                    self._make_full_state(
                        float(start[0]),
                        float(start[1]),
                        z,
                        0.0,
                        0.0,
                        vz,
                    )
                )
            time.sleep(period)

        hold_steps = max(1, int(LANDING_HOLD_SEC / period))
        for _ in range(hold_steps):
            for name in active_names:
                start = start_poses[name]
                self.fullstate_pubs[name].publish(
                    self._make_full_state(
                        float(start[0]),
                        float(start[1]),
                        LANDING_FINAL_HEIGHT,
                        0.0,
                        0.0,
                        0.0,
                    )
                )
            time.sleep(period)

        self.get_logger().info("Pouso por full state finalizado")

    def _make_full_state(
        self,
        x: float,
        y: float,
        z: float,
        vx: float,
        vy: float,
        vz: float,
    ) -> FullState:
        msg = FullState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = FRAME_ID
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = z
        msg.pose.orientation.w = 1.0
        msg.twist.linear.x = vx
        msg.twist.linear.y = vy
        msg.twist.linear.z = vz
        return msg

    def _poses_ready(self) -> bool:
        now = time.monotonic()
        return all(
            name in self.last_pose_wall and now - self.last_pose_wall[name] <= POSE_TIMEOUT_SEC
            for name in ROBOT_NAMES
        )

    def _publish_snapshot(self, stamp, snapshot) -> None:
        self.map_pub.publish(make_map(snapshot, stamp, FRAME_ID))
        self.markers_pub.publish(make_markers(snapshot, stamp, FRAME_ID))
        sample = self.metrics.update(snapshot, time.monotonic())
        self.metrics_pub.publish(String(data=self.metrics.to_json(sample)))

    def _log_every(self, key: str, message: str, period_sec: float) -> None:
        now = time.monotonic()
        if now - self.last_log_wall.get(key, 0.0) >= period_sec:
            self.last_log_wall[key] = now
            self.get_logger().info(message)


def _duration(seconds: float) -> Duration:
    sec = int(seconds)
    nanosec = int((seconds - sec) * 1_000_000_000)
    return Duration(sec=sec, nanosec=nanosec)


def main(args=None) -> None:
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = DRBECMNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.land_with_full_state()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
