#!/bin/bash
function cleanup() {
	pkill -x cf2
	pkill -9 ruby
}

function spawn_model() {
	MODEL=$1
	N=$2 # Cf ID
	X=$3 # spawn x position
	Y=$4 # spawn y position
	X=${X:=$X}
	Y=${Y:=$Y}
	SUPPORTED_MODELS=("crazyflie", "crazyflie_thrust_upgrade")
	if [[ " ${SUPPORTED_MODELS[*]} " != *"$MODEL"* ]];
	then
		echo "ERROR: Currently only vehicle model $MODEL is not supported!"
		echo "       Supported Models: [${SUPPORTED_MODELS[@]}]"
		trap "cleanup" SIGINT SIGTERM EXIT
		exit 1
	fi

	working_dir="$build_path/$n"
	[ ! -d "$working_dir" ] && mkdir -p "$working_dir"

	pushd "$working_dir" &>/dev/null


	set --
	set -- ${@} ${src_path}/tools/crazyflie-simulation/simulator_files/gazebo/launch/jinja_gen.py
	set -- ${@} ${src_path}/tools/crazyflie-simulation/simulator_files/gazebo/models/${MODEL}/model.sdf.jinja
	set -- ${@} ${src_path}/tools/crazyflie-simulation/simulator_files/gazebo
	set -- ${@} --cffirm_udp_port $((19950+${N}))
	set -- ${@} --cflib_udp_port $((19850+${N}))
	set -- ${@} --cf_id $((${N}))
	set -- ${@} --cf_name cf
	set -- ${@} --output-file /tmp/${MODEL}_${N}.sdf

	python3 ${@}

	echo "Spawning ${MODEL}_${N} at ${X} ${Y}"

    gz service -s /world/${gazebo_world_name}/create --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean --timeout 300 --req 'sdf_filename: "/tmp/'${MODEL}_${N}'.sdf", pose: {position: {x:'${X}', y:'${Y}', z: 0.5}}, name: "'${MODEL}_${N}'", allow_renaming: 1'
	
	echo "starting instance $N in $(pwd)"
	$build_path/cf2 $((19950+${N})) > out.log 2> error.log &

	popd &>/dev/null
}

if [ "$1" == "-h" ] || [ "$1" == "--help" ]
then
	echo "Description: This script is used to spawn multiple vehicles in gazebo in a square formation."
	echo "Usage: $0 [-n <num_vehicles>] [-m <vehicle_model>] [-w <world>]"
	exit 1
fi

while getopts n:m:w: option
do
	case "${option}"
	in
		n) NUM_VEHICLES=${OPTARG};;
		m) VEHICLE_MODEL=${OPTARG};;
		w) WORLD=${OPTARG};;
	esac
done

num_vehicles=${NUM_VEHICLES:=3}
world=${WORLD:=/CrazySim/pfc_ws/worlds/coro.world}
target=${TARGET:=cf2}
vehicle_model=${VEHICLE_MODEL:="crazyflie"}
export CF2_SIM_MODEL=gz_${vehicle_model}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
src_path="$SCRIPT_DIR/../../../../.."

build_path=${src_path}/sitl_make/build

if [[ "$world" == /* ]] || [[ "$world" == *.* ]]; then
	world_file="$world"
else
	world_file="${src_path}/tools/crazyflie-simulation/simulator_files/gazebo/worlds/${world}.sdf"
fi

if [ ! -f "$world_file" ]; then
	echo "ERROR: World file not found: $world_file"
	exit 1
fi

gazebo_world_name=$(python3 - "$world_file" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
world = root.find("world")
print(world.attrib.get("name", "default") if world is not None else "default")
PY
)

echo "killing running crazyflie firmware instances"
pkill -x cf2 || true

sleep 1

source ${src_path}/tools/crazyflie-simulation/simulator_files/gazebo/launch/setup_gz.bash ${src_path} ${build_path}

echo "Starting gazebo"
gz sim -s -r "$world_file" -v 0 &
sleep 3

if [ $num_vehicles -gt 255 ]
then
	echo "Tried spawning $num_vehicles vehicles. The maximum number of supported vehicles is 255"
	exit 1
fi
n=0
while [ $n -lt $num_vehicles ]; do
	case $n in
		0)
			x_cord=-1.5
			y_cord=1.2
			;;
		1)
			x_cord=-1.5
			y_cord=0.6
			;;
		2)
			x_cord=-0.9
			y_cord=0.6
			;;
		3)
			x_cord=-0.9
			y_cord=1.2
			;;
		*)
			denom=$(python -c "from math import ceil, sqrt; print(ceil(sqrt($num_vehicles)))")
			x_cord=$(($n%$denom))
			y_cord=$(($n/$denom - ($n%$denom)/$denom))
			;;
	esac
	spawn_model ${vehicle_model} $(($n)) $x_cord $y_cord
	n=$(($n + 1))
done

trap "cleanup" SIGINT SIGTERM EXIT

echo "Starting gazebo gui"
#gdb ruby
gz sim -g
