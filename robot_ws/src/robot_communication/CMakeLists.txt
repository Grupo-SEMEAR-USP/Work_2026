cmake_minimum_required(VERSION 3.0.2)
project(robot_communication)

## Find catkin macros and libraries
find_package(catkin REQUIRED COMPONENTS
  rospy
  actionlib_msgs
  std_msgs
  message_generation
  geometry_msgs
  sensor_msgs
)

################################################
## Declare ROS messages, services and actions ##
################################################

## Generate messages in the 'msg' folder
add_message_files(
  FILES
  ultrasonic_comm.msg
  encoder_comm.msg
  velocity_comm.msg
  SchedulerCommand.msg
  SchedulerResponse.msg
  AprilTagDetection.msg
  AprilTagDetectionArray.msg
  manipulation_comm.msg
  ManipulatorCommand.msg
  ContainerDetection.msg
  ContainerDetectionArray.msg
)

add_action_files(FILES MoveSegment.action)

## Generate added messages and services with any dependencies listed here
generate_messages(
  DEPENDENCIES
  actionlib_msgs
  geometry_msgs
  sensor_msgs
  std_msgs
)

###################################
## catkin specific configuration ##
###################################
## The catkin_package macro generates cmake config files for your package
catkin_package(
  CATKIN_DEPENDS 
    message_runtime
    actionlib_msgs
    geometry_msgs
    sensor_msgs
    std_msgs
    rospy
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
  scripts/mqtt_comm.py
  scripts/uart_comm.py
  scripts/reset_usb.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

## Mark other files for installation (e.g. launch and bag files, etc.)
install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)

install(DIRECTORY action/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/action
)

install(DIRECTORY msg/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/msg
)