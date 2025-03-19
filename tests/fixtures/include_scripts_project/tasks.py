def tasks1(task_suffix: str = ""):
    import os

    poe_executor = os.environ.get("POE_ACTIVE")
    return {
        "env": {"ENV_VAR": "ENV_VAL"},
        "envfile": ["envfile"],
        "tasks": {
            f"check-vars{task_suffix}": """
                poe_test_echo "ENV_VAR:${ENV_VAR}\nENVFILE_VAR:${ENVFILE_VAR}"
            """,
            f"check-args{task_suffix}": {
                "cmd": "poe_test_echo ${ARG_VAR}",
                "help": "Checking that we can pass an arg",
                "args": [
                    {
                        "name ": "ARG_VAR",
                        "options": ["--something"],
                        "help": "This is the arg",
                    }
                ],
            },
            f"script-executor{task_suffix}": (
                f"poe_test_echo build_time:{poe_executor}, " "run_time:${POE_ACTIVE}"
            ),
            f"cwd{task_suffix}": "poe_test_pwd",
            f"confdir{task_suffix}": "poe_test_echo POE_CONF_DIR=${POE_CONF_DIR}",
        },
    }
