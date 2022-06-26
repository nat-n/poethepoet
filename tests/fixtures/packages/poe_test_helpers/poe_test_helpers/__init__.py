import os
import sys


def echo():
    """
    Imitates the basic usage of the standard echo command for cross platform usage
    """
    print(" ".join(sys.argv[1:]))


def env():
    """
    Imitates the basic usage of the standard env command for cross platform usage
    """
    for key, value in os.environ.items():
        print(f"{key}={value}")


def pwd():
    """
    Imitates the basic usage of the POSIX pwd command for cross platform usage
    """
    print(os.getcwd())
