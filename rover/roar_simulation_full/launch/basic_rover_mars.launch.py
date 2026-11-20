import os
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler, SetEnvironmentVariable, DeclareLaunchArgument, TimerAction
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution, LaunchConfiguration
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    pkg_roar_simulation_full = get_package_share_directory('roar_simulation_full')
    pkg_marsyard = get_package_share_directory('marsyard')

    # 1. Declare Launch Arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )
    use_sim_time = LaunchConfiguration('use_sim_time')

    # 2. SETUP PATHS
    install_dir = os.path.abspath(os.path.join(pkg_roar_simulation_full, '..'))
    world_file = os.path.join(pkg_marsyard, 'worlds', 'marsyard.world')

    resource_paths = [
        install_dir, pkg_roar_simulation_full, pkg_marsyard,
        os.path.join(pkg_marsyard, 'models')
    ]
    if 'GZ_SIM_RESOURCE_PATH' in os.environ and os.environ['GZ_SIM_RESOURCE_PATH']:
        resource_paths.insert(0, os.environ['GZ_SIM_RESOURCE_PATH'])
    gz_resource_path = os.pathsep.join(resource_paths)
    gz_system_plugin_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH'),
        os.path.join(get_package_prefix('gz_ros2_control'), 'lib'),
    )))

    # 3. Process URDF
    xacro_file = os.path.join(pkg_roar_simulation_full, 'urdf', 'roar_complete_sim.urdf.xacro')
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            xacro_file
        ]
    )
    robot_description = {"robot_description": ParameterValue(robot_description_content, value_type=str)}

    # 4. Start Gazebo
    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', '-r', world_file],
        additional_env={
            'GZ_SIM_RESOURCE_PATH': gz_resource_path,
            'GZ_SIM_SYSTEM_PLUGIN_PATH': gz_system_plugin_path,
        },
        output='screen',
    )

    # 5. Robot State Publisher
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim_time}]
    )

    # 6. Spawn Robot
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'marsyard', '-topic', 'robot_description',
                   '-name', 'roar_rover', '-z', '3.0', '-Y', '1.5707'],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 7. Bridge Clock
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 8. Controllers (Removed the 30s timeout arg as the C++ core ignores it anyway)
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster"],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    diff_drive_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["diff_drive_controller"],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    arm_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["arm_controller"],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    return LaunchDescription([
        use_sim_time_arg,
        
        # Set resource paths for Gazebo Harmonic models and plugins
        SetEnvironmentVariable(name='GZ_SIM_RESOURCE_PATH', value=gz_resource_path),
        SetEnvironmentVariable(
            name='GZ_SIM_SYSTEM_PLUGIN_PATH', value=gz_system_plugin_path),
        
        # --- THE FIXES ---
        # 1. Force Qt to use X11 instead of Wayland to prevent the libEGL crash across different machines
        #SetEnvironmentVariable(name='QT_QPA_PLATFORM', value='xcb'),
        
        gazebo,
        bridge,
        node_robot_state_publisher,
        spawn_entity,
        
        # 2. Wait for robot URDF to be sent -> WAIT 12 SECONDS for meshes to render -> Start broadcaster
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=spawn_entity,
                on_exit=[
                    TimerAction(
                        period=12.0, 
                        actions=[joint_state_broadcaster_spawner]
                    )
                ],
            )
        ),
        
        # Wait for joint states -> Start drive controller
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[diff_drive_controller_spawner],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=diff_drive_controller_spawner,
                on_exit=[arm_controller_spawner],
            )
        ),
    ])