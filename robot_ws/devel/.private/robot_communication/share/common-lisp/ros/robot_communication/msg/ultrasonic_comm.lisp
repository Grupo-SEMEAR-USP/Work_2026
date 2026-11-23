; Auto-generated. Do not edit!


(cl:in-package robot_communication-msg)


;//! \htmlinclude ultrasonic_comm.msg.html

(cl:defclass <ultrasonic_comm> (roslisp-msg-protocol:ros-message)
  ((us_left_1
    :reader us_left_1
    :initarg :us_left_1
    :type cl:float
    :initform 0.0)
   (us_left_2
    :reader us_left_2
    :initarg :us_left_2
    :type cl:float
    :initform 0.0)
   (us_right_1
    :reader us_right_1
    :initarg :us_right_1
    :type cl:float
    :initform 0.0)
   (us_right_2
    :reader us_right_2
    :initarg :us_right_2
    :type cl:float
    :initform 0.0)
   (us_front_left
    :reader us_front_left
    :initarg :us_front_left
    :type cl:float
    :initform 0.0)
   (us_front_right
    :reader us_front_right
    :initarg :us_front_right
    :type cl:float
    :initform 0.0))
)

(cl:defclass ultrasonic_comm (<ultrasonic_comm>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <ultrasonic_comm>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'ultrasonic_comm)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_communication-msg:<ultrasonic_comm> is deprecated: use robot_communication-msg:ultrasonic_comm instead.")))

(cl:ensure-generic-function 'us_left_1-val :lambda-list '(m))
(cl:defmethod us_left_1-val ((m <ultrasonic_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:us_left_1-val is deprecated.  Use robot_communication-msg:us_left_1 instead.")
  (us_left_1 m))

(cl:ensure-generic-function 'us_left_2-val :lambda-list '(m))
(cl:defmethod us_left_2-val ((m <ultrasonic_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:us_left_2-val is deprecated.  Use robot_communication-msg:us_left_2 instead.")
  (us_left_2 m))

(cl:ensure-generic-function 'us_right_1-val :lambda-list '(m))
(cl:defmethod us_right_1-val ((m <ultrasonic_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:us_right_1-val is deprecated.  Use robot_communication-msg:us_right_1 instead.")
  (us_right_1 m))

(cl:ensure-generic-function 'us_right_2-val :lambda-list '(m))
(cl:defmethod us_right_2-val ((m <ultrasonic_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:us_right_2-val is deprecated.  Use robot_communication-msg:us_right_2 instead.")
  (us_right_2 m))

(cl:ensure-generic-function 'us_front_left-val :lambda-list '(m))
(cl:defmethod us_front_left-val ((m <ultrasonic_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:us_front_left-val is deprecated.  Use robot_communication-msg:us_front_left instead.")
  (us_front_left m))

(cl:ensure-generic-function 'us_front_right-val :lambda-list '(m))
(cl:defmethod us_front_right-val ((m <ultrasonic_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:us_front_right-val is deprecated.  Use robot_communication-msg:us_front_right instead.")
  (us_front_right m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <ultrasonic_comm>) ostream)
  "Serializes a message object of type '<ultrasonic_comm>"
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'us_left_1))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'us_left_2))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'us_right_1))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'us_right_2))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'us_front_left))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'us_front_right))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <ultrasonic_comm>) istream)
  "Deserializes a message object of type '<ultrasonic_comm>"
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'us_left_1) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'us_left_2) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'us_right_1) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'us_right_2) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'us_front_left) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'us_front_right) (roslisp-utils:decode-single-float-bits bits)))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<ultrasonic_comm>)))
  "Returns string type for a message object of type '<ultrasonic_comm>"
  "robot_communication/ultrasonic_comm")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'ultrasonic_comm)))
  "Returns string type for a message object of type 'ultrasonic_comm"
  "robot_communication/ultrasonic_comm")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<ultrasonic_comm>)))
  "Returns md5sum for a message object of type '<ultrasonic_comm>"
  "e2d56a586910c98d1be0a922e15f0ddb")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'ultrasonic_comm)))
  "Returns md5sum for a message object of type 'ultrasonic_comm"
  "e2d56a586910c98d1be0a922e15f0ddb")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<ultrasonic_comm>)))
  "Returns full string definition for message of type '<ultrasonic_comm>"
  (cl:format cl:nil "# ultrasonic_comm.msg~%float32 us_left_1~%float32 us_left_2~%~%float32 us_right_1~%float32 us_right_2~%~%float32 us_front_left~%float32 us_front_right~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'ultrasonic_comm)))
  "Returns full string definition for message of type 'ultrasonic_comm"
  (cl:format cl:nil "# ultrasonic_comm.msg~%float32 us_left_1~%float32 us_left_2~%~%float32 us_right_1~%float32 us_right_2~%~%float32 us_front_left~%float32 us_front_right~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <ultrasonic_comm>))
  (cl:+ 0
     4
     4
     4
     4
     4
     4
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <ultrasonic_comm>))
  "Converts a ROS message object to a list"
  (cl:list 'ultrasonic_comm
    (cl:cons ':us_left_1 (us_left_1 msg))
    (cl:cons ':us_left_2 (us_left_2 msg))
    (cl:cons ':us_right_1 (us_right_1 msg))
    (cl:cons ':us_right_2 (us_right_2 msg))
    (cl:cons ':us_front_left (us_front_left msg))
    (cl:cons ':us_front_right (us_front_right msg))
))
