def flask_version():
    import flask

    print(flask.__version__)


def flask_exec_version():
    from subprocess import Popen, PIPE

    Popen(["flask", "--version"])
