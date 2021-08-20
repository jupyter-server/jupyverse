from setuptools import setup, find_packages  # type: ignore

setup(
    name="fps_terminals",
    version="0.0.1",
    packages=find_packages(),
    install_requires=["fps"],
    entry_points={"fps_router": ["fps-terminals = fps_terminals.routes"]},
)
