from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_kernels",
    version="0.0.2",
    packages=find_packages(),
    install_requires=["fps", "kernel_server>=0.0.5", "fps-auth"],
    entry_points={"fps_router": ["fps-kernels = fps_kernels.routes"]},
)
