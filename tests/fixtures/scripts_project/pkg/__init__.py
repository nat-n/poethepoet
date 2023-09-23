import sys


def uprint(*objects, sep=" ", end="\n", file=sys.stdout):
    enc = file.encoding
    if enc == "UTF-8":
        print(*objects, sep=sep, end=end, file=file)
    else:

        def f(obj):
            return str(obj).encode(enc, errors="backslashreplace").decode(enc)

        print(*map(f, objects), sep=sep, end=end, file=file)


def echo_args():
    print("hello", *sys.argv[1:])


def get_random_number():
    print("determining most random number...")
    return 7


def echo_script(*args, **kwargs):
    print("args", args)
    print("kwargs", kwargs)


def describe_args(*args, **kwargs):
    for value in args:
        print(f"{type(value).__name__}: {value}")
    for key, value in kwargs.items():
        print(f"{key} => {type(value).__name__}: {value}")


def greet(
    greeting: str = "I'm sorry", user: str = "Dave", upper: bool = False, **kwargs
):
    if upper:
        uprint(
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
        uprint(greeting, user, *kwargs.values())


class Scripts:
    class Deep:
        def fun(self):
            print("task!")


async def async_task(*args, **kwargs):
    print("I'm an async task!", args, kwargs)
