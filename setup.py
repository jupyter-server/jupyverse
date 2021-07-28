from pathlib import Path
from setuptools import setup, find_packages

here = Path(__file__).parent
version_ns = {}
with open(here / "jupyverse" / "_version.py") as f:
    exec(f.read(), {}, version_ns)

setup(
    name="jupyverse",
    version=version_ns["__version__"],
    url="https://github.com/davidbrochart/jupyverse.git",
    author="David Brochart",
    author_email="david.brochart@gmail.com",
    description="A web server for Jupyter, based on FastAPI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "fastapi",
        "aiofiles",
        "typer",
        "uvicorn",
        "websockets",
        "kernel_server",
    ],
    extras_require={
        "test": [
            "flake8",
            "black",
            "mypy",
        ],
    },
    entry_points={
        "console_scripts": ["jupyverse = jupyverse.jupyverse:cli"],
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
