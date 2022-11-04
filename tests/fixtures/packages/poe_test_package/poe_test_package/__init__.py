import os
import sys

__version__ = "0.0.99"


def simple_say():
    print(",(", sys.argv[1], ")")


def print_version():
    print("Poe test package", __version__)


def print_env():
    for key, value in os.environ.items():
        print(f"{key}={value}")
