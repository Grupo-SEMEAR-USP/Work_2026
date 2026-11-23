;; Auto-generated. Do not edit!


(when (boundp 'robot_communication::manipulation_comm)
  (if (not (find-package "ROBOT_COMMUNICATION"))
    (make-package "ROBOT_COMMUNICATION"))
  (shadow 'manipulation_comm (find-package "ROBOT_COMMUNICATION")))
(unless (find-package "ROBOT_COMMUNICATION::MANIPULATION_COMM")
  (make-package "ROBOT_COMMUNICATION::MANIPULATION_COMM"))

(in-package "ROS")
;;//! \htmlinclude manipulation_comm.msg.html


(defclass robot_communication::manipulation_comm
  :super ros::object
  :slots (_base_angle_deg _base_angle_rad _upper_limit_active _encoder_valid _manip_feedback ))

(defmethod robot_communication::manipulation_comm
  (:init
   (&key
    ((:base_angle_deg __base_angle_deg) 0.0)
    ((:base_angle_rad __base_angle_rad) 0.0)
    ((:upper_limit_active __upper_limit_active) 0)
    ((:encoder_valid __encoder_valid) 0)
    ((:manip_feedback __manip_feedback) 0)
    )
   (send-super :init)
   (setq _base_angle_deg (float __base_angle_deg))
   (setq _base_angle_rad (float __base_angle_rad))
   (setq _upper_limit_active (round __upper_limit_active))
   (setq _encoder_valid (round __encoder_valid))
   (setq _manip_feedback (round __manip_feedback))
   self)
  (:base_angle_deg
   (&optional __base_angle_deg)
   (if __base_angle_deg (setq _base_angle_deg __base_angle_deg)) _base_angle_deg)
  (:base_angle_rad
   (&optional __base_angle_rad)
   (if __base_angle_rad (setq _base_angle_rad __base_angle_rad)) _base_angle_rad)
  (:upper_limit_active
   (&optional __upper_limit_active)
   (if __upper_limit_active (setq _upper_limit_active __upper_limit_active)) _upper_limit_active)
  (:encoder_valid
   (&optional __encoder_valid)
   (if __encoder_valid (setq _encoder_valid __encoder_valid)) _encoder_valid)
  (:manip_feedback
   (&optional __manip_feedback)
   (if __manip_feedback (setq _manip_feedback __manip_feedback)) _manip_feedback)
  (:serialization-length
   ()
   (+
    ;; float32 _base_angle_deg
    4
    ;; float32 _base_angle_rad
    4
    ;; uint8 _upper_limit_active
    1
    ;; uint8 _encoder_valid
    1
    ;; uint8 _manip_feedback
    1
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; float32 _base_angle_deg
       (sys::poke _base_angle_deg (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _base_angle_rad
       (sys::poke _base_angle_rad (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; uint8 _upper_limit_active
       (write-byte _upper_limit_active s)
     ;; uint8 _encoder_valid
       (write-byte _encoder_valid s)
     ;; uint8 _manip_feedback
       (write-byte _manip_feedback s)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; float32 _base_angle_deg
     (setq _base_angle_deg (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _base_angle_rad
     (setq _base_angle_rad (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; uint8 _upper_limit_active
     (setq _upper_limit_active (sys::peek buf ptr- :char)) (incf ptr- 1)
   ;; uint8 _encoder_valid
     (setq _encoder_valid (sys::peek buf ptr- :char)) (incf ptr- 1)
   ;; uint8 _manip_feedback
     (setq _manip_feedback (sys::peek buf ptr- :char)) (incf ptr- 1)
   ;;
   self)
  )

(setf (get robot_communication::manipulation_comm :md5sum-) "b39ca69519966dad3fbfe73959724983")
(setf (get robot_communication::manipulation_comm :datatype-) "robot_communication/manipulation_comm")
(setf (get robot_communication::manipulation_comm :definition-)
      "# manipulation_comm.msg
float32 base_angle_deg 
float32 base_angle_rad 
uint8 upper_limit_active 
uint8 encoder_valid
uint8 manip_feedback
")



(provide :robot_communication/manipulation_comm "b39ca69519966dad3fbfe73959724983")


