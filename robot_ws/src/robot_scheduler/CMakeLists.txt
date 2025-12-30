cmake_minimum_required(VERSION 3.0.2)
project(robot_scheduler)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  robot_communication
)

catkin_package(
  CATKIN_DEPENDS message_runtime rospy std_msgs geometry_msgs robot_communication
)

include_directories(
  ${catkin_INCLUDE_DIRS}
)

catkin_install_python(PROGRAMS
  scripts/scheduler.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)