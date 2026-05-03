from collections.abc import Mapping


class SpyDict(dict):
    """
    A kind of dict in which the behavior __getitem__ can be overridden.
    """

    def __init__(self, content=(), *, getitem_spy=None):
        super().__init__(content)
        self._getitem_spy = getitem_spy

    def __getitem__(self, key):
        """
        Return a transformed version of the key, and record that it was accessed.
        """
        value = super().__getitem__(key)
        if self._getitem_spy:
            return self._getitem_spy(self, key, value)
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def apply_envvars_to_template(
    content: str, env: Mapping[str, str], require_braces=False
) -> str:
    """
    Template in ${environment} $variables from env as if we were in a shell.

    Supports parameter expansion operators :- (default value) and :+ (alternate
    value), as well as escaping of $ with a preceding backslash.
    """
    from ..helpers.command import resolve_template

    return resolve_template(content, env, require_braces=require_braces)
