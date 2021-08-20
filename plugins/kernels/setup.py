from setuptools import setup  # type: ignore

setup(
    name="fps_kernels",
    install_requires=["fps", "kernel_server>=0.0.3"],
    entry_points={"fps_router": ["fps-kernels = fps_kernels.routes"]},
)
