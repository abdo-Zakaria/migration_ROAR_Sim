#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_prefix, get_package_share_directory
import os

def generate_launch_description():
    pkg_roar_rover_clean = FindPackageShare('roar_rover_clean')
    pkg_share = get_package_share_directory('roar_rover_clean')
    gz_resource_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_RESOURCE_PATH'),
        os.path.dirname(pkg_share),
        pkg_share,
    )))
    gz_system_plugin_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH'),
        os.path.join(get_package_prefix('gz_ros2_control'), 'lib'),
    )))
    
    x_arg = DeclareLaunchArgument('x', default_value='0.0', description='X position')
    y_arg = DeclareLaunchArgument('y', default_value='0.0', description='Y position')
    z_arg = DeclareLaunchArgument('z', default_value='0.5', description='Z position')
    yaw_arg = DeclareLaunchArgument('yaw', default_value='-1.5708', description='Yaw angle (-90 degrees)')
    
    urdf_file = PathJoinSubstitution([
        pkg_roar_rover_clean,
        'urdf', 'roar_complete_sim.urdf.xacro'
    ])
    
    robot_description = ParameterValue(Command(['xacro ', urdf_file]), value_type=str)
    
    world_file = os.path.join(pkg_share, 'worlds', 'rover_world.sdf')
    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', '-r', world_file],
        additional_env={
            'GZ_SIM_RESOURCE_PATH': gz_resource_path,
            'GZ_SIM_SYSTEM_PLUGIN_PATH': gz_system_plugin_path,
        },
        output='screen',
    )
    
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }]
    )
    
    spawn_entity_node = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_urdf',
        output='screen',
        arguments=[
            '-world', 'rover_world',
            '-name', 'roar_complete',
            '-topic', 'robot_description',
            '-x', LaunchConfiguration('x'),
            '-y', LaunchConfiguration('y'),
            '-z', LaunchConfiguration('z'),
            '-Y', LaunchConfiguration('yaw')
        ]
    )

    clock_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image',
            '/camera/depth@sensor_msgs/msg/Image[gz.msgs.Image',
            '/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
            '/bno055/data@sensor_msgs/msg/Imu[gz.msgs.IMU',
            '/bno055/mag@sensor_msgs/msg/MagneticField[gz.msgs.Magnetometer',
        ],
        output='screen'
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    diff_drive_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_drive_controller'],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    arm_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['arm_controller'],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )
    
    teleop_node = Node(
        package='roar_rover_clean',
        executable='teleop.py',
        name='teleop_node',
        output='screen',
        parameters=[{'use_sim_time': True}],
    )
    
    return LaunchDescription([
        x_arg,
        y_arg,
        z_arg,
        yaw_arg,
        SetEnvironmentVariable(name='GZ_SIM_RESOURCE_PATH', value=gz_resource_path),
        SetEnvironmentVariable(name='GZ_SIM_SYSTEM_PLUGIN_PATH', value=gz_system_plugin_path),
        gazebo,
        robot_state_publisher_node,
        spawn_entity_node,
        clock_bridge_node,
        RegisterEventHandler(
            OnProcessExit(
                target_action=spawn_entity_node,
                on_exit=[joint_state_broadcaster_spawner],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[diff_drive_controller_spawner],
            )
        ),
        RegisterEventHandler(
            OnProcessExit(
                target_action=diff_drive_controller_spawner,
                on_exit=[arm_controller_spawner],
            )
        ),
        teleop_node,
    ])
