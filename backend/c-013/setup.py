from setuptools import setup, find_packages

setup(
    name="app",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "Flask==3.0.3",
        "gunicorn==22.0.0",
    ],
)
