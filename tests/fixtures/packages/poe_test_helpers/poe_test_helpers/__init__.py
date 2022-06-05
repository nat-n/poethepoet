import os
import sys


def echo():
    print(sys.argv[1:])


def env():
    for key, value in os.environ.items():
        print(f"{key}={value}")
