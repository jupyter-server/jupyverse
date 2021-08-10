from setuptools import setup  # type: ignore

setup(
    name="fps_auth",
    install_requires=["fps", "httpx-oauth"],
    entry_points={
        "fps_router": ["fps-auth = fps_auth.routes"],
        "fps_config": ["fps-auth = fps_auth.config"],
    },
)
