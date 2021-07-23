from setuptools import setup, find_packages

setup(
    name="japiter",
    version="0.0.1",
    url="https://github.com/davidbrochart/japiter.git",
    author="David Brochart",
    author_email="david.brochart@gmail.com",
    description="A web framework for building Jupyter APIs",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "fastapi",
        "aiofiles",
        "typer",
        "uvicorn",
    ],
    extras_require={
        "test": [
            "flake8",
            "black",
        ],
    },
    entry_points={
        "console_scripts": ["japiter = japiter.japiter:cli"],
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
