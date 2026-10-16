import os
import subprocess
import sys
import time


def echo():
    """
    Imitates the basic usage of the standard echo command for cross platform usage
    """
    content = sys.argv[1:]
    print(" ".join(content), flush=True)


def echo_lines():
    """
    Print each argument on its own line, for producing multi-line output (e.g.
    env file content) cross platform.
    """
    for line in sys.argv[1:]:
        print(line, flush=True)


def delayed_echo():
    """
    A process that takes some time to start and then echoes the arguments.

    Usage: delayed_echo sleep_time [content...]
    """
    delay = sys.argv[1]
    content = sys.argv[2:] if len(sys.argv) > 2 else [f"Waited {delay}ms"]
    time.sleep(int(delay) / 1000)
    print(" ".join(content), flush=True)


def delayed_echo_with_pidfile():
    """
    A process that takes some time to start and then echoes the second argument.
    The third argument is a file path where the process writes its own PID.

    Usage: delayed_echo_with_pidfile sleep_time content pid_file_path
    """
    delay = sys.argv[1]
    content = sys.argv[2]
    pid_file_path = sys.argv[3]
    with open(pid_file_path, "w") as pid_file:
        pid_file.write(str(os.getpid()))
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
        except KeyboardInterrupt:
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


def hold_output():
    """
    Print a line and exit, leaving a detached process that holds stdout open, like a
    daemon that escaped its parent's process group.

    Usage: hold_output pid_file hold_ms [tick_ms]

    The detached process writes its pid to pid_file and holds stdout open for hold_ms,
    printing a line every tick_ms if given.
    """
    pid_file, hold_ms = sys.argv[1], sys.argv[2]
    tick_ms = sys.argv[3] if len(sys.argv) > 3 else "0"
    detach: dict = (
        {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        }
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER_CODE, hold_ms, tick_ms],
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=subprocess.DEVNULL,
        **detach,
    )
    with open(pid_file, "w") as pid_file_handle:
        pid_file_handle.write(str(holder.pid))
    print("started", flush=True)


_HOLDER_CODE = """
import sys, time
hold_ms, tick_ms = int(sys.argv[1]), int(sys.argv[2])
deadline = time.monotonic() + hold_ms / 1000
while time.monotonic() < deadline:
    if tick_ms:
        print("tick", flush=True)
    time.sleep((tick_ms or hold_ms) / 1000)
"""
