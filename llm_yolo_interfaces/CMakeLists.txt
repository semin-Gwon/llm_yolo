cmake_minimum_required(VERSION 3.8)
project(llm_yolo_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Intent.msg"
  "action/ApproachObject.action"
  "action/NavigateToPose.action"
  "action/RotateInPlace.action"
  "action/ScanScene.action"
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
