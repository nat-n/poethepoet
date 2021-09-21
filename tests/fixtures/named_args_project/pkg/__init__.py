from typing import Any, Optional


def greet(
    greeting: str = "greetings",
    user: str = "user",
    default: str = "default",
    optional: Optional[Any] = "Optional",
    upper: bool = False,
    **kwargs
):
    if upper:
        print(
            *tuple(
                *(
                    subpart.upper()
                    for subpart in (
                        greeting,
                        user,
                        default,
                        *(val for val in kwargs.values() if isinstance(val, str)),
                    )
                ),
                optional,
                *(val for val in kwargs.values() if not isinstance(val, str))
            )
        )
    else:
        print(greeting, user, default, *kwargs.values(), optional)
