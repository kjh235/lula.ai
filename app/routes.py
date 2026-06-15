import asyncio
import os
import sqlite3
import binascii
from datetime import datetime

from flask import render_template, jsonify, request, redirect, url_for, flash
from app import app
from app.db import get_conn
from credential_manager import save_credentials, get_credentials, delete_credentials, PLATFORM_BLESS
from app.recommendations import (
    get_customer_purchase_history,
    get_customer_info,
    recommend_for_customer,
    recommend_purchase_order,
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
    cust_list = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get('CustomerID'), bytes):
            d['CustomerID'] = d['CustomerID'].decode()
        cust_list.append(d)
    return render_template('customers.html', customers=cust_list)


@app.route("/customers/<customer_id>")
def customer_detail(customer_id):
    customer = get_customer_info(customer_id)
    if not customer:
        return "Customer not found", 404

    history = get_customer_purchase_history(customer_id)

    conn = get_conn()
    ltv_row = conn.execute(
        "SELECT COALESCE(SUM(PaidTotal), 0) AS LTV, COALESCE(SUM(PaidPieces), 0) AS Pieces, "
        "COUNT(OrderNumber) AS OrderCount, "
        "CASE WHEN COUNT(OrderNumber) > 0 THEN COALESCE(SUM(PaidTotal), 0) / COUNT(OrderNumber) ELSE 0 END AS AvgOrderValue, "
        "MIN(COALESCE(PaidDate, InvoiceDate)) AS FirstOrderDate, "
        "MAX(COALESCE(PaidDate, InvoiceDate)) AS LastOrderDate "
        "FROM Orders WHERE OrderEmail = ? AND OrderType = 'RETAIL'",
        (customer['CustomerEmail'],)
    ).fetchone()

    recent_orders = [dict(r) for r in conn.execute(
        "SELECT OrderNumber, InvoiceDate, PaidDate, PaidTotal, PaidPieces "
        "FROM Orders WHERE OrderEmail = ? AND OrderType = 'RETAIL' "
        "ORDER BY COALESCE(PaidDate, InvoiceDate) DESC LIMIT 5",
        (customer['CustomerEmail'],)
    ).fetchall()]
    conn.close()

    return render_template(
        'customer.html',
        customer=customer,
        history=history,
        ltv=ltv_row['LTV'] if ltv_row else 0,
        pieces=int(ltv_row['Pieces']) if ltv_row else 0,
        order_count=ltv_row['OrderCount'] if ltv_row else 0,
        avg_order_value=ltv_row['AvgOrderValue'] if ltv_row else 0,
        first_order_date=ltv_row['FirstOrderDate'] if ltv_row else None,
        last_order_date=ltv_row['LastOrderDate'] if ltv_row else None,
        recent_orders=recent_orders,
    )


@app.route("/inventory")
def inventory():
    conn = get_conn()
    raw = conn.execute(
        "SELECT p.ProductSKU, p.ProductName, p.ProductStyle, p.ProductSize, "
        "p.UnitPrice, p.SizingFamily, p.SizeNormalized, p.ProductFamily, "
        "COALESCE(SUM(l.Delta), 0) AS Quantity "
        "FROM Products p "
        "LEFT JOIN InventoryLedger l ON l.ProductName = p.ProductName "
        "GROUP BY p.ProductSKU "
        "ORDER BY p.ProductStyle, p.ProductSize"
    ).fetchall()
    products = []
    for r in raw:
        p = dict(r)
        price = p['UnitPrice']
        if isinstance(price, str):
            price = float(price.replace('$', '').replace(',', '') or 0)
        p['UnitPrice'] = float(price or 0)
        products.append(p)

    style_counts = [dict(r) for r in conn.execute(
        "SELECT ProductStyle, COUNT(*) AS cnt FROM Products "
        "GROUP BY ProductStyle ORDER BY cnt DESC"
    ).fetchall()]

    total_value = sum(p['UnitPrice'] for p in products)
    total_units = sum(p['Quantity'] for p in products)

    conn.close()
    return render_template(
        'inventory.html',
        products=products,
        style_counts=style_counts,
        total_value=total_value,
        total_units=total_units,
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


@app.route("/purchase-order")
def purchase_order():
    conn = get_conn()
    families = [r[0] for r in conn.execute(
        "SELECT DISTINCT SizingFamily FROM Products WHERE SizingFamily IS NOT NULL ORDER BY SizingFamily"
    ).fetchall()]
    conn.close()

    selected_family = request.args.get('family', '')
    total_qty = request.args.get('qty', 0, type=int)
    result = None

    if selected_family and total_qty > 0:
        result = recommend_purchase_order(selected_family, total_qty)

    return render_template(
        'purchase_order.html',
        families=families,
        selected_family=selected_family,
        total_qty=total_qty,
        result=result,
    )


_MATCHED_SALES_CTE = """
    matched_sales AS (
        SELECT oi.OrderItemID, oi.TotalPrice, o.PaidDate,
            COALESCE(
                (SELECT p1.ProductSKU FROM Products p1
                 WHERE p1.InvProductName = oi.ProductName LIMIT 1),
                (SELECT p2.ProductSKU FROM Products p2
                 WHERE oi.ProductName LIKE ('% ' || p2.ProductStyle || ' ' || p2.ProductSize)
                    OR oi.ProductName = (p2.ProductStyle || ' ' || p2.ProductSize)
                 LIMIT 1)
            ) AS ProductSKU
        FROM OrderItems oi
        JOIN Orders o ON o.OrderNumber = oi.OrderNumber
        WHERE o.OrderType = 'RETAIL' AND o.PaidDate IS NOT NULL
    )
"""


@app.route("/purchase-orders")
def purchase_orders():
    conn = get_conn()
    rows = conn.execute(
        "WITH " + _MATCHED_SALES_CTE +
        "SELECT "
        "  po.OrderNumber, po.OrderDate, po.Total AS TotalCost, "
        "  pos.TotalUnitsOrdered, "
        "  COUNT(ms.OrderItemID) AS TotalUnitsSold, "
        "  COALESCE(SUM(ms.TotalPrice), 0) AS TotalRevenue "
        "FROM PurchaseOrders po "
        "LEFT JOIN ("
        "  SELECT OrderNumber, SUM(Quantity) AS TotalUnitsOrdered "
        "  FROM PurchaseOrderItems GROUP BY OrderNumber"
        ") pos ON pos.OrderNumber = po.OrderNumber "
        "LEFT JOIN PurchaseOrderItems poi ON poi.OrderNumber = po.OrderNumber "
        "LEFT JOIN matched_sales ms ON ms.ProductSKU = poi.ProductSKU "
        "  AND ms.PaidDate >= po.OrderDate "
        "GROUP BY po.OrderNumber, po.OrderDate, po.Total, pos.TotalUnitsOrdered "
        "  SELECT oi.OrderItemID, oi.ProductName, oi.TotalPrice, o.PaidDate "
        "  FROM OrderItems oi "
        "  JOIN Orders o ON o.OrderNumber = oi.OrderNumber "
        "  WHERE o.OrderType = 'RETAIL' AND o.PaidDate IS NOT NULL "
        ") rs ON rs.ProductName = p.InvProductName AND rs.PaidDate >= po.OrderDate "
        "WHERE poi.ProductSKU NOT IN ('5PctOff') "
        "GROUP BY po.OrderNumber, po.OrderDate, po.Total "
        "ORDER BY po.OrderDate DESC"
    ).fetchall()
    conn.close()

    po_list = []
    for r in rows:
        d = dict(r)
        ordered = d['TotalUnitsOrdered'] or 0
        sold = min(d['TotalUnitsSold'] or 0, ordered)
        cost = float(d['TotalCost'] or 0)
        revenue = float(d['TotalRevenue'] or 0)
        d['SellThroughPct'] = round(sold / ordered * 100, 1) if ordered else 0
        d['CostRecoveryPct'] = round(revenue / cost * 100, 1) if cost else 0
        d['TotalUnitsSoldCapped'] = sold
        d['TotalCost'] = cost
        d['TotalRevenue'] = revenue
        po_list.append(d)

    total_pos = len(po_list)
    total_ordered = sum(p['TotalUnitsOrdered'] or 0 for p in po_list)
    total_sold = sum(p['TotalUnitsSoldCapped'] for p in po_list)
    overall_sell_thru = round(total_sold / total_ordered * 100, 1) if total_ordered else 0
    total_revenue = sum(p['TotalRevenue'] for p in po_list)

    return render_template(
        'purchase_orders.html',
        po_list=po_list,
        total_pos=total_pos,
        total_ordered=total_ordered,
        overall_sell_thru=overall_sell_thru,
        total_revenue=total_revenue,
    )


@app.route("/purchase-orders/<order_number>")
def purchase_order_detail(order_number):
    conn = get_conn()

    po = conn.execute(
        "SELECT * FROM PurchaseOrders WHERE OrderNumber = ?", (order_number,)
    ).fetchone()
    if not po:
        conn.close()
        return "Purchase order not found", 404
    po = dict(po)

    items = [dict(r) for r in conn.execute(
        "WITH " + _MATCHED_SALES_CTE +
        "SELECT "
        "  poi.ProductSKU, poi.ProductName AS POProductName, "
        "  poi.Quantity AS UnitsOrdered, poi.CostPerUnit, poi.TotalCost, "
        "  p.InvProductName, p.UnitPrice AS RetailPrice, "
        "  COUNT(ms.OrderItemID) AS UnitsSold, "
        "  COALESCE(SUM(ms.TotalPrice), 0) AS Revenue, "
        "  CASE WHEN COUNT(ms.OrderItemID) > 0 "
        "       THEN ROUND(AVG(JULIANDAY(ms.PaidDate) - JULIANDAY(po.OrderDate)), 1) "
        "  COALESCE(SUM(rs.UnitsSold), 0) AS UnitsSold, "
        "  COALESCE(SUM(rs.TotalRevenue), 0) AS Revenue, "
        "  CASE WHEN COUNT(rs.UnitsSold) > 0 "
        "       THEN ROUND(AVG(JULIANDAY(rs.PaidDate) - JULIANDAY(po.OrderDate)), 1) "
        "       ELSE NULL END AS AvgDaysToSell "
        "FROM PurchaseOrderItems poi "
        "JOIN PurchaseOrders po ON poi.OrderNumber = po.OrderNumber "
        "LEFT JOIN Products p ON p.ProductSKU = poi.ProductSKU "
        "LEFT JOIN matched_sales ms ON ms.ProductSKU = poi.ProductSKU "
        "  AND ms.PaidDate >= po.OrderDate "
        "WHERE poi.OrderNumber = ? "
        "LEFT JOIN ("
        " select OIS.ProductName, count(OIS.OrderItemID) as UnitsSold, sum(OIS.TotalPrice) as TotalRevenue, OIS.OrderNumber, OIS.PaidDate FROM "
        "  (SELECT oi.OrderItemID, oi.ProductName, oi.TotalPrice, o.PaidDate, o.OrderNumber "
        "  FROM OrderItems oi "
        "  JOIN Orders o ON o.OrderNumber = oi.OrderNumber ) as OIS "
        "  GROUP BY 	OIS.OrderNumber, OIS.PaidDate,OIS.ProductName "
        ") rs ON rs.ProductName = p.InvProductName AND rs.PaidDate >= po.OrderDate "
        "WHERE poi.OrderNumber = ? and poi.ProductSKU NOT IN ('5PctOff') "
        "GROUP BY poi.PurchaseItemID, poi.ProductSKU, poi.ProductName, "
        "         poi.Quantity, poi.CostPerUnit, poi.TotalCost, "
        "         p.InvProductName, p.UnitPrice "
        "ORDER BY poi.ProductName",
        (order_number,)
    ).fetchall()]
    conn.close()

    for item in items:
        units_ordered = item['UnitsOrdered'] or 1
        units_sold = item['UnitsSold'] or 0
        sold_capped = min(units_sold, units_ordered)
        item['UnitsSoldCapped'] = sold_capped
        item['SellThroughPct'] = round(sold_capped / units_ordered * 100, 1)
        cost = float(item['TotalCost'] or 0)
        revenue = float(item['Revenue'] or 0)
        item['TotalCost'] = cost
        item['Revenue'] = revenue
        item['CostRecoveryPct'] = round(revenue / cost * 100, 1) if cost else 0

    total_ordered = sum(i['UnitsOrdered'] or 0 for i in items)
    total_sold = sum(i['UnitsSoldCapped'] for i in items)
    total_cost = sum(i['TotalCost'] for i in items)
    total_revenue = sum(i['Revenue'] for i in items)
    sell_thru_pct = round(total_sold / total_ordered * 100, 1) if total_ordered else 0
    cost_recov_pct = round(total_revenue / total_cost * 100, 1) if total_cost else 0
    days_list = [i['AvgDaysToSell'] for i in items if i['AvgDaysToSell'] is not None]
    avg_days = round(sum(days_list) / len(days_list), 1) if days_list else None

    return render_template(
        'purchase_order_detail.html',
        po=po,
        items=items,
        total_ordered=total_ordered,
        total_sold=total_sold,
        sell_thru_pct=sell_thru_pct,
        total_cost=total_cost,
        total_revenue=total_revenue,
        cost_recov_pct=cost_recov_pct,
        avg_days=avg_days,
    )


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


@app.route("/admin/sync-status")
def sync_status():
    master_path = app.config['MASTER_DB_PATH']
    try:
        conn = sqlite3.connect(master_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT TableName, LastSyncedAt, RowsSynced FROM SyncLog ORDER BY TableName"
        ).fetchall()
        conn.close()
        return jsonify({"tables": [dict(r) for r in rows]})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/admin/sync-now", methods=["POST"])
def sync_now():
    from app.master_sync import run_full_sync
    try:
        result = run_full_sync(app.config['DB_PATH'], app.config['MASTER_DB_PATH'])
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/settings/credentials", methods=["GET"])
def credentials_settings():
    db_path = app.config['DB_PATH']
    existing = get_credentials(db_path, PLATFORM_BLESS)
    last_sync = _last_bless_sync(db_path)
    return render_template(
        "settings_credentials.html",
        username=existing[0] if existing else None,
        last_sync=last_sync,
    )


@app.route("/settings/credentials", methods=["POST"])
def credentials_settings_save():
    db_path = app.config['DB_PATH']
    action = request.form.get("action", "save")

    if action == "delete":
        delete_credentials(db_path, PLATFORM_BLESS)
        flash("Credentials removed.", "info")
        return redirect(url_for("credentials_settings"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("credentials_settings"))

    save_credentials(db_path, PLATFORM_BLESS, username, password)

    # Validate by attempting a login in the background (non-blocking)
    from lularoe_scraper import BlessScraper
    from app import _scheduler
    _scheduler.add_job(
        func=lambda: asyncio.run(BlessScraper(db_path).run()),
        id="bless_scrape_immediate",
        replace_existing=True,
    )

    flash("Credentials saved. A sync has been queued.", "success")
    return redirect(url_for("credentials_settings"))


@app.route("/admin/scrape-now", methods=["POST"])
def scrape_now():
    from lularoe_scraper import BlessScraper
    try:
        result = asyncio.run(BlessScraper(app.config['DB_PATH']).run())
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _last_bless_sync(db_path):
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT LastSyncedAt, RowsSynced FROM SyncLog "
            "WHERE TableName LIKE 'bless_scrape_%' ORDER BY LastSyncedAt DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return {"synced_at": row[0], "rows": row[1]} if row else None
    except Exception:
        return None
