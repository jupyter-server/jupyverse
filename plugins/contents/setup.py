from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_contents",
    version="0.0.3",
    packages=find_packages(),
    install_requires=["fps", "aiofiles", "fps-auth"],
    entry_points={"fps_router": ["fps-contents = fps_contents.routes"]},
)
