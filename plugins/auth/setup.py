from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_auth",
    packages=find_packages(),
    install_requires=["fps", "httpx-oauth"],
    entry_points={
        "fps_router": ["fps-auth = fps_auth.routes"],
        "fps_config": ["fps-auth = fps_auth.config"],
    },
)
