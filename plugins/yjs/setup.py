from setuptools import setup  # type: ignore

setup(
    name="fps_yjs",
    install_requires=["fps", "fps-contents", "fps-kernels"],
    entry_points={"fps_router": ["fps-yjs = fps_yjs.routes"]},
)
