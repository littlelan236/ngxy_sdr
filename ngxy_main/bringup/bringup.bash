export PYTHONPATH=/usr/lib/python3/dist-packages/:$PYTHONPATH
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
KEEP_LV1_ARGS=()
for arg in "$@"; do
	if [ "$arg" = "--keep-lv1" ]; then
		KEEP_LV1_ARGS+=("--keep-lv1")
		break
	fi
done

/home/ubuntu/radar2026/radio26/.venv/bin/python /home/ubuntu/radar2026/radio26/ngxy_main/main_gnuradio.py "${KEEP_LV1_ARGS[@]}"