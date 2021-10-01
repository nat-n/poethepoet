import sys
from typing import Any, Optional


def echo_args():
    print("hello", *sys.argv[1:])


def describe_args(*args, **kwargs):
    for value in args:
        print(f"{type(value).__name__}: {value}")
    for key, value in kwargs.items():
        print(f"{key} => {type(value).__name__}: {value}")


def greet(
    greeting: str = "I'm sorry", user: str = "Dave", upper: bool = False, **kwargs
):
    if upper:
        print(
            *(
                str(subpart).upper()
                for subpart in (
                    greeting,
                    user,
                    *(val for val in kwargs.values() if isinstance(val, str)),
                )
            ),
            *(
                val
                for val in kwargs.values()
                if val is not None and not isinstance(val, str)
            ),
        )
    else:
        print(greeting, user, *kwargs.values())


class Scripts:
    class Deep:
        def fun(self):
            print("task!")
