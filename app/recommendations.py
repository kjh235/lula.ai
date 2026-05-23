import math
import os
import pickle
from collections import defaultdict

from app.db import get_conn
from app.sizing import normalize_size, available_sizes_for_family

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
    cid = customer_id.encode() if isinstance(customer_id, str) else customer_id
    rows = conn.execute(
        "SELECT c.CustomerID, c.CustomerEmail AS CustomerName, c.CustomerName AS CustomerEmail, "
        "o.OrderNumber, o.InvoiceDate, o.PaidDate, "
        "oi.ProductName, oi.UnitPrice, oi.TotalPrice, oi.OrderLineItem, "
        "p.ProductSKU, p.ProductStyle, p.ProductSize, p.SizingFamily, p.SizeNormalized "
        "FROM Customers c "
        "JOIN Orders o ON c.CustomerName = o.OrderEmail "
        "JOIN OrderItems oi ON o.OrderNumber = oi.OrderNumber "
        "LEFT JOIN Products p ON p.InvProductName = oi.ProductName "
        "WHERE c.CustomerID = ? AND o.OrderType = 'RETAIL' "
        "ORDER BY o.InvoiceDate DESC",
        (cid,)
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
    cid = customer_id.encode() if isinstance(customer_id, str) else customer_id
    row = conn.execute(
        "SELECT CustomerID, CustomerEmail AS CustomerName, CustomerName AS CustomerEmail, CustomerType "
        "FROM Customers WHERE CustomerID = ?",
        (cid,)
    ).fetchone()
    conn.close()
    if row:
        info = dict(row)
        if isinstance(info.get('CustomerID'), bytes):
            info['CustomerID'] = info['CustomerID'].decode()
        return info
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


def recommend_purchase_order(sizing_family, total_qty, days=90):
    conn = get_conn()

    max_date_row = conn.execute(
        "SELECT MAX(COALESCE(PaidDate, InvoiceDate)) AS md FROM Orders"
    ).fetchone()
    max_date = max_date_row['md'] if max_date_row else None
    if not max_date:
        conn.close()
        return {'sizes': [], 'active_customers': 0, 'days': days, 'family': sizing_family}

    rows = conn.execute(
        "SELECT o.OrderEmail, p.SizeNormalized, "
        "MAX(COALESCE(o.PaidDate, o.InvoiceDate)) AS latest "
        "FROM Orders o "
        "JOIN OrderItems oi ON o.OrderNumber = oi.OrderNumber "
        "JOIN Products p ON p.InvProductName = oi.ProductName "
        "WHERE o.OrderType = 'RETAIL' "
        "AND p.SizingFamily = ? "
        "AND COALESCE(o.PaidDate, o.InvoiceDate) >= date(?, '-' || ? || ' days') "
        "GROUP BY o.OrderEmail, p.SizeNormalized "
        "ORDER BY latest DESC",
        (sizing_family, max_date, str(days))
    ).fetchall()
    conn.close()

    # Take each customer's most recent size purchase only
    customer_size = {}
    for r in rows:
        email = r['OrderEmail']
        if email not in customer_size:
            customer_size[email] = normalize_size(r['SizeNormalized'])

    size_counts = defaultdict(int)
    for size in customer_size.values():
        size_counts[size] += 1

    active_customers = len(customer_size)
    if active_customers == 0:
        return {'sizes': [], 'active_customers': 0, 'days': days, 'family': sizing_family}

    ordered_sizes = available_sizes_for_family(sizing_family)
    size_order = {token: ordinal for ordinal, token in ordered_sizes}

    results = []
    for ordinal, token in ordered_sizes:
        count = size_counts.get(token, 0)
        pct = (count / active_customers * 100) if active_customers else 0
        raw_qty = total_qty * count / active_customers if active_customers else 0
        results.append({
            'size': token,
            'customers': count,
            'pct': round(pct, 1),
            'raw_qty': raw_qty,
            'qty': math.floor(raw_qty),
        })

    # Largest-remainder rounding so quantities sum to total_qty
    allocated = sum(r['qty'] for r in results)
    remainder = total_qty - allocated
    by_fraction = sorted(
        range(len(results)),
        key=lambda i: results[i]['raw_qty'] - results[i]['qty'],
        reverse=True,
    )
    for i in by_fraction:
        if remainder <= 0:
            break
        if results[i]['customers'] > 0:
            results[i]['qty'] += 1
            remainder -= 1
    # If still short (more units than customers), distribute to top sizes
    if remainder > 0:
        by_customers = sorted(
            range(len(results)),
            key=lambda i: results[i]['customers'],
            reverse=True,
        )
        while remainder > 0:
            for i in by_customers:
                if results[i]['customers'] > 0 and remainder > 0:
                    results[i]['qty'] += 1
                    remainder -= 1

    for r in results:
        del r['raw_qty']

    return {
        'sizes': results,
        'active_customers': active_customers,
        'days': days,
        'family': sizing_family,
    }
