from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_jupyterlab",
    version="0.0.4",
    packages=find_packages(),
    install_requires=[
        "fps",
        "jupyterlab",
        "aiofiles",
        "fps-auth",
        "babel",
    ],
    entry_points={
        "fps_router": ["fps-jupyterlab = fps_jupyterlab.routes"],
        "fps_config": ["fps-jupyterlab = fps_jupyterlab.config"],
    },
)
