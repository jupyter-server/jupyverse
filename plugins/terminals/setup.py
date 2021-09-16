from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_terminals",
    version="0.0.4",
    packages=find_packages(),
    install_requires=["fps", "fps-auth", "websockets"],
    entry_points={"fps_router": ["fps-terminals = fps_terminals.routes"]},
)
