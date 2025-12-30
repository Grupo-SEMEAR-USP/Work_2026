cmake_minimum_required(VERSION 3.0.2)
project(robot_manipulation)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  geometry_msgs               
  robot_communication          
)

###################################
## catkin specific configuration ##
###################################
catkin_package(
  CATKIN_DEPENDS 
    rospy 
    std_msgs 
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

## Mark executable scripts (Python etc.) for installation
catkin_install_python(PROGRAMS
  scripts/gripper_adjust.py
  scripts/manipulation.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)