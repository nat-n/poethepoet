import sys


def main():
    print("hello", *sys.argv[1:])


class Scripts:
    @staticmethod
    def task():
        print("task!")
