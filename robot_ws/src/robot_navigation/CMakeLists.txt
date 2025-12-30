cmake_minimum_required(VERSION 3.0.2)
project(robot_navigation)

## Compile as C++11, supported in ROS Kinetic and newer
add_compile_options(-std=c++11)

## Find catkin macros and libraries
find_package(catkin REQUIRED COMPONENTS
  actionlib
  actionlib_msgs
  base_local_planner
  costmap_2d
  geometry_msgs
  move_base
  move_base_msgs
  nav_core
  nav_msgs
  pluginlib
  roscpp
  rospy
  std_msgs
  tf
  robot_communication
)

catkin_package(
  CATKIN_DEPENDS 
    actionlib
    actionlib_msgs
    base_local_planner
    costmap_2d
    geometry_msgs
    move_base
    move_base_msgs
    nav_core
    nav_msgs
    pluginlib
    roscpp
    rospy
    std_msgs
    tf
    robot_communication
)

###########
## Build ##
###########

include_directories(
  ${catkin_INCLUDE_DIRS}
)

#############
## Install ##
#############

# Instalação de Scripts Python
catkin_install_python(PROGRAMS
  scripts/navigation.py
  scripts/waypoint_saver.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

# Instalação das pastas de configuração
install(DIRECTORY launch config maps rviz
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)