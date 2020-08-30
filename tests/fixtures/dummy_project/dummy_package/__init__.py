import sys


def main(*args, greeting="hello", upper=False):
    if upper:
        print(
            greeting.upper(),
            *(arg.upper() for arg in args[1:]),
            *(arg.upper() for arg in sys.argv[1:])
        )
    else:
        print(greeting, *args, *sys.argv[1:])
