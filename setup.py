"""
CEO Thread Auto
"""
from pathlib import Path

from setuptools import setup, find_packages
from src.version import VERSION


ROOT = Path(__file__).resolve().parent

with (ROOT / "requirements.txt").open("r", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="ceo-thread-auto",
    version=VERSION,
    description="Thread auto uploader",
    author="와이엠",
    python_requires=">=3.11",
    packages=find_packages(include=["src", "src.*"]),
    include_package_data=True,
    install_requires=requirements,
)
