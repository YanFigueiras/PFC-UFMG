// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from crazyflie_interfaces:msg/AttitudeSetpoint.idl
// generated code does not contain a copyright notice
#include "crazyflie_interfaces/msg/detail/attitude_setpoint__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/detail/header__functions.h"

bool
crazyflie_interfaces__msg__AttitudeSetpoint__init(crazyflie_interfaces__msg__AttitudeSetpoint * msg)
{
  if (!msg) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__init(&msg->header)) {
    crazyflie_interfaces__msg__AttitudeSetpoint__fini(msg);
    return false;
  }
  // roll
  // pitch
  // yaw_rate
  // thrust
  return true;
}

void
crazyflie_interfaces__msg__AttitudeSetpoint__fini(crazyflie_interfaces__msg__AttitudeSetpoint * msg)
{
  if (!msg) {
    return;
  }
  // header
  std_msgs__msg__Header__fini(&msg->header);
  // roll
  // pitch
  // yaw_rate
  // thrust
}

bool
crazyflie_interfaces__msg__AttitudeSetpoint__are_equal(const crazyflie_interfaces__msg__AttitudeSetpoint * lhs, const crazyflie_interfaces__msg__AttitudeSetpoint * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__are_equal(
      &(lhs->header), &(rhs->header)))
  {
    return false;
  }
  // roll
  if (lhs->roll != rhs->roll) {
    return false;
  }
  // pitch
  if (lhs->pitch != rhs->pitch) {
    return false;
  }
  // yaw_rate
  if (lhs->yaw_rate != rhs->yaw_rate) {
    return false;
  }
  // thrust
  if (lhs->thrust != rhs->thrust) {
    return false;
  }
  return true;
}

bool
crazyflie_interfaces__msg__AttitudeSetpoint__copy(
  const crazyflie_interfaces__msg__AttitudeSetpoint * input,
  crazyflie_interfaces__msg__AttitudeSetpoint * output)
{
  if (!input || !output) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__copy(
      &(input->header), &(output->header)))
  {
    return false;
  }
  // roll
  output->roll = input->roll;
  // pitch
  output->pitch = input->pitch;
  // yaw_rate
  output->yaw_rate = input->yaw_rate;
  // thrust
  output->thrust = input->thrust;
  return true;
}

crazyflie_interfaces__msg__AttitudeSetpoint *
crazyflie_interfaces__msg__AttitudeSetpoint__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  crazyflie_interfaces__msg__AttitudeSetpoint * msg = (crazyflie_interfaces__msg__AttitudeSetpoint *)allocator.allocate(sizeof(crazyflie_interfaces__msg__AttitudeSetpoint), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(crazyflie_interfaces__msg__AttitudeSetpoint));
  bool success = crazyflie_interfaces__msg__AttitudeSetpoint__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
crazyflie_interfaces__msg__AttitudeSetpoint__destroy(crazyflie_interfaces__msg__AttitudeSetpoint * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    crazyflie_interfaces__msg__AttitudeSetpoint__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__init(crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  crazyflie_interfaces__msg__AttitudeSetpoint * data = NULL;

  if (size) {
    data = (crazyflie_interfaces__msg__AttitudeSetpoint *)allocator.zero_allocate(size, sizeof(crazyflie_interfaces__msg__AttitudeSetpoint), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = crazyflie_interfaces__msg__AttitudeSetpoint__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        crazyflie_interfaces__msg__AttitudeSetpoint__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__fini(crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      crazyflie_interfaces__msg__AttitudeSetpoint__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

crazyflie_interfaces__msg__AttitudeSetpoint__Sequence *
crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * array = (crazyflie_interfaces__msg__AttitudeSetpoint__Sequence *)allocator.allocate(sizeof(crazyflie_interfaces__msg__AttitudeSetpoint__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__destroy(crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__are_equal(const crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * lhs, const crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!crazyflie_interfaces__msg__AttitudeSetpoint__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
crazyflie_interfaces__msg__AttitudeSetpoint__Sequence__copy(
  const crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * input,
  crazyflie_interfaces__msg__AttitudeSetpoint__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(crazyflie_interfaces__msg__AttitudeSetpoint);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    crazyflie_interfaces__msg__AttitudeSetpoint * data =
      (crazyflie_interfaces__msg__AttitudeSetpoint *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!crazyflie_interfaces__msg__AttitudeSetpoint__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          crazyflie_interfaces__msg__AttitudeSetpoint__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!crazyflie_interfaces__msg__AttitudeSetpoint__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
