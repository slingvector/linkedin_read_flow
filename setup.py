from setuptools import setup, find_packages

setup(
    name="linkedin-read-flow",
    version="0.0.0",
    description="A robust, SOLID Python package for securely extracting network content off LinkedIn.",
    author="Your Name",
    packages=find_packages(exclude=["tests*", "examples*"]),
    install_requires=[
        "linkedin-api>=2.2.0",
        "python-dotenv>=1.2.0"
    ],
    python_requires=">=3.8",
)
