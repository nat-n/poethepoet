import os


def inspect_flag(flag):
    print(repr((flag, os.environ["flag"])))  # noqa: SIM112
