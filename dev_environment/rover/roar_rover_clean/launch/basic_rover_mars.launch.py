import os
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler, SetEnvironmentVariable, DeclareLaunchArgument, TimerAction
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution, LaunchConfiguration
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    pkg_roar_rover_clean = get_package_share_directory('roar_rover_clean')
    pkg_marsyard = get_package_share_directory('marsyard')

    # 1. Declare Launch Arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )
    use_sim_time = LaunchConfiguration('use_sim_time')

    # 2. SETUP PATHS
    world_file = os.path.join(pkg_marsyard, 'worlds', 'marsyard.world')
    resource_paths = [
        os.environ.get('GZ_SIM_RESOURCE_PATH', ''),
        os.path.dirname(pkg_roar_rover_clean),
        pkg_roar_rover_clean,
        os.path.join(pkg_marsyard, 'models'),
        pkg_marsyard,
    ]
    gz_resource_path = os.pathsep.join(path for path in resource_paths if path)
    system_plugin_paths = [
        os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH', ''),
        os.path.join(get_package_prefix('gz_ros2_control'), 'lib'),
    ]
    gz_system_plugin_path = os.pathsep.join(
        path for path in system_plugin_paths if path)

    # 3. Process URDF
    xacro_file = os.path.join(
        pkg_roar_rover_clean, 'urdf', 'base', 'rover_simulation_clean.urdf.xacro')
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
        cmd=['gz', 'sim', '-s', '-r', '--headless-rendering', world_file],
        output='screen'
    )
    gazebo_gui = TimerAction(
        period=3.0,
        actions=[ExecuteProcess(
            cmd=['gz', 'sim', '-g'],
            additional_env={'GZ_SIM_RESOURCE_PATH': gz_resource_path},
            output='screen'
        )]
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
        arguments=[
            '-world', 'marsyard', '-topic', 'robot_description',
            '-name', 'roar_rover', '-z', '3.0', '-Y', '1.5707'
        ],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 7. Bridge Clock
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/bno055/data@sensor_msgs/msg/Imu[gz.msgs.IMU',
            '/bno055/mag@sensor_msgs/msg/MagneticField[gz.msgs.Magnetometer',
            '/zed2i/image_raw@sensor_msgs/msg/Image[gz.msgs.Image',
            '/zed2i/depth@sensor_msgs/msg/Image[gz.msgs.Image',
            '/zed2i/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
            '/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
        ],
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

    node_clean_camera = Node(
        package='roar_rover_clean',
        executable='clean_camera_node.py',
        name='clean_camera_node',
        output='screen'
    )

    return LaunchDescription([
        use_sim_time_arg,
        
        # Set resource paths for Gazebo Harmonic models and control plugin.
        SetEnvironmentVariable(name='GZ_SIM_RESOURCE_PATH', value=gz_resource_path),
        SetEnvironmentVariable(
            name='GZ_SIM_SYSTEM_PLUGIN_PATH', value=gz_system_plugin_path),
        
        # --- THE FIXES ---
        # 1. Force Qt to use X11 instead of Wayland to prevent the libEGL crash across different machines
        #SetEnvironmentVariable(name='QT_QPA_PLATFORM', value='xcb'),
        
        gazebo,
        gazebo_gui,
        bridge,
        node_robot_state_publisher,
        spawn_entity,
        node_clean_camera,
        
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
    ])