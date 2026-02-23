"""
CEO Thread Auto
"""
from setuptools import setup, find_packages

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="ceo-thread-auto",
    version="2.3.8",
    description="Thread auto uploader",
    author="Paro Partners",
    python_requires=">=3.9",
    packages=find_packages(include=["src", "src.*"]),
    include_package_data=True,
    install_requires=requirements,
)
