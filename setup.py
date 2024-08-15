import os
import setuptools

# This file path
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

# Open version file
VERSION_FILE = open(os.path.join(__location__, "VERSION"))

# Get version number
VERSION = VERSION_FILE.read().strip().split("-")[0]

setuptools.setup(
    name="your-local-bartender",
    version=VERSION,
    scripts=[],
    author="Alex Bennett (alex@b16.dev)",
    description="AI assistant for Discord.",
    url="https://github.com/alexbennett/your-local-bartender",
    packages=setuptools.find_packages(),
    include_package_data=True,
    setup_requires=[],
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    test_suite="nose.collector",
    tests_require=["nose"],
)
