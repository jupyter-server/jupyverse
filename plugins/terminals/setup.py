from setuptools import setup  # type: ignore

setup(
    name="fps_terminals",
    install_requires=["fps"],
    entry_points={"fps_router": ["fps-terminals = fps_terminals.routes"]},
)
