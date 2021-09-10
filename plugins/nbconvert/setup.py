from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_nbconvert",
    version="0.0.2",
    packages=find_packages(),
    install_requires=["fps", "nbconvert", "fps-auth"],
    entry_points={"fps_router": ["fps-nbconvert = fps_nbconvert.routes"]},
)
