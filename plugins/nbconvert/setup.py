from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_nbconvert",
    version="0.0.1",
    packages=find_packages(),
    install_requires=["fps", "nbconvert"],
    entry_points={"fps_router": ["fps-nbconvert = fps_nbconvert.routes"]},
)
