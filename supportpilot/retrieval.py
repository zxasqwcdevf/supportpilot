"""Small-corpus BM25 / dense retrieval with reciprocal rank fusion."""
import math
import os
import re
from collections import Counter
from functools import lru_cache


def tokenize(text):
    words = re.findall(r"[a-z0-9]+|[가-힣]+", text.lower())
    result = []
    for word in words:
        result.append(word)
        if re.fullmatch(r"[가-힣]+", word):
            result.extend(word[i:i + 2] for i in range(len(word) - 1))
    return result


def document_text(doc):
    return doc["title"] + " " + " ".join(doc["keywords"]) + " " + doc["text"]


def keyword_matches(query, keyword):
    suffixes = {"", "은", "는", "이", "가", "을", "를", "도", "에", "에서", "으로", "로", "의", "해주세요", "해줘"}
    words = re.findall(r"[가-힣a-z0-9]+", query.lower())
    keyword = keyword.lower()
    return any(word.startswith(keyword) and word[len(keyword):] in suffixes for word in words)


def warmup(documents):
    # Includes first load/download, corpus encoding and one query encoding.
    dense_scores("검색 초기화", documents)


def eligible(lexical_score, dense_score=None):
    lexical_cutoff = float(os.getenv("SUPPORTPILOT_BM25_THRESHOLD", "2.0"))
    dense_cutoff = float(os.getenv("SUPPORTPILOT_DENSE_THRESHOLD", "0.8"))
    return lexical_score >= lexical_cutoff or (dense_score is not None and dense_score >= dense_cutoff)


def bm25(query, documents):
    corpus = [Counter(tokenize(document_text(doc))) for doc in documents]
    lengths = [sum(counts.values()) for counts in corpus]
    average = sum(lengths) / len(lengths) if lengths else 1
    scores = [0.0] * len(corpus)
    for term in set(tokenize(query)):
        frequency = sum(term in counts for counts in corpus)
        idf = math.log(1 + (len(corpus) - frequency + .5) / (frequency + .5))
        for i, counts in enumerate(corpus):
            tf = counts[term]
            if tf:
                scores[i] += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * lengths[i] / average))
    return scores


@lru_cache(maxsize=2)
def encoder(model_name):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name, device="cpu")


@lru_cache(maxsize=4)
def corpus_vectors(model_name, texts):
    return encoder(model_name).encode(["passage: " + text for text in texts], normalize_embeddings=True).tolist()


def dense_scores(query, documents):
    name = os.getenv("SUPPORTPILOT_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    vectors = corpus_vectors(name, tuple(document_text(doc) for doc in documents))
    query_vector = encoder(name).encode("query: " + query, normalize_embeddings=True).tolist()
    return [sum(a * b for a, b in zip(query_vector, vector)) for vector in vectors]


def fuse(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, 1):
            scores[index] = scores.get(index, 0) + 1 / (k + rank)
    return sorted(scores, key=lambda index: (-scores[index], index)), scores


def retrieve(query, documents, method=None, top_k=3, dense=None):
    method = method or os.getenv("SUPPORTPILOT_RETRIEVAL", "keyword")
    if method not in {"keyword", "bm25", "hybrid"}:
        raise ValueError("Unsupported retrieval method")
    if method == "keyword":
        scores = [sum(keyword_matches(query, keyword) for keyword in doc["keywords"]) for doc in documents]
        indices = sorted((i for i, score in enumerate(scores) if score > 0), key=lambda i: (-scores[i], i))
        return [{"document": documents[i], "score": scores[i], "method": method} for i in indices[:top_k]]
    lexical = bm25(query, documents)
    ranking = sorted((i for i, score in enumerate(lexical) if score > 0), key=lambda i: (-lexical[i], i))
    scores = dict(enumerate(lexical))
    semantic = None
    if method == "hybrid":
        semantic = dense if dense is not None else dense_scores(query, documents)
        if len(semantic) != len(documents):
            raise ValueError("Dense score count must match documents")
        # Development cutoff only: calibrate on held-out negative queries.
        cutoff = float(os.getenv("SUPPORTPILOT_DENSE_THRESHOLD", "0.8"))
        semantic_ranking = sorted((i for i, score in enumerate(semantic) if score >= cutoff), key=lambda i: (-semantic[i], i))
        ranking, scores = fuse([ranking, semantic_ranking])
        # Round for floating-point rank ties, then use semantic relevance.
        ranking.sort(key=lambda i: (-round(scores[i], 12), -semantic[i], -lexical[i], documents[i]["id"]))
    # Apply relevance gate to every final candidate, including BM25-only hits.
    ranking = [i for i in ranking if eligible(lexical[i], semantic[i] if semantic is not None else None)]
    return [{"document": documents[i], "score": scores[i], "bm25_score": lexical[i], "dense_score": semantic[i] if semantic is not None else None, "method": method} for i in ranking[:top_k]]
