;; Auto-generated. Do not edit!


(when (boundp 'robot_communication::ultrasonic_comm)
  (if (not (find-package "ROBOT_COMMUNICATION"))
    (make-package "ROBOT_COMMUNICATION"))
  (shadow 'ultrasonic_comm (find-package "ROBOT_COMMUNICATION")))
(unless (find-package "ROBOT_COMMUNICATION::ULTRASONIC_COMM")
  (make-package "ROBOT_COMMUNICATION::ULTRASONIC_COMM"))

(in-package "ROS")
;;//! \htmlinclude ultrasonic_comm.msg.html


(defclass robot_communication::ultrasonic_comm
  :super ros::object
  :slots (_us_left_1 _us_left_2 _us_right_1 _us_right_2 _us_front_left _us_front_right ))

(defmethod robot_communication::ultrasonic_comm
  (:init
   (&key
    ((:us_left_1 __us_left_1) 0.0)
    ((:us_left_2 __us_left_2) 0.0)
    ((:us_right_1 __us_right_1) 0.0)
    ((:us_right_2 __us_right_2) 0.0)
    ((:us_front_left __us_front_left) 0.0)
    ((:us_front_right __us_front_right) 0.0)
    )
   (send-super :init)
   (setq _us_left_1 (float __us_left_1))
   (setq _us_left_2 (float __us_left_2))
   (setq _us_right_1 (float __us_right_1))
   (setq _us_right_2 (float __us_right_2))
   (setq _us_front_left (float __us_front_left))
   (setq _us_front_right (float __us_front_right))
   self)
  (:us_left_1
   (&optional __us_left_1)
   (if __us_left_1 (setq _us_left_1 __us_left_1)) _us_left_1)
  (:us_left_2
   (&optional __us_left_2)
   (if __us_left_2 (setq _us_left_2 __us_left_2)) _us_left_2)
  (:us_right_1
   (&optional __us_right_1)
   (if __us_right_1 (setq _us_right_1 __us_right_1)) _us_right_1)
  (:us_right_2
   (&optional __us_right_2)
   (if __us_right_2 (setq _us_right_2 __us_right_2)) _us_right_2)
  (:us_front_left
   (&optional __us_front_left)
   (if __us_front_left (setq _us_front_left __us_front_left)) _us_front_left)
  (:us_front_right
   (&optional __us_front_right)
   (if __us_front_right (setq _us_front_right __us_front_right)) _us_front_right)
  (:serialization-length
   ()
   (+
    ;; float32 _us_left_1
    4
    ;; float32 _us_left_2
    4
    ;; float32 _us_right_1
    4
    ;; float32 _us_right_2
    4
    ;; float32 _us_front_left
    4
    ;; float32 _us_front_right
    4
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; float32 _us_left_1
       (sys::poke _us_left_1 (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _us_left_2
       (sys::poke _us_left_2 (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _us_right_1
       (sys::poke _us_right_1 (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _us_right_2
       (sys::poke _us_right_2 (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _us_front_left
       (sys::poke _us_front_left (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _us_front_right
       (sys::poke _us_front_right (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; float32 _us_left_1
     (setq _us_left_1 (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _us_left_2
     (setq _us_left_2 (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _us_right_1
     (setq _us_right_1 (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _us_right_2
     (setq _us_right_2 (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _us_front_left
     (setq _us_front_left (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _us_front_right
     (setq _us_front_right (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;;
   self)
  )

(setf (get robot_communication::ultrasonic_comm :md5sum-) "e2d56a586910c98d1be0a922e15f0ddb")
(setf (get robot_communication::ultrasonic_comm :datatype-) "robot_communication/ultrasonic_comm")
(setf (get robot_communication::ultrasonic_comm :definition-)
      "# ultrasonic_comm.msg
float32 us_left_1
float32 us_left_2

float32 us_right_1
float32 us_right_2

float32 us_front_left
float32 us_front_right
")



(provide :robot_communication/ultrasonic_comm "e2d56a586910c98d1be0a922e15f0ddb")


