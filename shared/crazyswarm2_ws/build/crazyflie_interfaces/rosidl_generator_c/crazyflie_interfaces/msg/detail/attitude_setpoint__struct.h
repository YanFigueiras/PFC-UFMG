// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from crazyflie_interfaces:msg/AttitudeSetpoint.idl
// generated code does not contain a copyright notice

#ifndef CRAZYFLIE_INTERFACES__MSG__DETAIL__ATTITUDE_SETPOINT__STRUCT_H_
#define CRAZYFLIE_INTERFACES__MSG__DETAIL__ATTITUDE_SETPOINT__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.h"

/// Struct defined in msg/AttitudeSetpoint in the package crazyflie_interfaces.
typedef struct crazyflie_interfaces__msg__AttitudeSetpoint
{
  std_msgs__msg__Header header;
  float roll;
  float pitch;
  float yaw_rate;
  uint16_t thrust;
} crazyflie_interfaces__msg__AttitudeSetpoint;

// Struct for a sequence of crazyflie_interfaces__msg__AttitudeSetpoint.
typedef struct crazyflie_interfaces__msg__AttitudeSetpoint__Sequence
{
  crazyflie_interfaces__msg__AttitudeSetpoint * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} crazyflie_interfaces__msg__AttitudeSetpoint__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // CRAZYFLIE_INTERFACES__MSG__DETAIL__ATTITUDE_SETPOINT__STRUCT_H_
