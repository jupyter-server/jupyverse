from setuptools import setup  # type: ignore

setup(
    name="fps_contents",
    install_requires=["fps", "aiofiles"],
    entry_points={"fps_router": ["fps-contents = fps_contents.routes"]},
)
