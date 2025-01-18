import os
import sys
import subprocess
import setuptools
from setuptools.command.build_py import build_py as _build_py

# Your .proto files live here (relative to setup.py):
PROTO_DIR = "home_led_matrix/apps/snake_app/protos"
# The folder into which Python/GRPC code will be generated:
GENERATED_DIR = "home_led_matrix/apps/snake_app/py_proto"

class BuildProtoCommand(_build_py):
    """Custom build step to compile .proto files before building Python package."""

    def run(self):
        # Ensure the output directory for generated code exists
        os.makedirs(GENERATED_DIR, exist_ok=True)

        # Collect all .proto files in PROTO_DIR
        proto_files = [
            f for f in os.listdir(PROTO_DIR) if f.endswith(".proto")
        ]

        for proto_file in proto_files:
            full_path = os.path.join(PROTO_DIR, proto_file)

            # Compile with grpc_tools.protoc
            # --proto_path: where to look for importable proto files
            # --python_out: where to generate Python PB2 modules
            # --grpc_python_out: where to generate gRPC stubs (remove if not needed)
            subprocess.check_call([
                sys.executable, '-m', 'grpc_tools.protoc',
                f'--proto_path={PROTO_DIR}',
                f'--python_out={GENERATED_DIR}',
                f'--grpc_python_out={GENERATED_DIR}',
                full_path
            ])

        # Continue with normal build
        super().run()


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
    url="https://github.com/JesperFritsch/home_led_matrix",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',

    # Add any dependencies needed for protobuf and gRPC
    install_requires=[
        "numpy",
        "grpcio",
        "grpcio-tools",
        "setuptools",
        "pillow",
        "asyncio",
        "firebase_admin",
        "aiohttp",
        "websockets"
        # plus anything else your package needs
    ],

    # Tell setuptools to use our custom command
    cmdclass={
        'build_py': BuildProtoCommand,
    },
)
