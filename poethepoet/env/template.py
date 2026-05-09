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
