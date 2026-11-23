; Auto-generated. Do not edit!


(cl:in-package robot_communication-msg)


;//! \htmlinclude manipulation_comm.msg.html

(cl:defclass <manipulation_comm> (roslisp-msg-protocol:ros-message)
  ((base_angle_deg
    :reader base_angle_deg
    :initarg :base_angle_deg
    :type cl:float
    :initform 0.0)
   (base_angle_rad
    :reader base_angle_rad
    :initarg :base_angle_rad
    :type cl:float
    :initform 0.0)
   (upper_limit_active
    :reader upper_limit_active
    :initarg :upper_limit_active
    :type cl:fixnum
    :initform 0)
   (encoder_valid
    :reader encoder_valid
    :initarg :encoder_valid
    :type cl:fixnum
    :initform 0)
   (manip_feedback
    :reader manip_feedback
    :initarg :manip_feedback
    :type cl:fixnum
    :initform 0))
)

(cl:defclass manipulation_comm (<manipulation_comm>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <manipulation_comm>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'manipulation_comm)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_communication-msg:<manipulation_comm> is deprecated: use robot_communication-msg:manipulation_comm instead.")))

(cl:ensure-generic-function 'base_angle_deg-val :lambda-list '(m))
(cl:defmethod base_angle_deg-val ((m <manipulation_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:base_angle_deg-val is deprecated.  Use robot_communication-msg:base_angle_deg instead.")
  (base_angle_deg m))

(cl:ensure-generic-function 'base_angle_rad-val :lambda-list '(m))
(cl:defmethod base_angle_rad-val ((m <manipulation_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:base_angle_rad-val is deprecated.  Use robot_communication-msg:base_angle_rad instead.")
  (base_angle_rad m))

(cl:ensure-generic-function 'upper_limit_active-val :lambda-list '(m))
(cl:defmethod upper_limit_active-val ((m <manipulation_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:upper_limit_active-val is deprecated.  Use robot_communication-msg:upper_limit_active instead.")
  (upper_limit_active m))

(cl:ensure-generic-function 'encoder_valid-val :lambda-list '(m))
(cl:defmethod encoder_valid-val ((m <manipulation_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:encoder_valid-val is deprecated.  Use robot_communication-msg:encoder_valid instead.")
  (encoder_valid m))

(cl:ensure-generic-function 'manip_feedback-val :lambda-list '(m))
(cl:defmethod manip_feedback-val ((m <manipulation_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:manip_feedback-val is deprecated.  Use robot_communication-msg:manip_feedback instead.")
  (manip_feedback m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <manipulation_comm>) ostream)
  "Serializes a message object of type '<manipulation_comm>"
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'base_angle_deg))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'base_angle_rad))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'upper_limit_active)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'encoder_valid)) ostream)
  (cl:write-byte (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'manip_feedback)) ostream)
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <manipulation_comm>) istream)
  "Deserializes a message object of type '<manipulation_comm>"
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'base_angle_deg) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'base_angle_rad) (roslisp-utils:decode-single-float-bits bits)))
    (cl:setf (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'upper_limit_active)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'encoder_valid)) (cl:read-byte istream))
    (cl:setf (cl:ldb (cl:byte 8 0) (cl:slot-value msg 'manip_feedback)) (cl:read-byte istream))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<manipulation_comm>)))
  "Returns string type for a message object of type '<manipulation_comm>"
  "robot_communication/manipulation_comm")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'manipulation_comm)))
  "Returns string type for a message object of type 'manipulation_comm"
  "robot_communication/manipulation_comm")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<manipulation_comm>)))
  "Returns md5sum for a message object of type '<manipulation_comm>"
  "b39ca69519966dad3fbfe73959724983")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'manipulation_comm)))
  "Returns md5sum for a message object of type 'manipulation_comm"
  "b39ca69519966dad3fbfe73959724983")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<manipulation_comm>)))
  "Returns full string definition for message of type '<manipulation_comm>"
  (cl:format cl:nil "# manipulation_comm.msg~%float32 base_angle_deg ~%float32 base_angle_rad ~%uint8 upper_limit_active ~%uint8 encoder_valid~%uint8 manip_feedback~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'manipulation_comm)))
  "Returns full string definition for message of type 'manipulation_comm"
  (cl:format cl:nil "# manipulation_comm.msg~%float32 base_angle_deg ~%float32 base_angle_rad ~%uint8 upper_limit_active ~%uint8 encoder_valid~%uint8 manip_feedback~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <manipulation_comm>))
  (cl:+ 0
     4
     4
     1
     1
     1
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <manipulation_comm>))
  "Converts a ROS message object to a list"
  (cl:list 'manipulation_comm
    (cl:cons ':base_angle_deg (base_angle_deg msg))
    (cl:cons ':base_angle_rad (base_angle_rad msg))
    (cl:cons ':upper_limit_active (upper_limit_active msg))
    (cl:cons ':encoder_valid (encoder_valid msg))
    (cl:cons ':manip_feedback (manip_feedback msg))
))
