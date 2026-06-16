// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from crazyflie_interfaces:msg/AttitudeSetpoint.idl
// generated code does not contain a copyright notice

#ifndef CRAZYFLIE_INTERFACES__MSG__DETAIL__ATTITUDE_SETPOINT__BUILDER_HPP_
#define CRAZYFLIE_INTERFACES__MSG__DETAIL__ATTITUDE_SETPOINT__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "crazyflie_interfaces/msg/detail/attitude_setpoint__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace crazyflie_interfaces
{

namespace msg
{

namespace builder
{

class Init_AttitudeSetpoint_thrust
{
public:
  explicit Init_AttitudeSetpoint_thrust(::crazyflie_interfaces::msg::AttitudeSetpoint & msg)
  : msg_(msg)
  {}
  ::crazyflie_interfaces::msg::AttitudeSetpoint thrust(::crazyflie_interfaces::msg::AttitudeSetpoint::_thrust_type arg)
  {
    msg_.thrust = std::move(arg);
    return std::move(msg_);
  }

private:
  ::crazyflie_interfaces::msg::AttitudeSetpoint msg_;
};

class Init_AttitudeSetpoint_yaw_rate
{
public:
  explicit Init_AttitudeSetpoint_yaw_rate(::crazyflie_interfaces::msg::AttitudeSetpoint & msg)
  : msg_(msg)
  {}
  Init_AttitudeSetpoint_thrust yaw_rate(::crazyflie_interfaces::msg::AttitudeSetpoint::_yaw_rate_type arg)
  {
    msg_.yaw_rate = std::move(arg);
    return Init_AttitudeSetpoint_thrust(msg_);
  }

private:
  ::crazyflie_interfaces::msg::AttitudeSetpoint msg_;
};

class Init_AttitudeSetpoint_pitch
{
public:
  explicit Init_AttitudeSetpoint_pitch(::crazyflie_interfaces::msg::AttitudeSetpoint & msg)
  : msg_(msg)
  {}
  Init_AttitudeSetpoint_yaw_rate pitch(::crazyflie_interfaces::msg::AttitudeSetpoint::_pitch_type arg)
  {
    msg_.pitch = std::move(arg);
    return Init_AttitudeSetpoint_yaw_rate(msg_);
  }

private:
  ::crazyflie_interfaces::msg::AttitudeSetpoint msg_;
};

class Init_AttitudeSetpoint_roll
{
public:
  explicit Init_AttitudeSetpoint_roll(::crazyflie_interfaces::msg::AttitudeSetpoint & msg)
  : msg_(msg)
  {}
  Init_AttitudeSetpoint_pitch roll(::crazyflie_interfaces::msg::AttitudeSetpoint::_roll_type arg)
  {
    msg_.roll = std::move(arg);
    return Init_AttitudeSetpoint_pitch(msg_);
  }

private:
  ::crazyflie_interfaces::msg::AttitudeSetpoint msg_;
};

class Init_AttitudeSetpoint_header
{
public:
  Init_AttitudeSetpoint_header()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_AttitudeSetpoint_roll header(::crazyflie_interfaces::msg::AttitudeSetpoint::_header_type arg)
  {
    msg_.header = std::move(arg);
    return Init_AttitudeSetpoint_roll(msg_);
  }

private:
  ::crazyflie_interfaces::msg::AttitudeSetpoint msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::crazyflie_interfaces::msg::AttitudeSetpoint>()
{
  return crazyflie_interfaces::msg::builder::Init_AttitudeSetpoint_header();
}

}  // namespace crazyflie_interfaces

#endif  // CRAZYFLIE_INTERFACES__MSG__DETAIL__ATTITUDE_SETPOINT__BUILDER_HPP_
