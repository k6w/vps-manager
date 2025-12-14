from setuptools import setup, find_packages

setup(
    name="vps-manager",
    version="1.2.3",
    description="A comprehensive terminal-based manager for NGINX domains and SSL certificates",
    author="k6w",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "vps-manager=vps_manager.main:main",
        ],
    },
    python_requires=">=3.8",
)
