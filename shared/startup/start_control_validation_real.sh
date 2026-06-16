#!/usr/bin/env bash
set -euo pipefail

SESSION_FILE="${1:-/CrazySim/startup/control_validation_real.yaml}"
SESSION_NAME="$(python3 - "$SESSION_FILE" <<'PY'
from pathlib import Path
import sys

for line in Path(sys.argv[1]).read_text().splitlines():
    stripped = line.strip()
    if stripped.startswith("name:"):
        print(stripped.split(":", 1)[1].strip())
        break
else:
    print("control_validation_real")
PY
)"

if ! command -v tmuxinator >/dev/null 2>&1; then
  echo "tmuxinator is not installed. Rebuild the image or install it with: gem install tmuxinator --no-document" >&2
  exit 1
fi

source_ros_setup() {
  set +u
  source "$1"
  set -u
}

source_ros_setup /opt/ros/humble/setup.bash
if [ -f /CrazySim/crazyswarm2_ws/install/setup.bash ]; then
  source_ros_setup /CrazySim/crazyswarm2_ws/install/setup.bash
fi

if [ -d /CrazySim/pfc_ws/src/control_validation ]; then
  mkdir -p /CrazySim/.colcon/pfc_ws
  (
    cd /CrazySim/pfc_ws
    colcon --log-base /CrazySim/.colcon/pfc_ws/log build --symlink-install \
      --build-base /CrazySim/.colcon/pfc_ws/build \
      --install-base /CrazySim/.colcon/pfc_ws/install \
      --packages-select control_validation
  )
fi

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
fi

if [ -t 0 ] && [ -t 1 ]; then
  tmuxinator start -p "$SESSION_FILE"
else
  tmuxinator start -p "$SESSION_FILE" --no-attach
fi
