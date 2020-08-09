import sys


def main(upper=False):
    if upper:
        print("HELLO", *(arg.upper() for arg in sys.argv[1:]))
    else:
        print("hello", *sys.argv[1:])
