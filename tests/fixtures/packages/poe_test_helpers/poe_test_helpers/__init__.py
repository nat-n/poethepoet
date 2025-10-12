import os
import sys
import time


def echo():
    """
    Imitates the basic usage of the standard echo command for cross platform usage
    """
    content = sys.argv[1:]
    print(" ".join(content), flush=True)


def delayed_echo():
    """
    A process that takes some time to start and then echoes the arguments.

    Usage: delayed_echo sleep_time [content...]
    """
    delay = sys.argv[1]
    content = sys.argv[2:] if len(sys.argv) > 2 else [f"Waited {delay}ms"]
    time.sleep(int(delay) / 1000)
    print(" ".join(content), flush=True)


def immortal_echo():
    """
    Swallow N interrupts and then echo the arguments on start and on each interrupt.

    Usage: immortal_echo N [content...]
    """
    lives = sys.argv[1]
    content = sys.argv[2:]
    timeout = 60
    signal_count = 0
    while signal_count < int(lives):
        try:
            print(" ".join(content), flush=True)
            time.sleep(timeout)
        except KeyboardInterrupt:  # noqa: PERF203
            signal_count += 1


def env():
    """
    Imitates the basic usage of the standard env command for cross platform usage
    """
    for key, value in os.environ.items():
        print(f"{key}={value}", flush=True)


def pwd():
    """
    Imitates the basic usage of the POSIX pwd command for cross platform usage
    """
    print(os.getcwd(), flush=True)


def fail():
    """
    A process that always fails

    Usage: fail [delay] [return_code]
    """
    delay = sys.argv[1] if len(sys.argv) > 1 else "0"
    return_code = sys.argv[2] if len(sys.argv) > 2 else "1"
    time.sleep(int(delay) / 1000)
    sys.exit(int(return_code))
