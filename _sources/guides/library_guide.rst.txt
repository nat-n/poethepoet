Using poethepoet as a library
=============================

Normally poethepoet would be installed as a tool or poetry plugin, but it can also be used as a library to embed task runner capabilities into another tool.


The following script replicates the main functionality of the `poe` standalone cli.

.. code-block:: python

    import sys

    from poethepoet.app import PoeThePoet


    if __name__ == "__main__":
        app = PoeThePoet()
        result = app(cli_args=sys.argv[1:])
        if result:
            sys.exit(result)

The `PoeThePoet <https://github.com/nat-n/poethepoet/blob/main/poethepoet/app.py>`_ class accepts various optional arguments to customize its behavior as described below.

.. autoclass:: poethepoet.app.PoeThePoet
