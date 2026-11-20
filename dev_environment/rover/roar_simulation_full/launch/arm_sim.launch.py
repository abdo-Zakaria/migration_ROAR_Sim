#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_prefix, get_package_share_directory
import os

def generate_launch_description():
    pkg_roar_simulation_full = FindPackageShare('roar_simulation_full')
    pkg_share = get_package_share_directory('roar_simulation_full')
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
    z_arg = DeclareLaunchArgument('z', default_value='0.0', description='Z position')
    yaw_arg = DeclareLaunchArgument('yaw', default_value='0.0', description='Yaw angle')
    
    urdf_file = PathJoinSubstitution([
        pkg_roar_simulation_full,
        'urdf', 'arm', 'arm_simulation.urdf.xacro'
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
        parameters=[{'robot_description': robot_description}]
    )
    
    spawn_entity_node = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_urdf',
        output='screen',
        arguments=[
            '-world', 'rover_world',
            '-name', 'roar_arm',
            '-topic', 'robot_description',
            '-x', LaunchConfiguration('x'),
            '-y', LaunchConfiguration('y'),
            '-z', LaunchConfiguration('z'),
            '-Y', LaunchConfiguration('yaw')
        ]
    )
    
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen'
    )
    
    return LaunchDescription([
        x_arg,
        y_arg,
        z_arg,
        yaw_arg,
        SetEnvironmentVariable(name='GZ_SIM_RESOURCE_PATH', value=gz_resource_path),
        SetEnvironmentVariable(
            name='GZ_SIM_SYSTEM_PLUGIN_PATH', value=gz_system_plugin_path),
        gazebo,
        robot_state_publisher_node,
        spawn_entity_node,
        joint_state_publisher_node,
    ])
