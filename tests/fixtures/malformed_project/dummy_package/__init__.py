import sys


def main(*args, greeting="hello"):
    print(greeting, *args, *sys.argv[1:])
