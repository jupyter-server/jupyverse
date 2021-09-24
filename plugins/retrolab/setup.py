from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_retrolab",
    version="0.0.4",
    packages=find_packages(),
    install_requires=["fps", "retrolab", "fps-lab", "fps-auth"],
    entry_points={
        "fps_router": ["fps-retrolab = fps_retrolab.routes"],
        "fps_config": ["fps-retrolab = fps_retrolab.config"],
    },
)
