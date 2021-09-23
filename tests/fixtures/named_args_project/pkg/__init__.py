from typing import Any, Optional


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
            )
        )
    else:
        print(greeting, user, *kwargs.values())
