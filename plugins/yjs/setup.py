from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_yjs",
    packages=find_packages(),
    install_requires=["fps", "fps-contents", "fps-kernels"],
    entry_points={"fps_router": ["fps-yjs = fps_yjs.routes"]},
)
