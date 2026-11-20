import os
from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, RegisterEventHandler,
    TimerAction
)
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution, LaunchConfiguration
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    pkg_roar_rover_noise = get_package_share_directory('roar_rover_noise')

    # ── 1. Launch Arguments ───────────────────────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation (Gazebo) clock if true')
    start_rviz_arg = DeclareLaunchArgument(
        'start_rviz', default_value='false',
        description='Start RViz after controllers are ready')
    use_sim_time = LaunchConfiguration('use_sim_time')
    start_rviz   = LaunchConfiguration('start_rviz')
    world_file_arg = DeclareLaunchArgument(
        'world_file',
        default_value=os.path.join(
            pkg_roar_rover_noise, 'worlds', 'rover_world.sdf'),
        description='Gazebo world file')
    world_file = LaunchConfiguration('world_file')
    spawn_x_arg = DeclareLaunchArgument('spawn_x', default_value='8.0')
    spawn_y_arg = DeclareLaunchArgument('spawn_y', default_value='-3.75')
    spawn_z_arg = DeclareLaunchArgument('spawn_z', default_value='2.196248')
    spawn_x = LaunchConfiguration('spawn_x')
    spawn_y = LaunchConfiguration('spawn_y')
    spawn_z = LaunchConfiguration('spawn_z')

    # ── 2. Resource paths ─────────────────────────────────────────────────────
    install_dir      = os.path.abspath(os.path.join(pkg_roar_rover_noise, '..'))
    gz_resource_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_RESOURCE_PATH'),
        install_dir,
        pkg_roar_rover_noise,
    )))
    gz_system_plugin_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH'),
        os.path.join(get_package_prefix('gz_ros2_control'), 'lib'),
    )))

    # ── 3. URDF / robot_description ──────────────────────────────────────────
    xacro_file = os.path.join(
        pkg_roar_rover_noise, 'urdf', 'base', 'rover_simulation.urdf.xacro')
    robot_description_content = Command([
        PathJoinSubstitution([FindExecutable(name='xacro')]), ' ', xacro_file
    ])
    robot_description = {
        'robot_description': ParameterValue(robot_description_content, value_type=str)
    }

    # ── 4. World file ─────────────────────────────────────────────────────────
    # ── 5. Gazebo SERVER (headless) ───────────────────────────────────────────
    server_env = {
        'GZ_SIM_RESOURCE_PATH':     gz_resource_path,
        'GZ_SIM_SYSTEM_PLUGIN_PATH': gz_system_plugin_path,
    }
    gazebo_server = ExecuteProcess(
        cmd=['gz', 'sim', '-s', '-r', '--headless-rendering', world_file],
        additional_env=server_env,
        output='screen'
    )

    # ── 6. Gazebo GUI CLIENT (hardware GPU) ───────────────────────────────────
    # Launched 3 s after the server so the server is ready to accept a GUI
    # connection. Uses your real AMD/Intel GPU — no software rendering here.
    client_env = {
        'QT_QPA_PLATFORM':          'xcb',
        'GZ_SIM_RESOURCE_PATH':     gz_resource_path,
    }
    gazebo_gui = TimerAction(
        period=3.0,
        actions=[ExecuteProcess(
            cmd=['gz', 'sim', '-g'],
            additional_env=client_env,
            output='screen'
        )]
    )

    # ── 7. Robot State Publisher ──────────────────────────────────────────────
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim_time}]
    )

    # ── 8. Spawn Robot ────────────────────────────────────────────────────────
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'rover_world', '-topic', 'robot_description',
                   '-name', 'roar_rover', '-x', spawn_x, '-y', spawn_y,
                   '-z', spawn_z, '-Y', '1.5707'],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # ── 8.1 Spawn Sun Marker ──────────────────────────────────────────────────
    sun_marker_file = os.path.join(pkg_roar_rover_noise, 'worlds', 'sun_marker.sdf')
    spawn_sun = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'rover_world', '-file', sun_marker_file,
                   '-name', 'sun_marker', 
                   '-x', '0.0', '-y', '10.0', '-z', '2.0'],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # ── 9. ROS↔Gazebo bridge ─────────────────────────────────────────────────
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
            '/world/rover_world/pose/info@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
                        '/world/rover_world/model/roar_rover/link/base_footprint/sensor/base_link_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
            '/world/rover_world/model/roar_rover/link/wheel_lhs_front/sensor/wheel_lhs_front_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
            '/world/rover_world/model/roar_rover/link/wheel_lhs_mid/sensor/wheel_lhs_mid_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
            '/world/rover_world/model/roar_rover/link/wheel_lhs_rear/sensor/wheel_lhs_rear_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
            '/world/rover_world/model/roar_rover/link/wheel_rhs_front/sensor/wheel_rhs_front_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
            '/world/rover_world/model/roar_rover/link/wheel_rhs_mid/sensor/wheel_rhs_mid_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
            '/world/rover_world/model/roar_rover/link/wheel_rhs_rear/sensor/wheel_rhs_rear_contact/contact@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts',
        ],
        output='screen',
                remappings=[
            ('/world/rover_world/model/roar_rover/link/base_footprint/sensor/base_link_contact/contact', '/rover_contact'),
            ('/world/rover_world/model/roar_rover/link/wheel_lhs_front/sensor/wheel_lhs_front_contact/contact', '/rover_contact'),
            ('/world/rover_world/model/roar_rover/link/wheel_lhs_mid/sensor/wheel_lhs_mid_contact/contact', '/rover_contact'),
            ('/world/rover_world/model/roar_rover/link/wheel_lhs_rear/sensor/wheel_lhs_rear_contact/contact', '/rover_contact'),
            ('/world/rover_world/model/roar_rover/link/wheel_rhs_front/sensor/wheel_rhs_front_contact/contact', '/rover_contact'),
            ('/world/rover_world/model/roar_rover/link/wheel_rhs_mid/sensor/wheel_rhs_mid_contact/contact', '/rover_contact'),
            ('/world/rover_world/model/roar_rover/link/wheel_rhs_rear/sensor/wheel_rhs_rear_contact/contact', '/rover_contact'),
        ],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # ── 10. Controllers ───────────────────────────────────────────────────────
    joint_state_broadcaster_spawner = Node(
        package='controller_manager', executable='spawner',
        arguments=['joint_state_broadcaster'],
        parameters=[{'use_sim_time': use_sim_time}]
    )
    diff_drive_controller_spawner = Node(
        package='controller_manager', executable='spawner',
        arguments=['diff_drive_controller'],
        parameters=[{'use_sim_time': use_sim_time}]
    )


    # ── 11. RViz (optional, delayed) ─────────────────────────────────────────
    rviz_config_file = os.path.join(pkg_roar_rover_noise, 'rviz', 'basic_rover.rviz')
    rviz_args = ['-d', rviz_config_file] if os.path.exists(rviz_config_file) else []
    node_rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2',
        output='screen', arguments=rviz_args,
        parameters=[{'use_sim_time': use_sim_time}],
        additional_env={'QT_QPA_PLATFORM': 'xcb'},
        condition=IfCondition(start_rviz),
    )
    # ── 12. Custom Noise & Telemetry Nodes ────────────────────────────────────
    node_zed_noise = Node(
        package='roar_rover_noise',
        executable='zed_degradation_node.py',
        name='zed_degradation_node',
        output='screen'
    )
    
    node_encoder_sim = Node(
        package='roar_rover_noise',
        executable='encoder_sim_node.py',
        name='encoder_sim_node',
        output='screen'
    )

    node_collision_alarm = Node(
        package='roar_rover_noise',
        executable='collision_alarm_node.py',
        name='collision_alarm_node',
        output='screen'
    )

    return LaunchDescription([
        use_sim_time_arg,
        start_rviz_arg,
        world_file_arg,
        spawn_x_arg,
        spawn_y_arg,
        spawn_z_arg,

        # Gazebo server (headless, software GL for sensors)
        gazebo_server,
        # Gazebo GUI (hardware GPU, delayed 3 s to let server start)
        gazebo_gui,

        node_robot_state_publisher,
        bridge,
        spawn_entity,
        spawn_sun,
        node_encoder_sim,
        node_zed_noise,
        node_collision_alarm,

        # Wait for spawn → wait 12 s → start joint state broadcaster
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=spawn_entity,
                on_exit=[TimerAction(
                    period=12.0,
                    actions=[joint_state_broadcaster_spawner]
                )]
            )
        ),

        # Joint broadcaster done → start diff_drive controller
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[diff_drive_controller_spawner]
            )
        ),

        # Diff drive done → start RViz (after 10 s cooldown)
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=diff_drive_controller_spawner,
                on_exit=[TimerAction(period=10.0, actions=[node_rviz])]
            )
        ),
    ])