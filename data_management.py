import sqlite3
import os
import binascii
import re
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _parse_money(value):
    return value.lstrip("$").replace(',', '')


def init_db(db_path="app/bless.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CUSTOMERS (
        CustomerID TEXT PRIMARY KEY NOT NULL,
        CustomerEmail TEXT UNIQUE NOT NULL,
        CustomerName TEXT NOT NULL,
        CustomerType TEXT NOT NULL,
        CustomerPhone TEXT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Products (
        ProductID TEXT PRIMARY KEY NOT NULL,
        ProductSKU TEXT UNIQUE NOT NULL,
        ProductName TEXT NOT NULL,
        ProductSize TEXT NOT NULL,
        ProductStyle TEXT NOT NULL,
        UnitPrice REAL NOT NULL,
        InvProductName TEXT NOT NULL,
        ProductCategory TEXT NULL,
        ProductFamily TEXT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS PurchaseOrders (
        OrderID TEXT PRIMARY KEY,
        OrderNumber TEXT UNIQUE NOT NULL,
        OrderEmail TEXT NOT NULL,
        OrderDate DATETIME NOT NULL,
        Subtotal REAL NOT NULL,
        Shipping REAL NOT NULL,
        Taxes REAL NOT NULL,
        Total REAL NOT NULL,
        Pieces REAL NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS PurchaseOrderItems (
        PurchaseItemID TEXT UNIQUE NOT NULL PRIMARY KEY,
        OrderNumber TEXT NOT NULL,
        ProductSKU TEXT,
        ProductName TEXT,
        Quantity INTEGER,
        CostPerUnit REAL,
        TotalCost REAL,
        LlrPieces REAL,
        FOREIGN KEY (OrderNumber) REFERENCES PurchaseOrders(OrderNumber),
        FOREIGN KEY (ProductSKU) REFERENCES Products(ProductSKU)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS RetailOrders (
        OrderID TEXT PRIMARY KEY,
        OrderNumber TEXT UNIQUE NOT NULL,
        OrderPopUp TEXT NOT NULL,
        OrderEmail TEXT NOT NULL,
        InvoiceDate DATETIME NOT NULL,
        InvSubtotal REAL NOT NULL,
        InvTaxes REAL NOT NULL,
        InvShipping REAL NOT NULL,
        InvShippingTaxes REAL NOT NULL,
        InvDiscount REAL NOT NULL,
        InvTotal REAL NOT NULL,
        InvPieces REAL NOT NULL,
        PaidDate DATETIME NULL,
        PaidSubtotal REAL NULL,
        PaidShipping REAL NULL,
        PaidTaxes REAL NULL,
        PaidShippingTaxes REAL NULL,
        PaidDiscount REAL NULL,
        PaidTotal REAL NULL,
        PaidPieces REAL NULL,
        ShipAddr1 TEXT NULL,
        ShipAddr2 TEXT NULL,
        City TEXT NULL,
        State TEXT NULL,
        Zip TEXT NULL,
        FOREIGN KEY (OrderEmail) REFERENCES CUSTOMERS(CustomerEmail)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Orders (
        OrderID TEXT PRIMARY KEY,
        OrderNumber TEXT UNIQUE NOT NULL,
        OrderPopUp TEXT NOT NULL,
        OrderEmail TEXT NOT NULL,
        InvoiceDate DATETIME NOT NULL,
        InvSubtotal REAL NOT NULL,
        InvTaxes REAL NOT NULL,
        InvShipping REAL NOT NULL,
        InvShippingTaxes REAL NOT NULL,
        InvDiscount REAL NOT NULL,
        InvTotal REAL NOT NULL,
        InvPieces REAL NOT NULL,
        PaidDate DATETIME NULL,
        PaidSubtotal REAL NULL,
        PaidShipping REAL NULL,
        PaidTaxes REAL NULL,
        PaidShippingTaxes REAL NULL,
        PaidDiscount REAL NULL,
        PaidTotal REAL NULL,
        PaidPieces REAL NULL,
        ShipAddr1 TEXT NULL,
        ShipAddr2 TEXT NULL,
        City TEXT NULL,
        State TEXT NULL,
        Zip TEXT NULL,
        OrderType TEXT NULL,
        FOREIGN KEY (OrderEmail) REFERENCES CUSTOMERS(CustomerEmail)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS OrderItems (
        OrderItemID TEXT UNIQUE NOT NULL PRIMARY KEY,
        OrderNumber TEXT NOT NULL,
        OrderLineItem TEXT NOT NULL,
        ProductName TEXT,
        UnitPrice REAL,
        DiscountPrice REAL,
        TotalPrice REAL,
        FOREIGN KEY (OrderNumber) REFERENCES Orders(OrderNumber),
        FOREIGN KEY (ProductName) REFERENCES Products(ProductName),
        UNIQUE (OrderNumber,OrderLineItem)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS InventoryLedger (
        LedgerID    TEXT PRIMARY KEY,
        ProductName TEXT NOT NULL,
        Delta       INTEGER NOT NULL,
        EventType   TEXT NOT NULL
                    CHECK (EventType IN (
                        'RETAIL_SALE',
                        'TRANSFER_IN',
                        'TRANSFER_OUT',
                        'PO_RECEIVED',
                        'MANUAL_ADJUSTMENT'
                    )),
        OrderNumber TEXT,
        EventDate   DATETIME NOT NULL,
        FOREIGN KEY (ProductName) REFERENCES Products(ProductName),
        UNIQUE (OrderNumber, ProductName)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Tasks (
        taskID TEXT UNIQUE NOT NULL PRIMARY KEY,
        taskName TEXT UNIQUE NOT NULL,
        lastStartTime TEXT NULL,
        lastEndTime TEXT NULL
    )
    ''')

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_product ON InventoryLedger(ProductName)")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_invname ON Products(InvProductName)")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE Products ADD COLUMN SizeNormalized TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE Products ADD COLUMN SizingFamily TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE Products ADD COLUMN ProductFamily TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS FitFeedback (
        FeedbackID TEXT PRIMARY KEY,
        CustomerID TEXT NOT NULL,
        ProductSKU TEXT NOT NULL,
        OrderNumber TEXT,
        SizePurchased TEXT NOT NULL,
        FitOutcome TEXT NOT NULL CHECK (FitOutcome IN ('too_small','true_to_size','too_large')),
        Source TEXT NOT NULL CHECK (Source IN ('explicit','implicit_repeat')),
        CreatedAt TEXT NOT NULL,
        FOREIGN KEY (CustomerID) REFERENCES CUSTOMERS(CustomerID)
    )
    ''')
    conn.commit()

    try:
        cursor.execute("CREATE INDEX idx_fitfb_customer ON FitFeedback(CustomerID)")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("CREATE INDEX idx_fitfb_sku ON FitFeedback(ProductSKU)")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Subscriptions (
        ID TEXT PRIMARY KEY,
        StripeSubscriptionID TEXT UNIQUE NOT NULL,
        StripeCustomerID TEXT,
        CustomerEmail TEXT,
        Status TEXT NOT NULL DEFAULT 'active',
        CreatedAt TEXT NOT NULL
    )
    ''')
    conn.commit()

    from app.sizing import classify_family, normalize_size as _normalize_size, classify_product_family
    needs_backfill = cursor.execute(
        "SELECT COUNT(*) FROM Products WHERE SizingFamily IS NULL"
    ).fetchone()[0]
    if needs_backfill > 0:
        rows = cursor.execute(
            "SELECT ProductID, ProductStyle, ProductSize FROM Products WHERE SizingFamily IS NULL"
        ).fetchall()
        for row in rows:
            pid, style, size = row[0], row[1], row[2]
            family = classify_family(style, size)
            norm = _normalize_size(size)
            cursor.execute(
                "UPDATE Products SET SizingFamily=?, SizeNormalized=? WHERE ProductID=?",
                (family, norm, pid)
            )
        conn.commit()

    needs_family_backfill = cursor.execute(
        "SELECT COUNT(*) FROM Products WHERE ProductFamily IS NULL"
    ).fetchone()[0]
    if needs_family_backfill > 0:
        rows = cursor.execute(
            "SELECT ProductID, ProductName, ProductStyle, SizingFamily FROM Products WHERE ProductFamily IS NULL"
        ).fetchall()
        for row in rows:
            pid, name, style, sizing_fam = row[0], row[1], row[2], row[3]
            product_family = classify_product_family(name, style, sizing_fam)
            cursor.execute(
                "UPDATE Products SET ProductFamily=? WHERE ProductID=?",
                (product_family, pid)
            )
        conn.commit()

    conn.close()


def insert_customer(dbconn, customerrec):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    try:
        row = cursor.execute(
            "SELECT CustomerID FROM Customers WHERE CustomerEmail = ?",
            (customerrec[1],)
        ).fetchone()

        if row is None:
            cursor.execute("INSERT OR IGNORE INTO Customers VALUES (?, ?, ?, ?, null)",
                           (UUID, customerrec[1], customerrec[0], customerrec[2])
                           )
            dbconn.commit()
            logger.warning("adding customer ...")
        logger.debug("customer saved")
    except sqlite3.Error as e:
        logger.error("Customer failed to save: %s", e)
        dbconn.rollback()


def insert_product(dbconn, productrec):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    cost = float(productrec[2].replace('$', ''))
    try:
        row = cursor.execute(
            "SELECT ProductID FROM Products WHERE ProductSKU = ?",
            (productrec[0],)
        ).fetchone()

        if row is None:

            cursor.execute("INSERT INTO Products VALUES (?, ?, ?, ?, ?, ?, ?, null, null, null)",
                       (UUID, productrec[0], productrec[1], productrec[4], productrec[3], cost, productrec[5])
                       )
            dbconn.commit()
        logger.debug("product saved")
    except sqlite3.Error as e:
        logger.error("Product failed to save: %s", e)
        dbconn.rollback()


def update_product(dbconn, translations_path=None):
    import pandas as pd
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    if translations_path is None:
        translations_path = os.path.join(os.path.dirname(__file__), "product_name_translations.json")
    with open(translations_path, "r") as f:
        translations = json.load(f)
    df_prod = pd.read_sql_query("SELECT ProductID, ProductName from Products", dbconn)
    for index, row in df_prod.iterrows():
        ProductID = row['ProductID']
        ProductName = row['ProductName']
        InvProductName = re.sub(r'(?<=)(\w+)(?=)', lambda m: translations.get(m.group(), m.group()), row['ProductName'])
        try:
            cursor.execute("UPDATE Products SET InvProductName=? WHERE ProductID =?", (InvProductName, ProductID))
            dbconn.commit()
            logger.debug("product saved")
        except sqlite3.Error as e:
            logger.error("Product failed to save: %s", e)
            dbconn.rollback()


def insert_purchase_order(dbconn, purchase_order_rec):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = purchase_order_rec[0]
    OrderEmail = purchase_order_rec[1]
    try:
        OrderDate = datetime.strptime(purchase_order_rec[2], "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        OrderDate = datetime.strptime(purchase_order_rec[2], "%m/%d/%Y %I:%M:%S")
    Subtotal = _parse_money(purchase_order_rec[3])
    Shipping = _parse_money(purchase_order_rec[4])
    Taxes = _parse_money(purchase_order_rec[5])
    Total = _parse_money(purchase_order_rec[6])
    Pieces = purchase_order_rec[7]

    try:
        row = cursor.execute(
            "SELECT OrderID FROM PurchaseOrders WHERE OrderNumber = ?",
            (OrderNumber,)
        ).fetchone()

        if row is None:
            cursor.execute("INSERT INTO PurchaseOrders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (UUID, OrderNumber, OrderEmail, OrderDate,
                            float(Subtotal), float(Shipping), float(Taxes),
                            float(Total), float(Pieces))
                           )
            dbconn.commit()
        logger.debug("purchase order saved")
    except sqlite3.Error as e:
        logger.error("purchase order failed to save: %s", e)
        dbconn.rollback()


def insert_purchase_order_item(dbconn, purchasedItemsRec, purchaseOrderNumber):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = purchaseOrderNumber
    ProductSKU = purchasedItemsRec[2]
    ProductName = purchasedItemsRec[3]
    Quantity = purchasedItemsRec[1]
    CostPerUnit = _parse_money(purchasedItemsRec[5])
    TotalCost = _parse_money(purchasedItemsRec[6])
    LlrPieces = purchasedItemsRec[4]
    try:
        cursor.execute("INSERT INTO PurchaseOrderItems VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (UUID, OrderNumber, ProductSKU, ProductName, Quantity, CostPerUnit,
                    TotalCost, LlrPieces)
                   )
        dbconn.commit()
        logger.debug("PO item saved")
    except sqlite3.Error as e:
        logger.error("PO item failed to save: %s", e)
        dbconn.rollback()


def insert_order(dbconn, retail_inv_rec, count_items):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = retail_inv_rec[3]
    OrderPopup = retail_inv_rec[4]
    OrderEmail = retail_inv_rec[1]
    d_date = retail_inv_rec[2].replace(' PST', '')
    try:
        InvDate = datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    except ValueError:
        InvDate = datetime.strptime(d_date, "%b %d %Y %I:%M")
    InvSubtotal = _parse_money(retail_inv_rec[5])
    InvShipping = _parse_money(retail_inv_rec[7])
    InvTaxes = _parse_money(retail_inv_rec[6])
    InvShippingTaxes = _parse_money(retail_inv_rec[8])
    InvDisc = 0
    InvTotal = _parse_money(retail_inv_rec[9])
    InvPieces = count_items

    try:
        row = cursor.execute(
            "SELECT OrderID FROM Orders WHERE OrderNumber = ?",
            (OrderNumber,)
        ).fetchone()

        if row is None:
            cursor.execute("INSERT INTO Orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, null,"
                           "null, null, null, null, null, null, null, null, null, null, null, null, null)",
                           (UUID, OrderNumber, OrderPopup, OrderEmail, InvDate,
                            float(InvSubtotal), float(InvTaxes), float(InvShipping), float(InvShippingTaxes),
                            float(InvDisc), float(InvTotal), float(InvPieces))
                           )
            dbconn.commit()
            logger.debug("order saved")
    except sqlite3.Error as e:
        logger.error("order failed to save: %s", e)
        dbconn.rollback()


def update_paid_order(conn, summary, numberOfItems, emailTime):
    UUID = binascii.b2a_hex(os.urandom(12))

    cursor = conn.cursor()
    d_date = summary[2].replace(' PST', '')
    PaidDate = emailTime
    try:
        PaidDate = datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    except ValueError:
        PaidDate = datetime.strptime(d_date, "%b %d %Y %I:%M")
    PaidSubtotal = _parse_money(summary[5])
    PaidShipping = _parse_money(summary[7])
    PaidTaxes = _parse_money(summary[6])
    PaidShipTaxes = _parse_money(summary[8])
    PaidDisc = 0
    PaidTotal = _parse_money(summary[9])
    PaidPieces = numberOfItems
    addr1 = summary[10]
    addr2 = summary[11]
    city = summary[12]
    state = summary[13]
    zip = summary[14]

    try:
        cursor.execute(
            """UPDATE Orders SET PaidDate=?, PaidSubtotal=?, PaidShipping=?,
               PaidTaxes=?, PaidShippingTaxes=?, PaidDiscount=?, PaidTotal=?,
               PaidPieces=?, ShipAddr1=?, ShipAddr2=?, City=?, State=?, Zip=?
               WHERE OrderNumber=?""",
            (PaidDate, float(PaidSubtotal), float(PaidShipping),
             float(PaidTaxes), float(PaidShipTaxes), float(PaidDisc),
             float(PaidTotal), float(PaidPieces), addr1, addr2,
             city, state, zip, summary[3])
        )
        conn.commit()
        logger.debug("order saved")
    except sqlite3.Error as e:
        logger.error("order failed to save: %s", e)
        conn.rollback()


def update_transfer_type(conn, summary, my_email):
    cursor = conn.cursor()
    if summary[1] == my_email:
        cursor.execute("UPDATE TransferOrders SET TransferInOut=? WHERE OrderNumber =?", ("IN", summary[3]))
        conn.commit()
    else:
        cursor.execute("UPDATE TransferOrders SET TransferInOut=? WHERE OrderNumber =?", ("OUT", summary[3]))
        conn.commit()
    return


def update_order_type(conn, orderNumber, type):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Orders SET OrderType=? WHERE OrderNumber =?", (type, orderNumber))
        conn.commit()
    except Exception:
        logger.error("order type failed to save")


def insert_order_item(conn, items, orderNumber):
    cursor = conn.cursor()
    UUID = binascii.b2a_hex(os.urandom(12))
    if type(items[0]) is str:
        itemName = items[0]
        itemPrice = _parse_money(items[1])
        itemDisc = 0
        itemTotal = itemPrice
        itemLine = items[2]
    else:
        itemName = items[0][0]
        itemPrice = _parse_money(items[0][1])
        itemDisc = _parse_money(items[1][1].lstrip("-"))
        itemTotal = float(itemPrice) - float(itemDisc)
        itemLine = items[0][2]
    try:
        cursor.execute("INSERT OR IGNORE INTO OrderItems VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (UUID, orderNumber, itemLine, itemName, float(itemPrice), float(itemDisc), float(itemTotal)))
        conn.commit()
        logger.debug("order item saved")
    except sqlite3.Error as e:
        logger.error("order item failed to save: %s", e)
        conn.rollback()


def update_task_start_time(conn, task, time):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Task SET lastStartTime=? WHERE taskName =?", (time, task))
        conn.commit()
        return
    except sqlite3.Error as e:
        logger.error("task failed to save: %s", e)
        conn.rollback()


def update_task_end_time(conn, task, time):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Task SET lastEndTime=? WHERE taskName =?", (time, task))
        conn.commit()
        return
    except sqlite3.Error as e:
        logger.error("task failed to save: %s", e)
        conn.rollback()


def init_task(conn, task):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Tasks VALUES (?, ?, null, null)",
                    (UUID, task))
        conn.commit()
        return
    except sqlite3.Error as e:
        logger.error("task failed to save: %s", e)
        conn.rollback()



def record_inventory_event(conn, product_name, delta, event_type, order_number, event_date):
    """Insert a single row into InventoryLedger.

    Uses ``INSERT OR IGNORE`` so duplicate calls for the same
    ``(order_number, product_name)`` combination are silently discarded —
    the unique constraint provides idempotency with no extra bookkeeping.

    Args:
        conn: open sqlite3 connection to bless.db
        product_name (str): Products.ProductName (FK)
        delta (int): stock change — positive = stock added, negative = stock removed
        event_type (str): one of ``'RETAIL_SALE'``, ``'TRANSFER_IN'``,
            ``'TRANSFER_OUT'``, ``'PO_RECEIVED'``, ``'MANUAL_ADJUSTMENT'``
        order_number (str | None): Orders/PurchaseOrders.OrderNumber,
            or ``None`` for manual adjustments
        event_date: datetime or ISO string for when the event occurred

    Returns:
        bool: ``True`` if a new row was inserted, ``False`` if it already existed.
    """
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO InventoryLedger "
            "(LedgerID, ProductName, Delta, EventType, OrderNumber, EventDate) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (UUID, product_name, delta, event_type, order_number, event_date),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error("inventory event failed to save: %s", e)
        conn.rollback()
    inserted = cursor.rowcount > 0
    if inserted:
        logger.info(
            "record_inventory_event: %+d '%s' [%s] order=%s",
            delta, product_name, event_type, order_number,
        )
    return inserted


def apply_order_to_inventory(conn, order_number):
    """Record InventoryLedger events for all items in a single paid order.

    Direction is determined by ``OrderType``:

    ============  ===========  =============================
    OrderType     Event type   Delta per item
    ============  ===========  =============================
    RETAIL        RETAIL_SALE  ``-count`` (stock leaves)
    TRANSFER_IN   TRANSFER_IN  ``+count`` (stock arrives)
    TRANSFER_OUT  TRANSFER_OUT ``-count`` (stock leaves)
    ============  ===========  =============================

    One ledger row is written per ``(OrderNumber, ProductName)`` group via
    ``INSERT OR IGNORE``, so this function is safe to call repeatedly.

    Args:
        conn: open sqlite3 connection to bless.db
        order_number (str): ``Orders.OrderNumber`` to process

    Returns:
        int: number of new ledger rows inserted (0 if the order is not paid,
             has an unrecognised type, was not found, or all rows already exist).
    """
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT OrderType, PaidDate FROM Orders WHERE OrderNumber = ?",
            (order_number,)
        ).fetchone()
    except sqlite3.Error as e:
        logger.error("inventory failed to save: %s", e)
        conn.rollback()

    if row is None:
        logger.warning("apply_order_to_inventory: order %s not found", order_number)
        return 0

    order_type, paid_date = row[0], row[1]

    if paid_date is None:
        logger.info(
            "apply_order_to_inventory: order %s not paid yet — skipping",
            order_number,
        )
        return 0

    event_type_map = {
        "RETAIL":       "RETAIL_SALE",
        "TRANSFER_IN":  "TRANSFER_IN",
        "TRANSFER_OUT": "TRANSFER_OUT",
    }
    if order_type not in event_type_map:
        logger.warning(
            "apply_order_to_inventory: order %s has unrecognised type '%s' — skipping",
            order_number, order_type,
        )
        return 0

    event_type = event_type_map[order_type]
    delta_sign = 1 if order_type == "TRANSFER_IN" else -1

    # One ledger row per (OrderNumber, ProductName) — count rows for quantity
    items = cursor.execute(
        "SELECT ProductName, COUNT(*) AS qty "
        "FROM OrderItems WHERE OrderNumber = ? GROUP BY ProductName",
        (order_number,)
    ).fetchall()

    if not items:
        logger.warning(
            "apply_order_to_inventory: no items found for order %s — skipping",
            order_number,
        )
        return 0

    inserted = 0
    for product_name, qty in items:
        if product_name is None:
            continue
        if record_inventory_event(
            conn,
            product_name=product_name,
            delta=delta_sign * qty,
            event_type=event_type,
            order_number=order_number,
            event_date=paid_date,
        ):
            inserted += 1

    logger.info(
        "apply_order_to_inventory: order %s (%s) — %d ledger row(s) inserted",
        order_number, order_type, inserted,
    )
    return inserted


def apply_purchase_order_to_inventory(conn, po_number):
    """Record ``PO_RECEIVED`` InventoryLedger events for a wholesale purchase order.

    Uses ``PurchaseOrderItems.Quantity`` for the delta (each PO line can be
    multiple units, unlike retail ``OrderItems`` where each row = 1 unit).
    Delta is always positive — wholesale stock arrives into inventory.

    One ledger row per ``(OrderNumber, ProductName)`` group, idempotent via
    ``INSERT OR IGNORE``.

    Args:
        conn: open sqlite3 connection to bless.db
        po_number (str): ``PurchaseOrders.OrderNumber`` to process

    Returns:
        int: number of new ledger rows inserted.
    """
    cursor = conn.cursor()

    po_row = cursor.execute(
        "SELECT OrderDate FROM PurchaseOrders WHERE OrderNumber = ?",
        (po_number,)
    ).fetchone()

    if po_row is None:
        logger.warning(
            "apply_purchase_order_to_inventory: PO %s not found", po_number
        )
        return 0

    event_date = po_row[0]

    items = cursor.execute(
        "SELECT ProductName, SUM(Quantity) AS total_qty "
        "FROM PurchaseOrderItems "
        "WHERE OrderNumber = ? AND ProductName IS NOT NULL "
        "GROUP BY ProductName",
        (po_number,)
    ).fetchall()

    if not items:
        logger.warning(
            "apply_purchase_order_to_inventory: no items for PO %s — skipping",
            po_number,
        )
        return 0

    inserted = 0
    for product_name, total_qty in items:
        if product_name is None or total_qty is None:
            continue
        if record_inventory_event(
            conn,
            product_name=product_name,
            delta=int(total_qty),
            event_type="PO_RECEIVED",
            order_number=po_number,
            event_date=event_date,
        ):
            inserted += 1

    logger.info(
        "apply_purchase_order_to_inventory: PO %s — %d ledger row(s) inserted",
        po_number, inserted,
    )
    return inserted


def get_product_quantity(conn, product_name):
    """Return current on-hand stock count for a single product.

    Computed as ``SUM(Delta)`` over all InventoryLedger rows for the product.

    Args:
        conn: open sqlite3 connection to bless.db
        product_name (str): ``Products.ProductName``

    Returns:
        int: current quantity (may be 0 or negative if data is incomplete).
    """
    row = conn.execute(
        "SELECT COALESCE(SUM(Delta), 0) FROM InventoryLedger WHERE ProductName = ?",
        (product_name,)
    ).fetchone()
    return int(row[0])


def get_all_inventory_quantities(conn):
    """Return current on-hand quantities for all products that have ledger activity.

    Products with no ledger rows are not included (they implicitly have 0 stock).

    Args:
        conn: open sqlite3 connection to bless.db

    Returns:
        dict: ``{product_name: quantity}`` for every ProductName in InventoryLedger.
    """
    rows = conn.execute(
        "SELECT ProductName, COALESCE(SUM(Delta), 0) AS qty "
        "FROM InventoryLedger GROUP BY ProductName"
    ).fetchall()
    return {row[0]: int(row[1]) for row in rows}


def apply_all_paid_orders_to_inventory(conn):
    """Apply inventory events for all paid orders not yet recorded in InventoryLedger.

    Finds paid orders whose ``OrderNumber`` does not appear in
    ``InventoryLedger``, then calls :func:`apply_order_to_inventory` for each.
    Safe to re-run — already-processed orders produce no new rows via
    ``INSERT OR IGNORE``.

    Args:
        conn: open sqlite3 connection to bless.db

    Returns:
        int: total ledger rows inserted across all processed orders.
    """
    rows = conn.execute(
        "SELECT OrderNumber FROM Orders "
        "WHERE PaidDate IS NOT NULL "
        "  AND OrderType IN ('RETAIL', 'TRANSFER_IN', 'TRANSFER_OUT') "
        "  AND OrderNumber NOT IN ("
        "      SELECT DISTINCT OrderNumber FROM InventoryLedger"
        "      WHERE OrderNumber IS NOT NULL)"
    ).fetchall()

    total = 0
    for (order_number,) in rows:
        total += apply_order_to_inventory(conn, order_number)

    logger.info(
        "apply_all_paid_orders_to_inventory: %d order(s) processed, "
        "%d ledger row(s) inserted",
        len(rows), total,
    )
    return total


def apply_all_purchase_orders_to_inventory(conn):
    """Apply ``PO_RECEIVED`` events for all purchase orders not yet in InventoryLedger.

    Finds POs whose ``OrderNumber`` does not appear in ``InventoryLedger``,
    then calls :func:`apply_purchase_order_to_inventory` for each.
    Safe to re-run.

    Args:
        conn: open sqlite3 connection to bless.db

    Returns:
        int: total ledger rows inserted.
    """
    rows = conn.execute(
        "SELECT OrderNumber FROM PurchaseOrders "
        "WHERE OrderNumber NOT IN ("
        "    SELECT DISTINCT OrderNumber FROM InventoryLedger"
        "    WHERE OrderNumber IS NOT NULL)"
    ).fetchall()

    total = 0
    for (order_number,) in rows:
        total += apply_purchase_order_to_inventory(conn, order_number)

    logger.info(
        "apply_all_purchase_orders_to_inventory: %d PO(s) processed, "
        "%d ledger row(s) inserted",
        len(rows), total,
    )
    return total


# ---------------------------------------------------------------------------
# TRANSFER_IN product catalog upsert
# ---------------------------------------------------------------------------

_KNOWN_SIZES = {
    '2XS', 'XS', 'S', 'M', 'L', 'XL', '2XL', '3XL',
    'OS', 'O/S', 'TC', 'TC2', 'T/C', 'T/C2',
    '1X', '2X', '3X',
    'K2', 'K4', 'K6', 'K8', 'K10', 'K12',
    'S/M',
}


def upsert_transfer_in_product(conn, product_name, unit_price=None):
    """Find or create a Product entry for an item from a TRANSFER_IN order.

    Match priority:
    1. Exact ``Products.InvProductName`` match  → return existing SKU
    2. Exact ``Products.ProductName`` match      → return existing SKU
    3. No match → create a stub Product with a generated placeholder SKU

    The stub uses ``TIN-<hex>`` as the ProductSKU to satisfy the ``UNIQUE NOT NULL``
    constraint. ``ProductStyle`` and ``ProductSize`` are parsed from the last
    space-separated token when it looks like a size code; otherwise the full
    name is used as the style and ``OS`` as the size.

    Args:
        conn: open sqlite3 connection to bless.db
        product_name (str): ``OrderItems.ProductName`` from the transfer order
        unit_price (float | None): price from the order item, used for ``UnitPrice``
            on new stub rows (defaults to 0.0 if not provided)

    Returns:
        str | None: ``ProductSKU`` of the matched or newly created Product,
            or ``None`` if *product_name* is falsy or a DB error occurred.
    """
    if not product_name:
        return None

    cursor = conn.cursor()

    # 1. Exact InvProductName match
    row = cursor.execute(
        "SELECT ProductSKU FROM Products WHERE InvProductName = ? LIMIT 1",
        (product_name,),
    ).fetchone()
    if row:
        return row[0]

    # 2. Exact ProductName match
    row = cursor.execute(
        "SELECT ProductSKU FROM Products WHERE ProductName = ? LIMIT 1",
        (product_name,),
    ).fetchone()
    if row:
        return row[0]

    # 3. No match — create stub
    parts = product_name.rsplit(' ', 1)
    if len(parts) == 2 and parts[1].upper() in {s.upper() for s in _KNOWN_SIZES}:
        style, size = parts[0], parts[1]
    else:
        style, size = product_name, 'OS'

    prod_id = binascii.b2a_hex(os.urandom(12)).decode()
    sku_placeholder = 'TIN-' + binascii.b2a_hex(os.urandom(6)).decode()
    price = float(unit_price) if unit_price is not None else 0.0

    try:
        cursor.execute(
            "INSERT INTO Products "
            "(ProductID, ProductSKU, ProductName, ProductSize, ProductStyle, "
            "UnitPrice, InvProductName) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (prod_id, sku_placeholder, product_name, size, style, price, product_name),
        )
        conn.commit()
        logger.info(
            "upsert_transfer_in_product: created stub '%s' (SKU=%s, style='%s', size='%s')",
            product_name, sku_placeholder, style, size,
        )
        return sku_placeholder
    except sqlite3.IntegrityError:
        logger.warning(
            "upsert_transfer_in_product: IntegrityError creating stub for '%s'",
            product_name,
        )
        return None


def upsert_products_from_transfer_in(conn, order_number):
    """Ensure all items from a TRANSFER_IN paid order exist in the Products catalog.

    Iterates over distinct ``OrderItems.ProductName`` values for the order and
    calls :func:`upsert_transfer_in_product` for each.  Only operates on
    ``TRANSFER_IN`` orders; returns 0 immediately for any other type.

    Args:
        conn: open sqlite3 connection to bless.db
        order_number (str): ``Orders.OrderNumber`` to process

    Returns:
        int: number of new Product stub rows created.
    """
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT OrderType FROM Orders WHERE OrderNumber = ?",
        (order_number,),
    ).fetchone()
    if not row or row[0] != 'TRANSFER_IN':
        return 0

    items = cursor.execute(
        "SELECT DISTINCT ProductName, UnitPrice FROM OrderItems WHERE OrderNumber = ?",
        (order_number,),
    ).fetchall()

    before = conn.execute("SELECT COUNT(*) FROM Products").fetchone()[0]
    for product_name, unit_price in items:
        if product_name:
            upsert_transfer_in_product(conn, product_name, unit_price)
    after = conn.execute("SELECT COUNT(*) FROM Products").fetchone()[0]

    created = after - before
    logger.info(
        "upsert_products_from_transfer_in: order %s — %d new product stub(s) created",
        order_number, created,
    )
    return created


def backfill_products_from_all_transfer_ins(conn):
    """Create stub Products for all TRANSFER_IN items not already in the catalog.

    Iterates over all paid ``TRANSFER_IN`` orders and calls
    :func:`upsert_transfer_in_product` for each distinct item.  Safe to
    re-run — existing products are found by name and skipped.

    Args:
        conn: open sqlite3 connection to bless.db

    Returns:
        int: total new Product stub rows created.
    """
    rows = conn.execute(
        "SELECT OrderNumber FROM Orders "
        "WHERE OrderType = 'TRANSFER_IN' AND PaidDate IS NOT NULL"
    ).fetchall()

    before = conn.execute("SELECT COUNT(*) FROM Products").fetchone()[0]

    for (order_number,) in rows:
        items = conn.execute(
            "SELECT DISTINCT ProductName, UnitPrice FROM OrderItems WHERE OrderNumber = ?",
            (order_number,),
        ).fetchall()
        for product_name, unit_price in items:
            if product_name:
                upsert_transfer_in_product(conn, product_name, unit_price)

    after = conn.execute("SELECT COUNT(*) FROM Products").fetchone()[0]
    total_created = after - before

    logger.info(
        "backfill_products_from_all_transfer_ins: %d order(s) processed, "
        "%d new product stub(s) created",
        len(rows), total_created,
    )
    return total_created
