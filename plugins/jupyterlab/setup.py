from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_jupyterlab",
    packages=find_packages(),
    install_requires=["fps", "jupyterlab", "fps-contents", "fps-kernels", "fps-auth"],
    entry_points={
        "fps_router": ["fps-jupyterlab = fps_jupyterlab.routes"],
        "fps_config": ["fps-jupyterlab = fps_jupyterlab.config"],
    },
)
