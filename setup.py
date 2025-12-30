from setuptools import setup, find_packages

def get_version():
    with open("VERSION", "r") as f:
        return f.read().strip()

setup(
    name="vps-manager",
    version=get_version(),
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
