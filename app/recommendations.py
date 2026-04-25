import os
import pickle
from collections import defaultdict

from app.db import get_conn
from app.sizing import normalize_size

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ml', 'artifacts')

_similarity_index = None
_size_models = None


def _load_artifacts():
    global _similarity_index, _size_models

    sim_path = os.path.join(ARTIFACTS_DIR, 'similarity.pkl')
    size_path = os.path.join(ARTIFACTS_DIR, 'size_model.pkl')

    if _similarity_index is None and os.path.exists(sim_path):
        with open(sim_path, 'rb') as f:
            _similarity_index = pickle.load(f)

    if _size_models is None and os.path.exists(size_path):
        with open(size_path, 'rb') as f:
            _size_models = pickle.load(f)


def get_customer_purchase_history(customer_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT c.CustomerID, c.CustomerName, c.CustomerEmail, "
        "o.OrderNumber, o.InvoiceDate, o.PaidDate, "
        "oi.ProductName, oi.UnitPrice, oi.TotalPrice, oi.OrderLineItem, "
        "p.ProductSKU, p.ProductStyle, p.ProductSize, p.SizingFamily, p.SizeNormalized "
        "FROM Customers c "
        "JOIN Orders o ON c.CustomerEmail = o.OrderEmail "
        "JOIN OrderItems oi ON o.OrderNumber = oi.OrderNumber "
        "LEFT JOIN Products p ON p.InvProductName = oi.ProductName "
        "WHERE c.CustomerID = ? AND o.OrderType = 'RETAIL' "
        "ORDER BY o.InvoiceDate DESC",
        (customer_id,)
    ).fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append({
            'customer_id': r['CustomerID'],
            'customer_name': r['CustomerName'],
            'order_number': r['OrderNumber'],
            'date': r['PaidDate'] or r['InvoiceDate'],
            'product_name': r['ProductName'],
            'product_sku': r['ProductSKU'],
            'product_style': r['ProductStyle'],
            'size': r['ProductSize'] or r['SizeNormalized'],
            'sizing_family': r['SizingFamily'],
            'unit_price': r['UnitPrice'],
            'total_price': r['TotalPrice'],
        })
    return history


def get_customer_info(customer_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT CustomerID, CustomerName, CustomerEmail, CustomerType "
        "FROM Customers WHERE CustomerID = ?",
        (customer_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def recommend_for_customer(customer_id, n=5):
    _load_artifacts()

    history = get_customer_purchase_history(customer_id)
    if not history:
        return {'recommendations': [], 'reason': 'no_purchase_history'}

    purchased_skus = {h['product_sku'] for h in history if h['product_sku']}

    sizes_by_family = defaultdict(list)
    for h in history:
        if h['sizing_family'] and h['size']:
            sizes_by_family[h['sizing_family']].append(h['size'])

    if not _similarity_index:
        return {'recommendations': [], 'reason': 'model_not_trained'}

    conn = get_conn()
    product_lookup = {}
    for r in conn.execute(
        "SELECT ProductSKU, ProductName, ProductStyle, ProductSize, "
        "UnitPrice, SizingFamily, SizeNormalized FROM Products"
    ).fetchall():
        product_lookup[r['ProductSKU']] = dict(r)
    conn.close()

    candidate_scores = defaultdict(float)
    candidate_based_on = {}

    for h in history:
        sku = h['product_sku']
        if not sku or sku not in _similarity_index:
            continue
        for sim_sku, score in _similarity_index[sku]:
            if sim_sku in purchased_skus:
                continue
            if score > candidate_scores[sim_sku]:
                candidate_scores[sim_sku] = score
                candidate_based_on[sim_sku] = sku

    ranked = sorted(candidate_scores.items(), key=lambda x: -x[1])

    recommendations = []
    for sku, score in ranked:
        if len(recommendations) >= n:
            break

        product = product_lookup.get(sku)
        if not product:
            continue

        family = product.get('SizingFamily', 'clothing')
        recommended_size = None
        fit_confidence = 'low'

        if _size_models and family in _size_models:
            model = _size_models[family]
            recommended_size, fit_confidence = model.predict_best_size(
                customer_id, sku, family
            )

        if recommended_size is None and family in sizes_by_family:
            from app.ml.size_model import SizeFitModel
            m = SizeFitModel()
            recommended_size = m.predict_size_fallback(
                sizes_by_family[family], family
            )
            fit_confidence = 'low'

        based_on_sku = candidate_based_on.get(sku)
        based_on_product = product_lookup.get(based_on_sku, {})

        recommendations.append({
            'sku': sku,
            'product_name': product.get('ProductName', ''),
            'product_style': product.get('ProductStyle', ''),
            'unit_price': product.get('UnitPrice'),
            'recommended_size': recommended_size or product.get('SizeNormalized', ''),
            'fit_confidence': fit_confidence,
            'similarity_score': round(score, 3),
            'based_on_sku': based_on_sku,
            'based_on_name': based_on_product.get('ProductName', ''),
        })

    return {'recommendations': recommendations}
