import asyncio
import hashlib
import math
import re
from typing import Any, Protocol

from fastembed import TextEmbedding


class Embedder(Protocol):
    dimensions: int

    # Turns each text into a vector of the embedder's size
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder:
    # Names the fastembed model; it is downloaded and loaded on first use
    def __init__(self, model_name: str, dimensions: int) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self._model: Any = None

    # Embeds texts with fastembed on a worker thread, so the event loop keeps running
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_now, texts)

    # Loads the model if needed and embeds the texts
    def _embed_now(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = TextEmbedding(self.model_name)
        return [[float(value) for value in vector] for vector in self._model.embed(texts)]


class HashingEmbedder:
    # A tiny embedder for tests: words are hashed into buckets
    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions

    # Counts hashed words per bucket and scales the result to length 1
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    # One text's bucket counts, normalised
    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions
            vector[bucket] += 1.0
        length = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / length for value in vector]
