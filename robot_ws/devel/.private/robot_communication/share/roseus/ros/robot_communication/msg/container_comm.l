;; Auto-generated. Do not edit!


(when (boundp 'robot_communication::container_comm)
  (if (not (find-package "ROBOT_COMMUNICATION"))
    (make-package "ROBOT_COMMUNICATION"))
  (shadow 'container_comm (find-package "ROBOT_COMMUNICATION")))
(unless (find-package "ROBOT_COMMUNICATION::CONTAINER_COMM")
  (make-package "ROBOT_COMMUNICATION::CONTAINER_COMM"))

(in-package "ROS")
;;//! \htmlinclude container_comm.msg.html


(defclass robot_communication::container_comm
  :super ros::object
  :slots (_color _position_x _position_y ))

(defmethod robot_communication::container_comm
  (:init
   (&key
    ((:color __color) "")
    ((:position_x __position_x) 0.0)
    ((:position_y __position_y) 0.0)
    )
   (send-super :init)
   (setq _color (string __color))
   (setq _position_x (float __position_x))
   (setq _position_y (float __position_y))
   self)
  (:color
   (&optional __color)
   (if __color (setq _color __color)) _color)
  (:position_x
   (&optional __position_x)
   (if __position_x (setq _position_x __position_x)) _position_x)
  (:position_y
   (&optional __position_y)
   (if __position_y (setq _position_y __position_y)) _position_y)
  (:serialization-length
   ()
   (+
    ;; string _color
    4 (length _color)
    ;; float32 _position_x
    4
    ;; float32 _position_y
    4
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; string _color
       (write-long (length _color) s) (princ _color s)
     ;; float32 _position_x
       (sys::poke _position_x (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;; float32 _position_y
       (sys::poke _position_y (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; string _color
     (let (n) (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4) (setq _color (subseq buf ptr- (+ ptr- n))) (incf ptr- n))
   ;; float32 _position_x
     (setq _position_x (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;; float32 _position_y
     (setq _position_y (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;;
   self)
  )

(setf (get robot_communication::container_comm :md5sum-) "5f327da10beacf9251645c5e9c0fcda7")
(setf (get robot_communication::container_comm :datatype-) "robot_communication/container_comm")
(setf (get robot_communication::container_comm :definition-)
      "#container_comm.msg
string color
float32 position_x
float32 position_y
")



(provide :robot_communication/container_comm "5f327da10beacf9251645c5e9c0fcda7")


