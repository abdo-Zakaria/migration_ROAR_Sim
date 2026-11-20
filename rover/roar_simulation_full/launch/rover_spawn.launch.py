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
    # Get the install directory for mesh files
    pkg_share = get_package_share_directory('roar_simulation_full')
    gz_resource_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_RESOURCE_PATH'),
        os.path.dirname(pkg_share),
        pkg_share,
    )))
    
    set_gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH', 
        value=gz_resource_path
    )
    set_gz_plugin_path = SetEnvironmentVariable(
        name='GZ_SIM_SYSTEM_PLUGIN_PATH',
        value=os.path.join(get_package_prefix('gz_ros2_control'), 'lib')
    )
    
    # URDF path and processing
    urdf_file = PathJoinSubstitution([pkg_roar_simulation_full, 'urdf', 'base', 'rover_simulation.urdf.xacro'])
    robot_description = ParameterValue(Command(['xacro ', urdf_file]), value_type=str)
    
    # 1. Gazebo Harmonic world
    world_file = os.path.join(pkg_share, 'worlds', 'rover_world.sdf')
    gz_sim = ExecuteProcess(
        cmd=['gz', 'sim', '-r', world_file],
        additional_env={
            'GZ_SIM_RESOURCE_PATH': gz_resource_path,
            'GZ_SIM_SYSTEM_PLUGIN_PATH': os.path.join(
                get_package_prefix('gz_ros2_control'), 'lib'),
        },
        output='screen',
    )
    
    # 2. Robot State Publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
        output='screen'
    )
    
    # 3. Spawn Robot
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'rover_world', '-name', 'roar_rover',
                   '-topic', 'robot_description', '-z', '0.5'],
        output='screen'
    )

    # 4. Bridge (Clock and Basic Topics)
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
        ],
        output='screen'
    )
    
    return LaunchDescription([
        set_gz_resource_path,
        set_gz_plugin_path,
        gz_sim,
        robot_state_publisher,
        spawn_entity,
        bridge
    ])
