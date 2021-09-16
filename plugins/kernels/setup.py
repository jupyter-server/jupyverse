from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_kernels",
    version="0.0.4",
    packages=find_packages(),
    install_requires=["fps", "fps-auth", "pyzmq", "websockets"],
    entry_points={"fps_router": ["fps-kernels = fps_kernels.routes"]},
)
