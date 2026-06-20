import math
import os
import pickle
from collections import defaultdict
from datetime import timedelta

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


def get_customer_purchase_history(user_id, customer_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT c.CustomerID, c.CustomerName, c.CustomerEmail, "
        "o.OrderNumber, o.InvoiceDate, o.PaidDate, "
        "oi.ProductName, oi.UnitPrice, oi.TotalPrice, oi.OrderLineItem, "
        "p.ProductSKU, p.ProductStyle, p.ProductSize, p.SizingFamily, p.SizeNormalized "
        "FROM Customers c "
        "JOIN Orders o ON c.CustomerEmail = o.OrderEmail AND o.UserID = c.UserID "
        "JOIN OrderItems oi ON o.OrderNumber = oi.OrderNumber AND oi.UserID = o.UserID "
        "LEFT JOIN Products p ON p.InvProductName = oi.ProductName AND p.UserID = c.UserID "
        "WHERE c.CustomerID = %s AND c.UserID = %s AND o.OrderType = 'RETAIL' "
        "ORDER BY o.InvoiceDate DESC",
        (customer_id, user_id)
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


def get_customer_info(user_id, customer_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT CustomerID, CustomerName, CustomerEmail, CustomerType "
        "FROM Customers WHERE CustomerID = %s AND UserID = %s",
        (customer_id, user_id)
    ).fetchone()
    conn.close()
    if row:
        return row
    return None


def recommend_for_customer(user_id, customer_id, n=5):
    _load_artifacts()

    history = get_customer_purchase_history(user_id, customer_id)
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
        "UnitPrice, SizingFamily, SizeNormalized FROM Products WHERE UserID = %s",
        (user_id,)
    ).fetchall():
        product_lookup[r['ProductSKU']] = r
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


def recommend_purchase_order(user_id, sizing_family, total_qty, days=90):
    conn = get_conn()

    max_date_row = conn.execute(
        "SELECT MAX(COALESCE(PaidDate, InvoiceDate)) AS md FROM Orders WHERE UserID = %s",
        (user_id,)
    ).fetchone()
    max_date = max_date_row['md'] if max_date_row else None
    if not max_date:
        conn.close()
        return {'sizes': [], 'active_customers': 0, 'days': days, 'family': sizing_family}

    if hasattr(max_date, 'date'):
        cutoff = max_date - timedelta(days=days)
    else:
        from datetime import datetime
        cutoff = datetime.fromisoformat(str(max_date)) - timedelta(days=days)

    rows = conn.execute(
        "SELECT o.OrderEmail, p.SizeNormalized, "
        "MAX(COALESCE(o.PaidDate, o.InvoiceDate)) AS latest "
        "FROM Orders o "
        "JOIN OrderItems oi ON o.OrderNumber = oi.OrderNumber AND oi.UserID = o.UserID "
        "JOIN Products p ON p.InvProductName = oi.ProductName AND p.UserID = o.UserID "
        "WHERE o.OrderType = 'RETAIL' "
        "AND o.UserID = %s "
        "AND p.SizingFamily = %s "
        "AND COALESCE(o.PaidDate, o.InvoiceDate) >= %s "
        "GROUP BY o.OrderEmail, p.SizeNormalized "
        "ORDER BY latest DESC",
        (user_id, sizing_family, cutoff)
    ).fetchall()
    conn.close()

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
