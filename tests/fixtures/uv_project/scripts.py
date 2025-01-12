def test_package_version():
    import poe_test_package

    print(poe_test_package.__version__)


def test_package_exec_version():
    from subprocess import Popen

    Popen(["test_print_version"])
