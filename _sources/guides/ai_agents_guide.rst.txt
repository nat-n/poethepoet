Using poethepoet with AI Agents
===============================

Poe the Poet is a good fit with agentic coding workflows, as a way to standardize allowed agent actions within a project. This page collects some tips to help get the most from poethepoet when working with coding agents.

.. tip::

  Add a section to your CLAUDE.md or AGENTS.md to instruct the agent to always check for and use available poe tasks when performing common actions like testing, linting, formatting, or whatever is relevant for your project.

  This helps the agent avoid running with incorrect configuration or dependencies, and makes it easier to manage permissions for these actions.

Agent Skill
-----------

The official poethepoet skill can help your AI Agent use poethepoet more effectively. It covers discovering and executing tasks, as well as more in-depth guidance on creating them.

See the :ref:`full installation instructions<Install the poethepoet AI Agent skill>`, or simply run the interactive installer with:

.. code-block:: sh

    poe _install_skill


Claude Code
-----------

Include the following in your ``.claude/settings.json`` to grant your agent permission to run any poe task, assuming you only define poe tasks for benign actions.

.. code-block:: json

   {
     "permissions": {
       "allow": [
         "Bash(poe *)"
       ]
     }
   }

If you have a lightweight poe task for code formatting, then you might want to configure your agent to run that task whenever it finishes making changes:

.. code-block:: json

  {
    "hooks": {
      "Stop": [
        {
          "hooks": [
            {
              "type": "command",
              "command": "poe format"
            }
          ]
        }
      ]
    }
  }
