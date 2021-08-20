from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_kernels",
    packages=find_packages(),
    install_requires=["fps", "kernel_server>=0.0.3"],
    entry_points={"fps_router": ["fps-kernels = fps_kernels.routes"]},
)
