import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    params = os.path.join(
        get_package_share_directory("shenai_health_scan"), "config", "params.yaml")
    return LaunchDescription([
        Node(package="shenai_health_scan", executable="scan_node",
             name="shenai_health_scan", parameters=[params], output="screen"),
    ])
