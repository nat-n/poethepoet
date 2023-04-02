Composing tasks
===============

Composing tasks into sequences
------------------------------

The main way to compose tasks is to use the *sequence* task type, which allows you
to define a sequence of tasks to be executed in order.

Here's a basic example:

.. code-block:: toml

  [tool.poe.tasks]

  _publish = "poetry publish"
  release = [
    { cmd = "pytest --cov=src" },
    { script = "devtasks:build" },
    { ref = "_publish" },
  ]

And here's an example that uses the *sequence* task type explicitly in a task definition:


.. code-block:: toml

  [tool.poe.tasks._publish]
  cmd = "poetry publish"

  [tool.poe.tasks.release]
  sequence = [
    { cmd = "pytest --cov=src" },
    { script = "devtasks:build" },
    { ref = "_publish" }
  ]

.. seealso::

    See :ref:`"sequence" tasks` specifics for more information on the :code:`sequence` task type.

Composing tasks into graphs (Experimental)
------------------------------------------

You can define tasks that depend on other tasks, and optionally capture and reuse the
output of those tasks, thus defining an execution graph of tasks. This is done by using
the *deps* task option, or if you want to capture the output of the upstream task to
pass it to the present task then specify the *uses* option, as demonstrated below.

.. code-block:: toml

  [tool.poe.tasks]
  _website_bucket_name.shell = """
    aws cloudformation describe-stacks \
      --stack-name $AWS_SAM_STACK_NAME \
      --query "Stacks[0].Outputs[?(@.OutputKey == 'FrontendS3Bucket')].OutputValue" \
    | jq -cr 'select(0)[0]'
  """

  [tool.poe.tasks.build-backend]
  help = "Build the backend"
  sequence = [
    {cmd = "poetry export -f requirements.txt --output src/requirements.txt"},
    {cmd = "sam build"},
  ]

  [tool.poe.tasks.build-frontend]
  help = "Build the frontend"
  cmd = "npm --prefix client run build"

  [tool.poe.tasks.shipit]
  help = "Build and deploy the app"
  sequence = [
    "sam deploy --config-env $SAM_ENV_NAME",
    "aws s3 sync --delete ./client/build s3://${BUCKET_NAME}"
  ]
  default_item_type = "cmd"
  deps = ["build-frontend", "build-backend"]
  uses = { BUCKET_NAME = "_website_bucket_name" }


In this example the :code:`shipit` task depends on the :code:`build-frontend` :code:`build-backend`, which
means that these tasks get executed before the :code:`shipit` task. It also declares that it
uses the output of the hidden :code:`_website_bucket_name` task, which means that this also
gets executed, but its output it captured and then made available to the :code:`shipit` task
as the environment variable :code:`BUCKET_NAME`.

.. warning::

  Note that captured output that is exposed as an environment variable via the `uses`
  is compacted to have new lines removed. This is similar to how interpolated command
  output is treated by bash.


.. caution::

  This feature is experimental. There may be edge cases that aren't handled well, so
  feedback is requested. Some details of the implementation or API may be altered in
  future versions.
