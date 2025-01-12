import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="home_led_matrix",
    version="0.0.1",
    author="Jesper Fritsch",
    author_email="jesperf96@gmail.com",
    description="A small package to control a LED matrix",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JesperFritsch/home_led_matrix",  # Replace with your actual repo
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",      # Choose the correct license
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',
)

