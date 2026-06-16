from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    rviz = LaunchConfiguration("rviz")
    use_sim_time = LaunchConfiguration("use_sim_time")

    return LaunchDescription([
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        Node(
            package="control_validation",
            executable="control_validation_node",
            name="control_validation_node",
            output="screen",
            sigterm_timeout="10.0",
            sigkill_timeout="12.0",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="control_validation_rviz",
            output="screen",
            condition=IfCondition(rviz),
            parameters=[{"use_sim_time": use_sim_time}],
        ),
    ])
