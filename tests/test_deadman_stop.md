# Deadman Stop Manual Test

1. Launch `mvp_onboard_min.launch.py`
2. Verify `/deadman_state` becomes `HEARTBEAT_OK` when offboard stack is running
3. Stop offboard stack
4. Verify `/deadman_state` changes to `TIMEOUT_STOP`
