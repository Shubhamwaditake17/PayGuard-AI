import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import Chunk


class Retriever:
    """TF-IDF (1-2gram) vector retriever. Swap `_embed` for Azure OpenAI / sentence-transformers
    embeddings + FAISS/Azure AI Search without touching the agent."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
        self.matrix = self.vec.fit_transform([c.text for c in chunks])

    def search(self, query: str, k: int = 3, min_score: float = 0.0) -> list[Chunk]:
        q = self.vec.transform([query])
        sims = (self.matrix @ q.T).toarray().ravel()   # rows are L2-normalised => cosine
        out = []
        for i in np.argsort(sims)[::-1][:k]:
            if sims[i] >= min_score and sims[i] > 0:
                c = self.chunks[i]
                out.append(Chunk(c.id, c.source, c.text, float(sims[i])))
        return out
