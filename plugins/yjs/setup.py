from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_yjs",
    version="0.0.2",
    packages=find_packages(),
    install_requires=["fps", "fps-contents", "fps-kernels", "fps-auth"],
    entry_points={"fps_router": ["fps-yjs = fps_yjs.routes"]},
)
