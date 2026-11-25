; Auto-generated. Do not edit!


(cl:in-package robot_communication-msg)


;//! \htmlinclude container_comm.msg.html

(cl:defclass <container_comm> (roslisp-msg-protocol:ros-message)
  ((color
    :reader color
    :initarg :color
    :type cl:string
    :initform "")
   (position_x
    :reader position_x
    :initarg :position_x
    :type cl:float
    :initform 0.0)
   (position_y
    :reader position_y
    :initarg :position_y
    :type cl:float
    :initform 0.0))
)

(cl:defclass container_comm (<container_comm>)
  ())

(cl:defmethod cl:initialize-instance :after ((m <container_comm>) cl:&rest args)
  (cl:declare (cl:ignorable args))
  (cl:unless (cl:typep m 'container_comm)
    (roslisp-msg-protocol:msg-deprecation-warning "using old message class name robot_communication-msg:<container_comm> is deprecated: use robot_communication-msg:container_comm instead.")))

(cl:ensure-generic-function 'color-val :lambda-list '(m))
(cl:defmethod color-val ((m <container_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:color-val is deprecated.  Use robot_communication-msg:color instead.")
  (color m))

(cl:ensure-generic-function 'position_x-val :lambda-list '(m))
(cl:defmethod position_x-val ((m <container_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:position_x-val is deprecated.  Use robot_communication-msg:position_x instead.")
  (position_x m))

(cl:ensure-generic-function 'position_y-val :lambda-list '(m))
(cl:defmethod position_y-val ((m <container_comm>))
  (roslisp-msg-protocol:msg-deprecation-warning "Using old-style slot reader robot_communication-msg:position_y-val is deprecated.  Use robot_communication-msg:position_y instead.")
  (position_y m))
(cl:defmethod roslisp-msg-protocol:serialize ((msg <container_comm>) ostream)
  "Serializes a message object of type '<container_comm>"
  (cl:let ((__ros_str_len (cl:length (cl:slot-value msg 'color))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) __ros_str_len) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) __ros_str_len) ostream))
  (cl:map cl:nil #'(cl:lambda (c) (cl:write-byte (cl:char-code c) ostream)) (cl:slot-value msg 'color))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'position_x))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
  (cl:let ((bits (roslisp-utils:encode-single-float-bits (cl:slot-value msg 'position_y))))
    (cl:write-byte (cl:ldb (cl:byte 8 0) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 8) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 16) bits) ostream)
    (cl:write-byte (cl:ldb (cl:byte 8 24) bits) ostream))
)
(cl:defmethod roslisp-msg-protocol:deserialize ((msg <container_comm>) istream)
  "Deserializes a message object of type '<container_comm>"
    (cl:let ((__ros_str_len 0))
      (cl:setf (cl:ldb (cl:byte 8 0) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) __ros_str_len) (cl:read-byte istream))
      (cl:setf (cl:slot-value msg 'color) (cl:make-string __ros_str_len))
      (cl:dotimes (__ros_str_idx __ros_str_len msg)
        (cl:setf (cl:char (cl:slot-value msg 'color) __ros_str_idx) (cl:code-char (cl:read-byte istream)))))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'position_x) (roslisp-utils:decode-single-float-bits bits)))
    (cl:let ((bits 0))
      (cl:setf (cl:ldb (cl:byte 8 0) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 8) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 16) bits) (cl:read-byte istream))
      (cl:setf (cl:ldb (cl:byte 8 24) bits) (cl:read-byte istream))
    (cl:setf (cl:slot-value msg 'position_y) (roslisp-utils:decode-single-float-bits bits)))
  msg
)
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql '<container_comm>)))
  "Returns string type for a message object of type '<container_comm>"
  "robot_communication/container_comm")
(cl:defmethod roslisp-msg-protocol:ros-datatype ((msg (cl:eql 'container_comm)))
  "Returns string type for a message object of type 'container_comm"
  "robot_communication/container_comm")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql '<container_comm>)))
  "Returns md5sum for a message object of type '<container_comm>"
  "5f327da10beacf9251645c5e9c0fcda7")
(cl:defmethod roslisp-msg-protocol:md5sum ((type (cl:eql 'container_comm)))
  "Returns md5sum for a message object of type 'container_comm"
  "5f327da10beacf9251645c5e9c0fcda7")
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql '<container_comm>)))
  "Returns full string definition for message of type '<container_comm>"
  (cl:format cl:nil "#container_comm.msg~%string color~%float32 position_x~%float32 position_y~%~%"))
(cl:defmethod roslisp-msg-protocol:message-definition ((type (cl:eql 'container_comm)))
  "Returns full string definition for message of type 'container_comm"
  (cl:format cl:nil "#container_comm.msg~%string color~%float32 position_x~%float32 position_y~%~%"))
(cl:defmethod roslisp-msg-protocol:serialization-length ((msg <container_comm>))
  (cl:+ 0
     4 (cl:length (cl:slot-value msg 'color))
     4
     4
))
(cl:defmethod roslisp-msg-protocol:ros-message-to-list ((msg <container_comm>))
  "Converts a ROS message object to a list"
  (cl:list 'container_comm
    (cl:cons ':color (color msg))
    (cl:cons ':position_x (position_x msg))
    (cl:cons ':position_y (position_y msg))
))
