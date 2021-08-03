from setuptools import setup  # type: ignore

setup(
    name="fps_retrolab",
    install_requires=["fps", "retrolab", "fps-contents", "fps-kernels"],
    entry_points={"fps_router": ["fps-retrolab = fps_retrolab.routes"]},
)
