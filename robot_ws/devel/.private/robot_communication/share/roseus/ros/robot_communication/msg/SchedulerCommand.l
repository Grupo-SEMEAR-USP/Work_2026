;; Auto-generated. Do not edit!


(when (boundp 'robot_communication::SchedulerCommand)
  (if (not (find-package "ROBOT_COMMUNICATION"))
    (make-package "ROBOT_COMMUNICATION"))
  (shadow 'SchedulerCommand (find-package "ROBOT_COMMUNICATION")))
(unless (find-package "ROBOT_COMMUNICATION::SCHEDULERCOMMAND")
  (make-package "ROBOT_COMMUNICATION::SCHEDULERCOMMAND"))

(in-package "ROS")
;;//! \htmlinclude SchedulerCommand.msg.html


(defclass robot_communication::SchedulerCommand
  :super ros::object
  :slots (_uid _target _payload _need_ack _timeout ))

(defmethod robot_communication::SchedulerCommand
  (:init
   (&key
    ((:uid __uid) 0)
    ((:target __target) "")
    ((:payload __payload) "")
    ((:need_ack __need_ack) nil)
    ((:timeout __timeout) 0.0)
    )
   (send-super :init)
   (setq _uid (round __uid))
   (setq _target (string __target))
   (setq _payload (string __payload))
   (setq _need_ack __need_ack)
   (setq _timeout (float __timeout))
   self)
  (:uid
   (&optional __uid)
   (if __uid (setq _uid __uid)) _uid)
  (:target
   (&optional __target)
   (if __target (setq _target __target)) _target)
  (:payload
   (&optional __payload)
   (if __payload (setq _payload __payload)) _payload)
  (:need_ack
   (&optional (__need_ack :null))
   (if (not (eq __need_ack :null)) (setq _need_ack __need_ack)) _need_ack)
  (:timeout
   (&optional __timeout)
   (if __timeout (setq _timeout __timeout)) _timeout)
  (:serialization-length
   ()
   (+
    ;; uint64 _uid
    8
    ;; string _target
    4 (length _target)
    ;; string _payload
    4 (length _payload)
    ;; bool _need_ack
    1
    ;; float32 _timeout
    4
    ))
  (:serialize
   (&optional strm)
   (let ((s (if strm strm
              (make-string-output-stream (send self :serialization-length)))))
     ;; uint64 _uid
#+(or :alpha :irix6 :x86_64)
       (progn (sys::poke _uid (send s :buffer) (send s :count) :long) (incf (stream-count s) 8))
#-(or :alpha :irix6 :x86_64)
       (cond ((and (class _uid) (= (length (_uid . bv)) 2)) ;; bignum
              (write-long (ash (elt (_uid . bv) 0) 0) s)
              (write-long (ash (elt (_uid . bv) 1) -1) s))
             ((and (class _uid) (= (length (_uid . bv)) 1)) ;; big1
              (write-long (elt (_uid . bv) 0) s)
              (write-long (if (>= _uid 0) 0 #xffffffff) s))
             (t                                         ;; integer
              (write-long _uid s)(write-long (if (>= _uid 0) 0 #xffffffff) s)))
     ;; string _target
       (write-long (length _target) s) (princ _target s)
     ;; string _payload
       (write-long (length _payload) s) (princ _payload s)
     ;; bool _need_ack
       (if _need_ack (write-byte -1 s) (write-byte 0 s))
     ;; float32 _timeout
       (sys::poke _timeout (send s :buffer) (send s :count) :float) (incf (stream-count s) 4)
     ;;
     (if (null strm) (get-output-stream-string s))))
  (:deserialize
   (buf &optional (ptr- 0))
   ;; uint64 _uid
     
#+(or :alpha :irix6 :x86_64)
      (setf _uid (prog1 (sys::peek buf ptr- :long) (incf ptr- 8)))
#-(or :alpha :irix6 :x86_64)
      (setf _uid (let ((b0 (prog1 (sys::peek buf ptr- :integer) (incf ptr- 4)))
                  (b1 (prog1 (sys::peek buf ptr- :integer) (incf ptr- 4))))
              (cond ((= b1 -1) b0)
                     ((and (= b1  0)
                           (<= lisp::most-negative-fixnum b0 lisp::most-positive-fixnum))
                      b0)
                    ((= b1  0) (make-instance bignum :size 1 :bv (integer-vector b0)))
                    (t (make-instance bignum :size 2 :bv (integer-vector b0 (ash b1 1)))))))
   ;; string _target
     (let (n) (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4) (setq _target (subseq buf ptr- (+ ptr- n))) (incf ptr- n))
   ;; string _payload
     (let (n) (setq n (sys::peek buf ptr- :integer)) (incf ptr- 4) (setq _payload (subseq buf ptr- (+ ptr- n))) (incf ptr- n))
   ;; bool _need_ack
     (setq _need_ack (not (= 0 (sys::peek buf ptr- :char)))) (incf ptr- 1)
   ;; float32 _timeout
     (setq _timeout (sys::peek buf ptr- :float)) (incf ptr- 4)
   ;;
   self)
  )

(setf (get robot_communication::SchedulerCommand :md5sum-) "95112fe84583f15f46a9728e120c0c3a")
(setf (get robot_communication::SchedulerCommand :datatype-) "robot_communication/SchedulerCommand")
(setf (get robot_communication::SchedulerCommand :definition-)
      "# SchedulerCommand.msg
uint64 uid
string target
string payload
bool need_ack
float32 timeout
")



(provide :robot_communication/SchedulerCommand "95112fe84583f15f46a9728e120c0c3a")


