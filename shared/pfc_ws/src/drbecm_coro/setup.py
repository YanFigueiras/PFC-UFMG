from glob import glob
from setuptools import find_packages, setup


package_name = "drbecm_coro"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
        ("share/" + package_name + "/config", glob("config/*.rviz")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="yanfigueiras",
    maintainer_email="yanfigueiras@example.com",
    description="Simple DRBECM exploration controller for coro.world",
    license="MIT",
    entry_points={
        "console_scripts": [
            "drbecm_node = drbecm_coro.node:main",
        ],
    },
)
