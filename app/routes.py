import os
import binascii
from datetime import datetime

from flask import render_template, jsonify, request
from app import app
from app.db import get_conn
from app.recommendations import (
    get_customer_purchase_history,
    get_customer_info,
    recommend_for_customer,
)


@app.route("/")
def landing():
    return render_template('landing.html')


@app.route("/dashboard")
def dashboard():
    conn = get_conn()
    customer_count = conn.execute("SELECT COUNT(*) FROM Customers").fetchone()[0]
    product_count = conn.execute("SELECT COUNT(*) FROM Products").fetchone()[0]
    order_count = conn.execute(
        "SELECT COUNT(*) FROM Orders WHERE OrderType = 'RETAIL'"
    ).fetchone()[0]
    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(PaidTotal), 0) FROM Orders WHERE OrderType = 'RETAIL' AND PaidTotal IS NOT NULL"
    ).fetchone()[0]

    now = datetime.now()
    mtd_row = conn.execute(
        "SELECT COALESCE(SUM(PaidTotal), 0) AS rev, COALESCE(SUM(PaidPieces), 0) AS pcs "
        "FROM Orders WHERE OrderType = 'RETAIL' AND PaidDate IS NOT NULL "
        "AND strftime('%%Y', PaidDate) = ? AND strftime('%%m', PaidDate) = ?",
        (str(now.year), f"{now.month:02d}")
    ).fetchone()
    mtd_revenue = mtd_row['rev'] if mtd_row else 0
    mtd_pieces = int(mtd_row['pcs']) if mtd_row else 0

    recent_orders = [dict(r) for r in conn.execute(
        "SELECT OrderNumber, OrderEmail, PaidDate, PaidTotal, PaidPieces "
        "FROM Orders WHERE OrderType = 'RETAIL' AND PaidDate IS NOT NULL "
        "ORDER BY PaidDate DESC LIMIT 10"
    ).fetchall()]

    top_customers = [dict(r) for r in conn.execute(
        "SELECT c.CustomerID, c.CustomerName, "
        "COALESCE(SUM(o.PaidTotal), 0) AS LTV, "
        "COUNT(o.OrderNumber) AS OrderCount "
        "FROM Customers c "
        "LEFT JOIN Orders o ON c.CustomerEmail = o.OrderEmail AND o.OrderType = 'RETAIL' "
        "WHERE c.CustomerType = 'RETAIL' "
        "GROUP BY c.CustomerID "
        "ORDER BY LTV DESC LIMIT 10"
    ).fetchall()]

    conn.close()
    return render_template(
        'dashboard.html',
        customer_count=customer_count,
        product_count=product_count,
        order_count=order_count,
        total_revenue=total_revenue,
        mtd_revenue=mtd_revenue,
        mtd_pieces=mtd_pieces,
        recent_orders=recent_orders,
        top_customers=top_customers,
    )


@app.route("/customers")
def customers():
    conn = get_conn()
    rows = conn.execute(
        "SELECT c.CustomerID, c.CustomerName, c.CustomerEmail, c.CustomerType, "
        "COALESCE(SUM(o.PaidTotal), 0) AS LTV, "
        "COALESCE(SUM(o.PaidPieces), 0) AS TotalPieces, "
        "COUNT(o.OrderNumber) AS OrderCount "
        "FROM Customers c "
        "LEFT JOIN Orders o ON c.CustomerEmail = o.OrderEmail AND o.OrderType = 'RETAIL' "
        "WHERE c.CustomerType = 'RETAIL' "
        "GROUP BY c.CustomerID "
        "ORDER BY LTV DESC"
    ).fetchall()
    conn.close()
    return render_template('customers.html', customers=[dict(r) for r in rows])


@app.route("/customers/<customer_id>")
def customer_detail(customer_id):
    customer = get_customer_info(customer_id)
    if not customer:
        return "Customer not found", 404

    history = get_customer_purchase_history(customer_id)

    conn = get_conn()
    ltv_row = conn.execute(
        "SELECT COALESCE(SUM(PaidTotal), 0) AS LTV, COALESCE(SUM(PaidPieces), 0) AS Pieces, "
        "COUNT(OrderNumber) AS OrderCount "
        "FROM Orders WHERE OrderEmail = ? AND OrderType = 'RETAIL'",
        (customer['CustomerEmail'],)
    ).fetchone()
    conn.close()

    recs = recommend_for_customer(customer_id, n=5)

    return render_template(
        'customer.html',
        customer=customer,
        history=history,
        ltv=ltv_row['LTV'] if ltv_row else 0,
        pieces=int(ltv_row['Pieces']) if ltv_row else 0,
        order_count=ltv_row['OrderCount'] if ltv_row else 0,
        recommendations=recs.get('recommendations', []),
    )


@app.route("/inventory")
def inventory():
    conn = get_conn()
    products = [dict(r) for r in conn.execute(
        "SELECT ProductSKU, ProductName, ProductStyle, ProductSize, "
        "UnitPrice, SizingFamily, SizeNormalized FROM Products ORDER BY ProductStyle, ProductSize"
    ).fetchall()]

    family_counts = [dict(r) for r in conn.execute(
        "SELECT SizingFamily, COUNT(*) AS cnt FROM Products GROUP BY SizingFamily ORDER BY cnt DESC"
    ).fetchall()]

    total_value = conn.execute(
        "SELECT COALESCE(SUM(UnitPrice), 0) FROM Products"
    ).fetchone()[0]

    conn.close()
    return render_template(
        'inventory.html',
        products=products,
        family_counts=family_counts,
        total_value=total_value,
    )


@app.route("/orders")
def orders():
    conn = get_conn()
    all_orders = [dict(r) for r in conn.execute(
        "SELECT o.OrderNumber, o.OrderEmail, o.OrderType, o.InvoiceDate, "
        "o.PaidDate, o.InvTotal, o.PaidTotal, o.InvPieces, o.PaidPieces, "
        "c.CustomerName "
        "FROM Orders o "
        "LEFT JOIN Customers c ON c.CustomerEmail = o.OrderEmail "
        "ORDER BY o.InvoiceDate DESC"
    ).fetchall()]
    conn.close()
    return render_template('orders.html', orders=all_orders)


@app.route("/api/customers/<customer_id>/recommendations")
def api_recommendations(customer_id):
    n = request.args.get('n', 5, type=int)
    result = recommend_for_customer(customer_id, n=n)
    return jsonify(result)


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ['customer_id', 'product_sku', 'size', 'outcome']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    if data['outcome'] not in ('too_small', 'true_to_size', 'too_large'):
        return jsonify({"error": "outcome must be: too_small, true_to_size, or too_large"}), 400

    fid = binascii.b2a_hex(os.urandom(12)).decode()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO FitFeedback VALUES (?, ?, ?, ?, ?, ?, 'explicit', ?)",
            (fid, data['customer_id'], data['product_sku'],
             data.get('order_number'), data['size'], data['outcome'],
             datetime.utcnow().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "saved", "feedback_id": fid}), 201
