from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_yjs",
    version="0.0.1",
    packages=find_packages(),
    install_requires=["fps", "fps-contents", "fps-kernels"],
    entry_points={"fps_router": ["fps-yjs = fps_yjs.routes"]},
)
