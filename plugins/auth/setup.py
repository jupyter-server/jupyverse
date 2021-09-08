from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_auth",
    version="0.0.2",
    packages=find_packages(),
    install_requires=[
        "fps",
        "fastapi-users[sqlalchemy]>=7.0.0",
        "httpx-oauth",
        "aiosqlite",
    ],
    entry_points={
        "fps_router": ["fps-auth = fps_auth.routes"],
        "fps_config": ["fps-auth = fps_auth.config"],
    },
)
