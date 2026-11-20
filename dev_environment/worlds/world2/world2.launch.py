import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess

def generate_launch_description():
    world_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(os.path.dirname(world_dir))
    world_path = os.path.join(world_dir, 'world2.world')
    resource_path = os.pathsep.join(filter(None, (
        os.environ.get('GZ_SIM_RESOURCE_PATH'),
        os.path.join(workspace_dir, 'worlds'),
        os.path.join(workspace_dir, 'models'),
        os.path.join(workspace_dir, 'install', 'share'),
    )))
    
    return LaunchDescription([
        ExecuteProcess(
            cmd=['gz', 'sim', '-r', world_path],
            additional_env={'GZ_SIM_RESOURCE_PATH': resource_path},
            output='screen',
        )
    ])
