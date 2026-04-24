import numpy as np
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def build_tfidf_matrix(products):
    """Build TF-IDF matrix over product style + name tokens.

    Args:
        products: list of dicts with 'ProductSKU', 'ProductStyle', 'ProductName', 'SizingFamily'

    Returns:
        (skus, tfidf_sim) where tfidf_sim is a dense cosine similarity matrix
    """
    skus = [p['ProductSKU'] for p in products]
    docs = []
    for p in products:
        tokens = f"{p['ProductStyle']} {p['ProductName']} {p.get('SizingFamily', '')}"
        docs.append(tokens.lower())

    if not docs:
        return skus, np.zeros((0, 0))

    vectorizer = TfidfVectorizer(token_pattern=r'(?u)\b\w[\w/]+\b')
    tfidf = vectorizer.fit_transform(docs)
    sim = cosine_similarity(tfidf)
    return skus, sim


def build_cooccurrence_matrix(order_items, sku_list):
    """Build item-item co-occurrence matrix from order purchase data.

    Args:
        order_items: list of dicts with 'OrderNumber', 'ProductName'
        sku_list: ordered list of product SKUs (defines matrix axes)

    Returns:
        cooc_sim: dense normalized co-occurrence similarity matrix (same dim as sku_list)
    """
    sku_idx = {sku: i for i, sku in enumerate(sku_list)}
    n = len(sku_list)
    cooc = np.zeros((n, n), dtype=np.float64)

    orders = defaultdict(set)
    for item in order_items:
        orders[item['OrderNumber']].add(item.get('ProductSKU') or item.get('ProductName'))

    for order_skus in orders.values():
        resolved = [s for s in order_skus if s in sku_idx]
        for i_sku in resolved:
            for j_sku in resolved:
                if i_sku != j_sku:
                    cooc[sku_idx[i_sku], sku_idx[j_sku]] += 1

    row_sums = cooc.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    cooc_sim = cooc / row_sums
    return cooc_sim


def build_similarity_index(products, order_items, alpha=0.6, top_k=20):
    """Build blended similarity index.

    Args:
        products: list of product dicts
        order_items: list of order item dicts
        alpha: weight for TF-IDF vs co-occurrence (alpha * tfidf + (1-alpha) * cooc)
        top_k: number of similar items to store per product

    Returns:
        dict mapping SKU -> list of (SKU, score) tuples sorted descending by score
    """
    skus, tfidf_sim = build_tfidf_matrix(products)
    n = len(skus)

    if n == 0:
        return {}

    cooc_sim = build_cooccurrence_matrix(order_items, skus)

    has_cooc = cooc_sim.sum() > 0
    if has_cooc:
        blended = alpha * tfidf_sim + (1 - alpha) * cooc_sim
    else:
        blended = tfidf_sim

    similarity_index = {}
    for i, sku in enumerate(skus):
        scores = blended[i]
        ranked = sorted(
            [(skus[j], scores[j]) for j in range(n) if j != i],
            key=lambda x: -x[1]
        )
        similarity_index[sku] = ranked[:top_k]

    return similarity_index
