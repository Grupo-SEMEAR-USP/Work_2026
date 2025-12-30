
(cl:in-package :asdf)

(defsystem "robot_communication-msg"
  :depends-on (:roslisp-msg-protocol :roslisp-utils :geometry_msgs-msg
               :std_msgs-msg
)
  :components ((:file "_package")
    (:file "AprilTagDetection" :depends-on ("_package_AprilTagDetection"))
    (:file "_package_AprilTagDetection" :depends-on ("_package"))
    (:file "AprilTagDetectionArray" :depends-on ("_package_AprilTagDetectionArray"))
    (:file "_package_AprilTagDetectionArray" :depends-on ("_package"))
    (:file "SchedulerCommand" :depends-on ("_package_SchedulerCommand"))
    (:file "_package_SchedulerCommand" :depends-on ("_package"))
    (:file "SchedulerResponse" :depends-on ("_package_SchedulerResponse"))
    (:file "_package_SchedulerResponse" :depends-on ("_package"))
    (:file "encoder_comm" :depends-on ("_package_encoder_comm"))
    (:file "_package_encoder_comm" :depends-on ("_package"))
    (:file "ultrasonic_comm" :depends-on ("_package_ultrasonic_comm"))
    (:file "_package_ultrasonic_comm" :depends-on ("_package"))
    (:file "velocity_comm" :depends-on ("_package_velocity_comm"))
    (:file "_package_velocity_comm" :depends-on ("_package"))
  ))