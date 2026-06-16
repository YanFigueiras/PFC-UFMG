# ------------------ Jazzy ----------------------

# Start from ROS2 base image
FROM ros:jazzy AS vis_guard_jazzy
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install apt dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    git \
    ros-jazzy-crazyflie-interfaces \
    && rm -rf /var/lib/apt/lists/*

# fix: Reinstalling NumPy < 2.0.0
# ROS Jazzy's core and existing dependencies are not yet fully compatible with NumPy 2.0.
RUN pip3 install "numpy<2.0.0" --force-reinstall

# Create workspace and copy dependency manifests
RUN mkdir -p /root/ros2_ws/src/visibility_guard
WORKDIR /root/ros2_ws

# Copy only dependency files to cache installation
# COPY package.xml /root/ros2_ws/src/visibility_guard/
# COPY requirements.txt /root/ros2_ws/src/visibility_guard/

# Install python dependencies from requirements.txt
RUN pip3 install -r src/visibility_guard/requirements.txt

# Build workspace dependencies
RUN rosdep update && . /opt/ros/jazzy/setup.sh && apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y

# Copy the rest of the package files
# COPY . /root/ros2_ws/src/visibility_guard

# Build the package
RUN . /opt/ros/jazzy/setup.sh && colcon build --symlink-install

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc && \
    echo "source /root/ros2_ws/install/setup.bash" >> /root/.bashrc

# Automate workspace sourcing for docker run / exec commands
ENTRYPOINT ["/bin/bash", "-c", "source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/setup.bash && exec \"$@\"", "--"]
CMD ["bash"]


# ------------------ Humble ----------------------
# Start from ROS2 base image
FROM ros:humble AS vis_guard_humble
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install apt dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    git \
    ros-humble-crazyflie-interfaces \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies globally
RUN pip3 install \
    colcon-common-extensions \
    rosdep \
    gurobipy \
    shapely \
    transforms3d \
    opencv-python

# fix: Reinstalling NumPy < 2.0.0
# ROS Humble's core and existing dependencies are not yet fully compatible with NumPy 2.0.
RUN pip3 install "numpy<2.0.0" --force-reinstall

# Create workspace and copy dependency manifests
RUN mkdir -p /root/ros2_ws/src/
WORKDIR /root/ros2_ws

# Copy only dependency files to cache installation
# COPY package.xml /root/ros2_ws/src/visibility_guard/
# COPY requirements.txt /root/ros2_ws/src/visibility_guard/

# Install python dependencies from requirements.txt
RUN pip3 install -r src/visibility_guard/requirements.txt

# Build workspace dependencies
RUN rosdep update && . /opt/ros/humble/setup.sh && apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y

# Copy the rest of the package files
# COPY . /root/ros2_ws/src/visibility_guard

# Build the package
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /root/ros2_ws/install/setup.bash" >> /root/.bashrc

# Automate workspace sourcing for docker run / exec commands
ENTRYPOINT ["/bin/bash", "-c", "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && exec \"$@\"", "--"]
CMD ["bash"]
