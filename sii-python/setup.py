from setuptools import setup, find_packages

setup(
    name="sii-image",
    version="0.1.0",
    author="elsan97",
    description="Small Image Interface (SII) format reader and writer",
    packages=find_packages(),
    install_requires=[
        "Pillow>=9.0.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)