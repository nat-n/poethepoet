import os
import sys
from typing import Any, Optional


def main(*args, greeting="hello", upper=False):
    if upper:
        print(
            greeting.upper(),
            *(arg.upper() for arg in args[1:]),
            *(arg.upper() for arg in sys.argv[1:]),
        )
    else:
        print(greeting, *args, *sys.argv[1:])


def print_var(*var_names):
    for var in var_names:
        print(os.environ.get(var))


def args(
    greeting: str = "greetings",
    user: str = "user",
    default: str = "default",
    optional: Optional[Any] = "Optional",
    upper: bool = False,
    **kwargs
):

    if upper:
        p = (
            tuple(
                map(
                    str.upper,
                    [
                        greeting,
                        user,
                        default,
                        *[val for val in kwargs.values() if isinstance(val, str)],
                    ],
                )
            )
            + (optional,)
            + tuple([val for val in kwargs.values() if not isinstance(val, str)])
        )
    else:
        p = (greeting, user, default, *kwargs.values(), optional)
    print(*p)
