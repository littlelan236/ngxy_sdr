# AGENTS.md

## What this is

RoboMaster 2026 wireless communication subsystem. SDR hardware (PlutoSDR) receives/transmits over-the-air frames via GNU Radio, decodes them in Python, and publishes results over ROS2. Three PlutoSDRs: signal RX, jamming RX, backup.

## Key entrypoints

- `ngxy_main/main_gnuradio.py` — production entry. Multi-process: spawns one GRC flowgraph per SDR board, ZMQ bridges to decoder threads, ROS2 publishes results.
- `ngxy_main/grc_main.py` — GRC flowgraph wrapper. Each flowgraph runs in its own `multiprocessing.Process`. `top_thread_wrapper` is the API used by main.
- `ngxy_main/debug/transmit_test_pluto.py` — standalone TX test script.

## Running scripts

Always run from the workspace root (`ngxy_sdr/`), not from subdirectories:

```
python -m ngxy_main.debug.transmit_test_pluto
# or
python ngxy_main/debug/transmit_test_pluto.py
```

Direct execution of scripts inside `ngxy_main/` subdirectories will fail with `ModuleNotFoundError: No module named 'ngxy_main'` unless the script adds the workspace root to `sys.path` (some do, some don't).

## Python path

Python 3.10+ required (uses `X | None` union syntax, `match` patterns absent but PEP 604 annotations throughout). The project is NOT a pip-installable package — no `setup.py` or `pyproject.toml`. All imports are relative to workspace root on `sys.path`.

## Framework & hardware dependencies

- `gnuradio` (3.10.x) — flowgraph runtime
- `adi` (libiio/PlutoSDR bindings) + `rtlsdr` — SDR hardware control
- `rclpy` — ROS2 Python client
- `zmq` — inter-process communication between GRC subprocesses and main
- Linux-only runtime: `iio_info` CLI tool, USB device enumeration. Dev may happen on Windows but the app runs on Ubuntu.

## Architecture

```
PlutoSDR HW
  → GRC subprocess (Pluto IIO Source → LPF → FM demod → Symbol Sync → Hard Decision → pack_bits)
    → ZMQ PUB (tcp://127.0.0.1:2236 for signal, :2235 for jamming)
      → frame_decoder_zmq (SUB → bit sync → OTA frame extract → serial frame decode → CRC check)
        → callback → main loop ros_publish_queue → ROS2 publish
```

TX path: `frame_coder` builds OTA frames as bitstream → `zmqServerTx` PUBs → external GRC TX flowgraph SUBs.

## Frame protocol (two layers)

**OTA frame**: 8-byte access code + 2×2-byte length + 15-byte payload. Two access codes: `ACCESS_CODE_SIGNAL` (0x2F6F4C74...) and `ACCESS_CODE_JAMMING` (0x16E8D377...).

**Serial frame** (inside OTA payload): SOF(0xA5) + data_length(2B) + seq(1B) + CRC8(1B) + cmd_id(2B) + data + CRC16(2B). Little-endian for header/data, big-endian for OTA access codes.

Defined in `ngxy_main/defs/def_frame.py`. Six command types: `enemy_pos`, `enemy_hp`, `enemy_ammo`, `buff_state`, `gains`, `jamming`.

## Conventions

- **No comments** in code unless explicitly asked. The codebase has very few comments.
- **Logging**: use `ngxy_main.drivers.util._log()` which does both `logging.log()` and `print()`.
- **File paths**: `_makesure_path_exist()` from `util.py` for log/rec directories.
- **Recording**: IQ files saved to `rec/` directory, auto-created.
- **Constants**: all RF parameters, filter taps, frame definitions live under `ngxy_main/defs/`.
- **Device serials**: hardcoded in `ngxy_main/drivers/extract_usb.py` — these are physical USB serial numbers of the PlutoSDR boards.

## Gotchas

- `main_gnuradio.py` imports `from wireless_ros2_adaptor import ...` — this file at `ngxy_main/drivers/wireless_ros2_adaptor.py` only contains a remote path reference; the actual module lives on the deployment Ubuntu machine at `/home/ubuntu/radar2026/radarvisual26-pyside/driver/`. It will fail on Windows dev.
- GRC subprocesses can crash silently. The main loop monitors process liveness and auto-restarts with backup device failover.
- `BW_SIG /= 2` etc. in `main_gnuradio.py:99-102` — bandwidth values are halved at import time for GRC filter parameters.
- `grc_main.py` imports `grc_hard_decision_block` as a top-level name (not relative) — requires `ngxy_main/` on `sys.path`.
- ZMQ addresses: signal=`tcp://127.0.0.1:2236`, jamming=`tcp://127.0.0.1:2235`, TX test=`tcp://127.0.0.1:2234`.

## Deployment

Target machine: Ubuntu at `/home/ubuntu/radar2026/radio26/`. Startup via `ngxy_main/bringup/bringup.bash`. ROS2 workspace sourced from `detectorcppside26`.
