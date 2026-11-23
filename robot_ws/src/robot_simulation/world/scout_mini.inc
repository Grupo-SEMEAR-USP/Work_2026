# Definition of the lidar sensor
define scout_laser ranger (
  sensor (
    range [ 0.0  40.0 ] # Obtained using ros2 topic echo /scan --no-arr
    fov 360.0
    samples 723
  )
  color "red"
  size [ 0.05 0.05 0.05 ]
)

# Definition of the Agile Scout Mini robot 
# according to the specification: https://global.agilex.ai/products/scout-mini-r-d-kit?_pos=2&_psq=scout+mini&_ss=e&_v=1.0
define scout_mini position (
  size [0.506 0.355 0.110] 
  origin [0 0 0 0]
  gui_nose 1
  drive "omni"
  scout_laser(pose [ -0.00057135 -0.000014925 -0.011704 0.0 ]) 
)
