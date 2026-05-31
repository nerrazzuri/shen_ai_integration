from setuptools import find_packages, setup
import os
from glob import glob

package_name = "shenai_health_scan"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools", "requests"],
    zip_safe=True,
    maintainer="Liang Kai Feng",
    maintainer_email="liangkaifeng1987@gmail.com",
    description="Shen.AI facial health scan on AgiBot X2",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "scan_node = shenai_health_scan.node:main",
            "scan_demo = shenai_health_scan.demo:main",
        ],
    },
)
