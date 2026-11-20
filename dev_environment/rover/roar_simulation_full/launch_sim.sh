#!/usr/bin/env bash
# =============================================================================
# launch_sim.sh - Clean launch script for roar_simulation_full
# Usage:  bash launch_sim.sh [rviz]
# =============================================================================
set -e

# Find the workspace root automatically (assuming this script is in src/package/)
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# ── 1. Source the workspace ───────────────────────────────────────────────────
if [[ ! -f "$WORKSPACE_DIR/install/setup.bash" ]]; then
    echo "[launch_sim] ERROR: install/setup.bash not found."
    echo "             Run 'colcon build' from $WORKSPACE_DIR first."
    exit 1
fi
source "$WORKSPACE_DIR/install/setup.bash"

# ── 2. Kill stale Gazebo / gz processes and ROS2 nodes ───────────────────────
echo "[launch_sim] Killing any stale Gazebo/ROS2 processes..."
pkill -9 -f "gz sim"  2>/dev/null || true
pkill -9 -x "rviz2" 2>/dev/null || true
pkill -9 -x "rviz" 2>/dev/null || true
pkill -9 -f "robot_state_publisher" 2>/dev/null || true
pkill -9 -f "spawner" 2>/dev/null || true
pkill -9 -f "ros2" 2>/dev/null || true
pkill -9 -f "zed_degradation_node" 2>/dev/null || true
pkill -9 -f "encoder_sim_node" 2>/dev/null || true
pkill -9 -f "clean_camera_node" 2>/dev/null || true
pkill -9 -f "ros_gz_bridge" 2>/dev/null || true
pkill -9 -f "teleop" 2>/dev/null || true
pkill -9 -x "gazebo" 2>/dev/null || true
killall -9 gz rviz2 gzserver gzclient ruby gazebo 2>/dev/null || true
sleep 1   

# ── 3. Clean stale FastDDS shared-memory ports ───────────────────────────────
echo "[launch_sim] Cleaning stale FastDDS shared memory..."
rm -f /dev/shm/fastrtps_port* 2>/dev/null || true
rm -f /tmp/.gz_sim_*      2>/dev/null || true

# ── 4. Set environment BEFORE any child process is forked ────────────────────
export QT_QPA_PLATFORM=xcb

INSTALL_DIR="$WORKSPACE_DIR/install"
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:+$GZ_SIM_RESOURCE_PATH:}$INSTALL_DIR"

# ── 5. Launch ─────────────────────────────────────────────────────────────────
START_RVIZ="false"
if [[ "$1" == "rviz" ]]; then
    START_RVIZ="true"
fi

echo "[launch_sim] Launching roar_simulation_full simulation..."
exec ros2 launch roar_simulation_full basic_rover.launch.py start_rviz:=$START_RVIZ
