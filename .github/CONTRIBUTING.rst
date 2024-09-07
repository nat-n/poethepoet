So you’d like to contribute? Awesome! Here are some things worth
knowing.

Reporting a bug / requesting a feature / asking a question
----------------------------------------------------------

Go `open an issue <https://github.com/nat-n/poethepoet/issues>`_ or `start a discussion <https://github.com/nat-n/poethepoet/discussions>`_ and I’ll probably reply soon.

Contributing to the docs
------------------------

Just make a PR with your proposed changes targeting the main branch. The `documentation website <https://poethepoet.natn.io/>`_ will update once your PR is merged.

Contributing code
-----------------

Preface
~~~~~~~

If you’re willing to contribute your ideas and effort to making poethepoet better, then that’s awesome and I’m grateful. I don’t have all the answers so it’s particularly important for this project to benefit from diverse perspectives and technical expertise.

However please be aware that a lot of thought has gone into the architecture of poethepoet, and whilst I know it’s not perfect, and I am very interested in alternative perspectives, I do have strong (and I hope reasonable) opinions about how certain things should work. This particularly applies to naming and internal APIs. There is a lot to consider in terms of making sure the tool stays simple, flexible, and performant. So please don’t be offended if there is some push back.

Development process
~~~~~~~~~~~~~~~~~~~

1. If your planned changes entail non-trivial UI or internal API changes then it’s a good idea to bring them up for discussion as a `GitHub issue <https://github.com/nat-n/poethepoet/issues>`_ first.

2. Fork and clone the repo, and create a feature or bugfix branch off of the *development* branch.

3. Double check that you’re starting from the *development* branch, and not from the the *main* branch.

4. Run ``poetry install`` to setup your development environment. (`install poetry <https://python-poetry.org/docs/#installation>`__)

5. Do your code.

6. If you’ve added a feature then before it can be including in a release we will need:

   a. a feature test along the same lines as the examples in the tests dir,
   b. to update documentation.

5. Run ``poe check`` to check that you haven’t broken anything that will block the CI pipeline.

6. Create a commit with a clear commit message that describes the commit contents.

7. Open a PR on GitHub.

.. seealso::

  You can also open a draft PR proposing incomplete changes to recieve feedback.

Pull requests
~~~~~~~~~~~~~

There isn’t currently a pull request template, but please try and be descriptive about what problem you’re solving and how, and reference related issues.

In some cases it might be acceptable to merge code to *development* to make a pre-release from it without including full automated tests and documentation.
However this is a special case, because it blocks further releases from the *development* branch until the tests and docs are there.

Branching model
~~~~~~~~~~~~~~~

This project implements something like git flow.

*TL;DR* branch off of *development* for new features, or *main* for documentation improvements.

We like to keep a clean history, so squash-rebase merges are preferred for the *development* or *main* branches.

Overview of branches
~~~~~~~~~~~~~~~~~~~~

Historic branches
^^^^^^^^^^^^^^^^^

-  **main** the primary branch containing released code and up to date docs.
-  **development** in progress and pre-released features that are expected to be included in a release when ready.

Working branches
^^^^^^^^^^^^^^^^

-  **hotfix/** branches for minor/urgent bug fixes from main
-  **feature/** branches for new feature development from development
-  **bugfix/** for new bug fixes from development
-  **doc/** branches for documentation changes

How to add a new feature
~~~~~~~~~~~~~~~~~~~~~~~~

1. Create your branch from *development*

.. code-block:: bash

   git fetch
   git checkout origin/development
   git checkout -b feature/my_new_feature

2. Create a pull request back to *development*

How to add a hot fix
~~~~~~~~~~~~~~~~~~~~

1. Create your branch from *main*

.. code-block:: bash

   git fetch
   git checkout origin/main
   git checkout -b feature/my_new_feature

2. Create a pull request back to *main*, and one to *development*

How to create release
~~~~~~~~~~~~~~~~~~~~~

1. From the head of the *development* branch, create release commit that bumps the version in ``pyproject.toml`` and ``__version__.py`` (there’s a test to ensure these are in sync).
2. Create a release (and tag) on GitHub, following the existing convention for naming and release notes format (use the *Generate release notes* button as a starting point), and the GitHub CI will do the rest.
3. Unless it is a pre-release then the final step is to merge *development* into *main*.
