from setuptools import setup

setup(
    name="kernel_server",
    version="0.0.1",
    url="https://github.com/davidbrochart/kernel_server.git",
    author="David Brochart",
    author_email="david.brochart@gmail.com",
    description="A Jupyter kernel server",
    packages=["kernel_server"],
    python_requires=">=3.7",
    install_requires=[
        "pyzmq",
        "websockets",
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
