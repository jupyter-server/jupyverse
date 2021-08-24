from pathlib import Path
from setuptools import setup, find_packages

here = Path(__file__).parent
version_ns = {}
with open(here / "kernel_server" / "_version.py") as f:
    exec(f.read(), {}, version_ns)

setup(
    name="kernel_server",
    version=version_ns["__version__"],
    url="https://github.com/davidbrochart/kernel_server.git",
    author="David Brochart",
    author_email="david.brochart@gmail.com",
    description="A Jupyter kernel server",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "pyzmq",
        "websockets",
        "fastapi",
    ],
    extras_require={
        "test": [
            "black",
            "mypy",
            "flake8",
        ],
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
