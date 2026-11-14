"""
Embedding utility — hashes text into a deterministic 384-dimension vector.
This avoids requiring an external embedding model so the project runs
without API keys or model downloads. The hash-based embedder captures
shared words and character trigrams, which is enough for semantic similarity
at the demo scale.
"""
import hashlib
import math
import struct
import re
from typing import List

DIMENSIONS = 384


def _tokenize(text: str) -> List[str]:
    """Lowercase, strip non-alphanumeric, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t]


def _hash_token(token: str, dim: int) -> int:
    """Hash a token to a dimension index."""
    h = hashlib.md5(token.encode()).digest()
    return struct.unpack("I", h[:4])[0] % dim


def _hash_trigram(trigram: str, dim: int) -> int:
    """Hash a character trigram to a dimension index."""
    h = hashlib.md5(trigram.encode()).digest()
    return struct.unpack("I", h[:4])[0] % dim


def embed(text: str, dim: int = DIMENSIONS) -> List[float]:
    """
    Embed text into a deterministic, unit-length vector of `dim` dimensions.

    Each token contributes +1 to its hashed dimension. Character trigrams
    contribute a smaller weight. The vector is L2-normalized.
    """
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    for token in tokens:
        idx = _hash_token(token, dim)
        vec[idx] += 1.0

        # Add character trigrams for partial matching
        padded = f"#{token}#"
        for i in range(len(padded) - 2):
            trigram = padded[i : i + 3]
            t_idx = _hash_trigram(trigram, dim)
            vec[t_idx] += 0.3

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]

    return vec


def embed_as_cypher(text: str, dim: int = DIMENSIONS) -> str:
    """Return a Cypher vector() literal for the text."""
    v = embed(text, dim)
    parts = ", ".join(str(x) for x in v)
    return f"vector([{parts}], {dim}, FLOAT32)"
