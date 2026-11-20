import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable, OpaqueFunction
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration

def _launch_gazebo(context, *args, **kwargs):
    world_name = LaunchConfiguration('world').perform(context)
    
    # Get package directories
    pkg_worlds = get_package_share_directory('worlds')
    
    # Path to the world file
    world_path = os.path.join(pkg_worlds, 'worlds', world_name)
    if not os.path.exists(world_path):
        print(f"[worlds.launch] Error: World file not found at {world_path}")
        # Default fallback
        world_path = os.path.join(pkg_worlds, 'worlds', 'marsyard.world')

    # Construct resource paths for Gazebo to find models (model://)
    resource_paths = []
    
    # 1. Include this worlds package and its consolidated models
    resource_paths.append(pkg_worlds)
    resource_paths.append(os.path.join(pkg_worlds, 'models'))
    resource_paths.append(os.path.join(pkg_worlds, 'models', 'rocks'))
    resource_paths.append(os.path.join(pkg_worlds, 'models', 'aruco'))
    
    # 2. Find marsyard package if available
    try:
        pkg_marsyard = get_package_share_directory('marsyard')
        # marsyard model is inside marsyard/models
        resource_paths.append(os.path.join(pkg_marsyard, 'models'))
    except Exception as e:
        print(f"[worlds.launch] Could not find marsyard package: {e}")
        
    # 3. Find roar_simulation package if available
    try:
        pkg_roar_sim = get_package_share_directory('roar_simulation')
        # Parent of share/roar_simulation (which is install/roar_simulation/share)
        resource_paths.append(os.path.dirname(pkg_roar_sim))
    except Exception as e:
        print(f"[worlds.launch] Could not find roar_simulation package: {e}")

    # 4. Find rock_generator package if available
    try:
        pkg_rock_gen = get_package_share_directory('rock_generator')
        # rock models are under rock_generator/rocks_ws
        resource_paths.append(os.path.join(pkg_rock_gen, 'rocks_ws'))
        # Add parent to resolve package://rock_generator/rocks_ws/ paths
        resource_paths.append(os.path.dirname(pkg_rock_gen))
    except Exception as e:
        print(f"[worlds.launch] Could not find rock_generator package: {e}")



    # Merge with existing environment variables
    gz_existing = os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    gz_path = os.pathsep.join(resource_paths)
    if gz_existing:
        gz_path = gz_path + os.pathsep + gz_existing

    # Bridge for simulator clock so ROS 2 nodes can sync with simulation time
    clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='clock_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )
#prblem
    # Set up Gazebo environment variables directly
    gazebo_env = dict(os.environ)
    gazebo_env['GZ_SIM_RESOURCE_PATH'] = gz_path

    # Launch Gazebo Harmonic without a GUI renderer.
    gazebo_process = ExecuteProcess(
        cmd=['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '4', world_path],
        additional_env=gazebo_env,
        output='screen'
    )

    return [
        gazebo_process,
        clock_bridge
    ]


def generate_launch_description():
    # Declare the world argument
    world_arg = DeclareLaunchArgument(
        'world',
        default_value='marsyard.world',
        description='Name of the world file to load'
    )

    return LaunchDescription([
        world_arg,
        OpaqueFunction(function=_launch_gazebo)
    ])
