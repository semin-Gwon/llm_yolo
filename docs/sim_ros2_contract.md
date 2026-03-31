# Isaac Sim 5.1.0 ROS 2 Contract

`llm_yolo` sim MVP uses the Isaac Sim ROS 2 bridge as a generic mobile robot interface.

## Minimum Topics

- `/cmd_vel` (`geometry_msgs/msg/Twist`)
  - `go2_skill_server_sim` publishes velocity commands for `NavigateToPose` and `RotateInPlace`.
- `/odom` (`nav_msgs/msg/Odometry`)
  - `go2_skill_server_sim` uses odometry to decide when a named-place goal is reached.
- `/tf`
  - Reserved for RViz and later Nav2 integration. Not consumed directly by the current MVP backend.
- `/sim/visible_objects` (`std_msgs/msg/String`)
  - Isaac Sim side publishes comma-separated visible object class names, for example `chair,person`.
- `/perception/visible_objects` (`std_msgs/msg/String`)
  - `perception_node_sim` republishes normalized visible objects for `scan_scene`.

## Camera Topics

Camera RGB/depth topics are not consumed in the current MVP. They are deferred until the YOLO phase.

## Named Places

`NavigateToPose` in sim mode resolves target names using:

- `/home/jnu/llm_yolo/configs/sim/sim_named_places.yaml`

Coordinates in that file are initial placeholders and should be aligned with the actual Isaac Sim scene.
