import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/CrazySim/crazyswarm2_ws/install/crazyflie_py'
