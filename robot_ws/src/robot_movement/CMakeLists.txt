cmake_minimum_required(VERSION 3.0.2)
project(robot_movement)

## Find catkin macros and libraries
find_package(catkin REQUIRED COMPONENTS
  roscpp
  std_msgs
  geometry_msgs
  nav_msgs
  tf
  tf2
  tf2_ros
  tf2_geometry_msgs
  robot_communication
  rospy
)

###################################
## catkin specific configuration ##
###################################
catkin_package(
  INCLUDE_DIRS include  # Exporta a pasta 'include'
  # LIBRARIES robot_movement 
  # Lista todas as dependências que outro pacote precisaria se dependesse deste
  CATKIN_DEPENDS 
    roscpp 
    std_msgs 
    geometry_msgs 
    nav_msgs 
    tf 
    tf2 
    tf2_ros 
    tf2_geometry_msgs
    robot_communication
)

###########
## Build ##
###########

## Specify additional locations of header files
include_directories(
  include
  ${catkin_INCLUDE_DIRS}
)

## Declare a C++ executable
add_executable(hw_interface_node src/hw_interface.cpp)

## Specify libraries to link a library or executable target against
target_link_libraries(hw_interface_node
  ${catkin_LIBRARIES}
)

#############
## Install ##
#############

## Mark executables for installation
install(TARGETS hw_interface_node
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

catkin_install_python(PROGRAMS
  scripts/align_block.py
  scripts/align_table.py
  scripts/border_detect.py
  scripts/imu_stable.py
  scripts/move_time.py
  scripts/teste_angular.py
  scripts/teste_linear.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

## Mark other files for installation (e.g. launch and bag files, etc.)
install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)

install(DIRECTORY config/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
)