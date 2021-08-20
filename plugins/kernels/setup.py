from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_kernels",
    version="0.0.1",
    packages=find_packages(),
    install_requires=["fps", "kernel_server>=0.0.3"],
    entry_points={"fps_router": ["fps-kernels = fps_kernels.routes"]},
)
