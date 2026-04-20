import gc
from collections import OrderedDict

from .AbstractTTS import AbstractTTS
from book_assistant.Commons import warning

class LRUModelCache:
    """Keeps at most `capacity` TTS models loaded at once."""

    def __init__(self, models: dict[str, AbstractTTS], capacity: int):
        self._factory = models          # all known models (not yet loaded)
        self._capacity = capacity
        self._cache: OrderedDict[str, AbstractTTS] = OrderedDict()

    def keys(self):
        return self._factory.keys()

    def __contains__(self, name: str) -> bool:
        return name in self._factory

    def __getitem__(self, name: str) -> AbstractTTS:
        if name in self._cache:
            self._cache.move_to_end(name)   # mark as most recently used
            return self._cache[name]

        # evict LRU if at capacity
        while len(self._cache) >= self._capacity:
            evicted_name, evicted_model = self._cache.popitem(last=False)
            warning(f"LRU close: {evicted_name}")
            evicted_model.close()
            gc.collect()

        model = self._factory[name]
        self._cache[name] = model
        self._cache.move_to_end(name)
        model.ensure_initialized()
        warning(f"Loaded models: {sorted(self._cache.keys())}")
        return model