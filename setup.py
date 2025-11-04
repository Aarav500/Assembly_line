"""
Setup file for unified_app
Enables proper imports across modules
"""

from setuptools import setup, find_packages

setup(
    name="unified_app",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        # Add common dependencies here
        'flask>=2.3.0',
        'requests>=2.31.0',
    ],
)
