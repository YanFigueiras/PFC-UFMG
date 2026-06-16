from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    rviz = LaunchConfiguration("rviz")
    rviz_config = PathJoinSubstitution([
        FindPackageShare("drbecm_coro"),
        "config",
        "drbecm_coro.rviz",
    ])

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("rviz", default_value="true"),
        Node(
            package="drbecm_coro",
            executable="drbecm_node",
            name="drbecm_node",
            output="screen",
            parameters=[{"use_sim_time": use_sim_time}],
            sigterm_timeout="10.0",
            sigkill_timeout="12.0",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="drbecm_rviz",
            arguments=["-d", rviz_config],
            output="screen",
            condition=IfCondition(rviz),
            parameters=[{"use_sim_time": use_sim_time}],
        ),
    ])
