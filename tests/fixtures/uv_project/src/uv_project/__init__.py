import poe_test_package


def hello() -> str:
    print("Hello from uv-project", poe_test_package.__version__)
