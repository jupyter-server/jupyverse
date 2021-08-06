from setuptools import setup  # type: ignore

setup(
    name="fps_nbconvert",
    install_requires=["fps", "nbconvert"],
    entry_points={"fps_router": ["fps-nbconvert = fps_nbconvert.routes"]},
)
