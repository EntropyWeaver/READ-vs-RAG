"""Chunk baselines: BM25, real dense embeddings, RRF hybrid and optional cross encoder."""

import math
import re
import time
from collections import Counter
from dataclasses import dataclass

from .corpus import Line, normalize


def tokenize(text):
    return re.findall(r"\w+(?:\.\d+)?", normalize(text)[0])


@dataclass
class Chunk:
    id: str
    lines: list[Line]

    @property
    def text(self):
        return "\n".join(line.text for line in self.lines)


def chunk_corpus(corpus, chars=1500, overlap_lines=2, contextual=False):
    if chars < 80 or overlap_lines < 0:
        raise ValueError("chunk_chars >= 80 and overlap_lines >= 0 required")
    chunks = []
    for doc, texts in corpus.docs.items():
        start, headings, context_at, unit = 0, {}, [], None
        for i, text in enumerate(texts):
            match = re.match(r"^(#{1,6})\s+", text)
            if match:
                depth = len(match[1])
                headings = {k: v for k, v in headings.items() if k < depth}
                headings[depth] = i
                unit = None
            if re.search(r"(?i)(?:amounts?|figures?|Rs\.?|INR|units?)\s+(?:are\s+)?in\s+|fiscal year", text):
                unit = i
            context_at.append(sorted(set(headings.values()) | ({unit} if unit is not None else set())))
        while start < len(texts):
            end, size = start, 0
            while end < len(texts) and (size + len(texts[end]) + 1 <= chars or end == start):
                size += len(texts[end]) + 1
                end += 1
            ids = list(range(start, end))
            if contextual:
                ids = sorted(set(context_at[start] + ids))
            lines = [Line(doc, i + 1, texts[i]) for i in ids]
            chunks.append(Chunk(f"{doc}:{start + 1}-{end}", lines))
            if end == len(texts):
                break
            start = max(start + 1, end - overlap_lines)
    return chunks


class BM25:
    def __init__(self, chunks, k1=1.5, b=.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.counts = [Counter(tokenize(c.text)) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.avg = sum(self.lengths) / max(1, len(chunks)) or 1
        df = Counter(t for c in self.counts for t in c)
        self.idf = {t: math.log(1 + (len(chunks) - n + .5) / (n + .5)) for t, n in df.items()}

    def search(self, query, k):
        scores = []
        for i, counts in enumerate(self.counts):
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg)
            score = sum(self.idf.get(t, 0) * counts[t] * (self.k1 + 1) / (counts[t] + norm)
                        for t in set(tokenize(query)))
            if score > 0:
                scores.append((i, score))
        return sorted(scores, key=lambda p: (-p[1], p[0]))[:k]


class Dense:
    def __init__(self, chunks, model, revision, query_prefix, device="cpu", allow_truncation=False):
        if not revision or revision in ("main", "master"):
            raise ValueError("Pin embedding_revision to a model commit SHA")
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Dense requires: pip install -e '.[dense]'. No lexical fallback is used.") from exc
        self.np, self.chunks, self.query_prefix = np, chunks, query_prefix
        self.model = SentenceTransformer(model, revision=revision, device=device, trust_remote_code=False)
        # Count before encoding: silent truncation would weaken the baseline.
        lengths = [len(self.model.tokenizer.encode(c.text, truncation=False)) for c in chunks]
        self.truncated_chunks = sum(n > self.model.max_seq_length for n in lengths)
        if self.truncated_chunks and not allow_truncation:
            raise ValueError(f"{self.truncated_chunks} chunks exceed encoder max_seq_length="
                             f"{self.model.max_seq_length}; reduce chunk_chars or explicitly allow truncation")
        self.embeddings = self.model.encode([c.text for c in chunks], normalize_embeddings=True,
                                            convert_to_numpy=True, show_progress_bar=False)

    def search(self, query, k):
        text = self.query_prefix + query
        if len(self.model.tokenizer.encode(text, truncation=False)) > self.model.max_seq_length:
            raise ValueError("Query exceeds encoder length; refusing silent truncation")
        q = self.model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
        scores = self.embeddings @ q
        indices = self.np.argsort(-scores, kind="stable")[:k]
        return [(int(i), float(scores[i])) for i in indices]


class Retriever:
    def __init__(self, corpus, config):
        started = time.perf_counter()
        self.config = config
        self.chunks = chunk_corpus(corpus, config.get("chunk_chars", 1500),
                                   config.get("overlap_lines", 2), config.get("contextual", True))
        self.kind, self.k = config["retriever"], config.get("k", 8)
        if self.k <= 0 or self.kind not in {"bm25", "dense", "hybrid"}:
            raise ValueError("Invalid retrieval configuration")
        self.bm25 = BM25(self.chunks) if self.kind in {"bm25", "hybrid"} else None
        self.dense = None
        if self.kind in {"dense", "hybrid"}:
            self.dense = Dense(self.chunks, config["embedding_model"], config["embedding_revision"],
                               config.get("query_prefix", ""), config.get("device", "cpu"),
                               config.get("allow_embedding_truncation", False))
        self.reranker = None
        if config.get("reranker_model"):
            from sentence_transformers import CrossEncoder
            revision = config.get("reranker_revision")
            if not revision or revision in ("main", "master"):
                raise ValueError("Pin reranker_revision")
            self.reranker = CrossEncoder(config["reranker_model"], revision=revision,
                                         device=config.get("device", "cpu"), trust_remote_code=False)
        self.build_s = time.perf_counter() - started

    def search(self, query):
        pool = max(self.k, self.config.get("candidate_k", 40)) if self.kind == "hybrid" or self.reranker else self.k
        if self.kind == "bm25":
            hits = self.bm25.search(query, pool)
        elif self.kind == "dense":
            hits = self.dense.search(query, pool)
        else:
            fused = Counter()
            for ranking in (self.bm25.search(query, pool), self.dense.search(query, pool)):
                for rank, (i, _) in enumerate(ranking, 1):
                    fused[i] += 1 / (60 + rank)
            hits = sorted(fused.items(), key=lambda p: (-p[1], p[0]))[:pool]
        if self.reranker and hits:
            pairs = [(query, self.chunks[i].text) for i, _ in hits]
            lengths = [len(self.reranker.tokenizer.encode(a, b, truncation=False)) for a, b in pairs]
            max_length = self.reranker.max_length or self.reranker.tokenizer.model_max_length
            if any(n > max_length for n in lengths):
                raise ValueError("Reranker input would truncate; reduce chunks or query size")
            scores = self.reranker.predict(pairs)
            hits = sorted([(i, float(s)) for (i, _), s in zip(hits, scores)], key=lambda p: (-p[1], p[0]))
        return [(self.chunks[i], score) for i, score in hits[:self.k]]
