// Auto-generated. Do not edit!

// (in-package robot_communication.msg)


"use strict";

const _serializer = _ros_msg_utils.Serialize;
const _arraySerializer = _serializer.Array;
const _deserializer = _ros_msg_utils.Deserialize;
const _arrayDeserializer = _deserializer.Array;
const _finder = _ros_msg_utils.Find;
const _getByteLength = _ros_msg_utils.getByteLength;

//-----------------------------------------------------------

class manipulation_comm {
  constructor(initObj={}) {
    if (initObj === null) {
      // initObj === null is a special case for deserialization where we don't initialize fields
      this.base_angle_deg = null;
      this.base_angle_rad = null;
      this.upper_limit_active = null;
      this.encoder_valid = null;
      this.manip_feedback = null;
    }
    else {
      if (initObj.hasOwnProperty('base_angle_deg')) {
        this.base_angle_deg = initObj.base_angle_deg
      }
      else {
        this.base_angle_deg = 0.0;
      }
      if (initObj.hasOwnProperty('base_angle_rad')) {
        this.base_angle_rad = initObj.base_angle_rad
      }
      else {
        this.base_angle_rad = 0.0;
      }
      if (initObj.hasOwnProperty('upper_limit_active')) {
        this.upper_limit_active = initObj.upper_limit_active
      }
      else {
        this.upper_limit_active = 0;
      }
      if (initObj.hasOwnProperty('encoder_valid')) {
        this.encoder_valid = initObj.encoder_valid
      }
      else {
        this.encoder_valid = 0;
      }
      if (initObj.hasOwnProperty('manip_feedback')) {
        this.manip_feedback = initObj.manip_feedback
      }
      else {
        this.manip_feedback = 0;
      }
    }
  }

  static serialize(obj, buffer, bufferOffset) {
    // Serializes a message object of type manipulation_comm
    // Serialize message field [base_angle_deg]
    bufferOffset = _serializer.float32(obj.base_angle_deg, buffer, bufferOffset);
    // Serialize message field [base_angle_rad]
    bufferOffset = _serializer.float32(obj.base_angle_rad, buffer, bufferOffset);
    // Serialize message field [upper_limit_active]
    bufferOffset = _serializer.uint8(obj.upper_limit_active, buffer, bufferOffset);
    // Serialize message field [encoder_valid]
    bufferOffset = _serializer.uint8(obj.encoder_valid, buffer, bufferOffset);
    // Serialize message field [manip_feedback]
    bufferOffset = _serializer.uint8(obj.manip_feedback, buffer, bufferOffset);
    return bufferOffset;
  }

  static deserialize(buffer, bufferOffset=[0]) {
    //deserializes a message object of type manipulation_comm
    let len;
    let data = new manipulation_comm(null);
    // Deserialize message field [base_angle_deg]
    data.base_angle_deg = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [base_angle_rad]
    data.base_angle_rad = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [upper_limit_active]
    data.upper_limit_active = _deserializer.uint8(buffer, bufferOffset);
    // Deserialize message field [encoder_valid]
    data.encoder_valid = _deserializer.uint8(buffer, bufferOffset);
    // Deserialize message field [manip_feedback]
    data.manip_feedback = _deserializer.uint8(buffer, bufferOffset);
    return data;
  }

  static getMessageSize(object) {
    return 11;
  }

  static datatype() {
    // Returns string type for a message object
    return 'robot_communication/manipulation_comm';
  }

  static md5sum() {
    //Returns md5sum for a message object
    return 'b39ca69519966dad3fbfe73959724983';
  }

  static messageDefinition() {
    // Returns full string definition for message
    return `
    # manipulation_comm.msg
    float32 base_angle_deg 
    float32 base_angle_rad 
    uint8 upper_limit_active 
    uint8 encoder_valid
    uint8 manip_feedback
    `;
  }

  static Resolve(msg) {
    // deep-construct a valid message object instance of whatever was passed in
    if (typeof msg !== 'object' || msg === null) {
      msg = {};
    }
    const resolved = new manipulation_comm(null);
    if (msg.base_angle_deg !== undefined) {
      resolved.base_angle_deg = msg.base_angle_deg;
    }
    else {
      resolved.base_angle_deg = 0.0
    }

    if (msg.base_angle_rad !== undefined) {
      resolved.base_angle_rad = msg.base_angle_rad;
    }
    else {
      resolved.base_angle_rad = 0.0
    }

    if (msg.upper_limit_active !== undefined) {
      resolved.upper_limit_active = msg.upper_limit_active;
    }
    else {
      resolved.upper_limit_active = 0
    }

    if (msg.encoder_valid !== undefined) {
      resolved.encoder_valid = msg.encoder_valid;
    }
    else {
      resolved.encoder_valid = 0
    }

    if (msg.manip_feedback !== undefined) {
      resolved.manip_feedback = msg.manip_feedback;
    }
    else {
      resolved.manip_feedback = 0
    }

    return resolved;
    }
};

module.exports = manipulation_comm;
