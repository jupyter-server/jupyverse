from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_contents",
    packages=find_packages(),
    install_requires=["fps", "aiofiles"],
    entry_points={"fps_router": ["fps-contents = fps_contents.routes"]},
)
