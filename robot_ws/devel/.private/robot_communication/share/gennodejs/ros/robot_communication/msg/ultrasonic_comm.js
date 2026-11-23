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

class ultrasonic_comm {
  constructor(initObj={}) {
    if (initObj === null) {
      // initObj === null is a special case for deserialization where we don't initialize fields
      this.us_left_1 = null;
      this.us_left_2 = null;
      this.us_right_1 = null;
      this.us_right_2 = null;
      this.us_front_left = null;
      this.us_front_right = null;
    }
    else {
      if (initObj.hasOwnProperty('us_left_1')) {
        this.us_left_1 = initObj.us_left_1
      }
      else {
        this.us_left_1 = 0.0;
      }
      if (initObj.hasOwnProperty('us_left_2')) {
        this.us_left_2 = initObj.us_left_2
      }
      else {
        this.us_left_2 = 0.0;
      }
      if (initObj.hasOwnProperty('us_right_1')) {
        this.us_right_1 = initObj.us_right_1
      }
      else {
        this.us_right_1 = 0.0;
      }
      if (initObj.hasOwnProperty('us_right_2')) {
        this.us_right_2 = initObj.us_right_2
      }
      else {
        this.us_right_2 = 0.0;
      }
      if (initObj.hasOwnProperty('us_front_left')) {
        this.us_front_left = initObj.us_front_left
      }
      else {
        this.us_front_left = 0.0;
      }
      if (initObj.hasOwnProperty('us_front_right')) {
        this.us_front_right = initObj.us_front_right
      }
      else {
        this.us_front_right = 0.0;
      }
    }
  }

  static serialize(obj, buffer, bufferOffset) {
    // Serializes a message object of type ultrasonic_comm
    // Serialize message field [us_left_1]
    bufferOffset = _serializer.float32(obj.us_left_1, buffer, bufferOffset);
    // Serialize message field [us_left_2]
    bufferOffset = _serializer.float32(obj.us_left_2, buffer, bufferOffset);
    // Serialize message field [us_right_1]
    bufferOffset = _serializer.float32(obj.us_right_1, buffer, bufferOffset);
    // Serialize message field [us_right_2]
    bufferOffset = _serializer.float32(obj.us_right_2, buffer, bufferOffset);
    // Serialize message field [us_front_left]
    bufferOffset = _serializer.float32(obj.us_front_left, buffer, bufferOffset);
    // Serialize message field [us_front_right]
    bufferOffset = _serializer.float32(obj.us_front_right, buffer, bufferOffset);
    return bufferOffset;
  }

  static deserialize(buffer, bufferOffset=[0]) {
    //deserializes a message object of type ultrasonic_comm
    let len;
    let data = new ultrasonic_comm(null);
    // Deserialize message field [us_left_1]
    data.us_left_1 = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [us_left_2]
    data.us_left_2 = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [us_right_1]
    data.us_right_1 = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [us_right_2]
    data.us_right_2 = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [us_front_left]
    data.us_front_left = _deserializer.float32(buffer, bufferOffset);
    // Deserialize message field [us_front_right]
    data.us_front_right = _deserializer.float32(buffer, bufferOffset);
    return data;
  }

  static getMessageSize(object) {
    return 24;
  }

  static datatype() {
    // Returns string type for a message object
    return 'robot_communication/ultrasonic_comm';
  }

  static md5sum() {
    //Returns md5sum for a message object
    return 'e2d56a586910c98d1be0a922e15f0ddb';
  }

  static messageDefinition() {
    // Returns full string definition for message
    return `
    # ultrasonic_comm.msg
    float32 us_left_1
    float32 us_left_2
    
    float32 us_right_1
    float32 us_right_2
    
    float32 us_front_left
    float32 us_front_right
    `;
  }

  static Resolve(msg) {
    // deep-construct a valid message object instance of whatever was passed in
    if (typeof msg !== 'object' || msg === null) {
      msg = {};
    }
    const resolved = new ultrasonic_comm(null);
    if (msg.us_left_1 !== undefined) {
      resolved.us_left_1 = msg.us_left_1;
    }
    else {
      resolved.us_left_1 = 0.0
    }

    if (msg.us_left_2 !== undefined) {
      resolved.us_left_2 = msg.us_left_2;
    }
    else {
      resolved.us_left_2 = 0.0
    }

    if (msg.us_right_1 !== undefined) {
      resolved.us_right_1 = msg.us_right_1;
    }
    else {
      resolved.us_right_1 = 0.0
    }

    if (msg.us_right_2 !== undefined) {
      resolved.us_right_2 = msg.us_right_2;
    }
    else {
      resolved.us_right_2 = 0.0
    }

    if (msg.us_front_left !== undefined) {
      resolved.us_front_left = msg.us_front_left;
    }
    else {
      resolved.us_front_left = 0.0
    }

    if (msg.us_front_right !== undefined) {
      resolved.us_front_right = msg.us_front_right;
    }
    else {
      resolved.us_front_right = 0.0
    }

    return resolved;
    }
};

module.exports = ultrasonic_comm;
