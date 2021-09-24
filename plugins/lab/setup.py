from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_lab",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "fps",
        "fps-auth",
        "aiofiles",
        "babel",
    ],
    entry_points={
        "fps_router": ["fps-lab = fps_lab.routes"],
        "fps_config": ["fps-lab = fps_lab.config"],
    },
)
