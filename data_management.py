import psycopg2
import os
import binascii
import re
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _parse_money(value):
    return value.lstrip("$").replace(',', '')


def _parse_datetime(value, formats):
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"time data {value!r} does not match any known format")


def _ensure_column(cursor, table, column, col_type):
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}")


def init_db(database_url=None):
    conn = psycopg2.connect(database_url or os.environ['DATABASE_URL'])
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        UserID TEXT PRIMARY KEY,
        UserEmail TEXT UNIQUE NOT NULL,
        UserName TEXT,
        GoogleRefreshToken TEXT,
        CreatedAt TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CUSTOMERS (
        CustomerID TEXT PRIMARY KEY NOT NULL,
        UserID TEXT NOT NULL REFERENCES Users(UserID),
        CustomerEmail TEXT NOT NULL,
        CustomerName TEXT NOT NULL,
        CustomerType TEXT NOT NULL,
        CustomerPhone TEXT NULL,
        UNIQUE (UserID, CustomerEmail)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Products (
        ProductID TEXT PRIMARY KEY NOT NULL,
        UserID TEXT NOT NULL REFERENCES Users(UserID),
        ProductSKU TEXT NOT NULL,
        ProductName TEXT NOT NULL,
        ProductSize TEXT NOT NULL,
        ProductStyle TEXT NOT NULL,
        UnitPrice REAL NOT NULL,
        InvProductName TEXT NOT NULL,
        ProductCategory TEXT NULL,
        ProductFamily TEXT NULL,
        SizeNormalized TEXT,
        SizingFamily TEXT,
        UNIQUE (UserID, ProductSKU)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS PurchaseOrders (
        OrderID TEXT PRIMARY KEY,
        UserID TEXT NOT NULL REFERENCES Users(UserID),
        OrderNumber TEXT NOT NULL,
        OrderEmail TEXT NOT NULL,
        OrderDate TIMESTAMP NOT NULL,
        Subtotal REAL NOT NULL,
        Shipping REAL NOT NULL,
        Taxes REAL NOT NULL,
        Total REAL NOT NULL,
        Pieces REAL NOT NULL,
        UNIQUE (UserID, OrderNumber)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS PurchaseOrderItems (
        PurchaseItemID TEXT UNIQUE NOT NULL PRIMARY KEY,
        UserID TEXT NOT NULL,
        OrderNumber TEXT NOT NULL,
        ProductSKU TEXT,
        ProductName TEXT,
        Quantity INTEGER,
        CostPerUnit REAL,
        TotalCost REAL,
        LlrPieces REAL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Orders (
        OrderID TEXT PRIMARY KEY,
        UserID TEXT NOT NULL REFERENCES Users(UserID),
        OrderNumber TEXT NOT NULL,
        OrderPopUp TEXT NOT NULL,
        OrderEmail TEXT NOT NULL,
        InvoiceDate TIMESTAMP NOT NULL,
        InvSubtotal REAL NOT NULL,
        InvTaxes REAL NOT NULL,
        InvShipping REAL NOT NULL,
        InvShippingTaxes REAL NOT NULL,
        InvDiscount REAL NOT NULL,
        InvTotal REAL NOT NULL,
        InvPieces REAL NOT NULL,
        PaidDate TIMESTAMP NULL,
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
        UNIQUE (UserID, OrderNumber)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS OrderItems (
        OrderItemID TEXT UNIQUE NOT NULL PRIMARY KEY,
        UserID TEXT NOT NULL,
        OrderNumber TEXT NOT NULL,
        OrderLineItem TEXT NOT NULL,
        ProductName TEXT,
        UnitPrice REAL,
        DiscountPrice REAL,
        TotalPrice REAL,
        UNIQUE (UserID, OrderNumber, OrderLineItem)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS InventoryLedger (
        LedgerID    TEXT PRIMARY KEY,
        UserID      TEXT NOT NULL REFERENCES Users(UserID),
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
        EventDate   TIMESTAMP NOT NULL,
        UNIQUE (UserID, OrderNumber, ProductName)
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

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS FitFeedback (
        FeedbackID TEXT PRIMARY KEY,
        UserID TEXT NOT NULL,
        CustomerID TEXT NOT NULL,
        ProductSKU TEXT NOT NULL,
        OrderNumber TEXT,
        SizePurchased TEXT NOT NULL,
        FitOutcome TEXT NOT NULL CHECK (FitOutcome IN ('too_small','true_to_size','too_large')),
        Source TEXT NOT NULL CHECK (Source IN ('explicit','implicit_repeat')),
        CreatedAt TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Subscriptions (
        ID TEXT PRIMARY KEY,
        StripeSubscriptionID TEXT UNIQUE NOT NULL,
        StripeCustomerID TEXT,
        CustomerEmail TEXT,
        Status TEXT NOT NULL DEFAULT 'active',
        CreatedAt TEXT NOT NULL,
        UserID TEXT REFERENCES Users(UserID)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Credentials (
        CredentialID TEXT PRIMARY KEY,
        UserID TEXT NOT NULL REFERENCES Users(UserID),
        platform TEXT NOT NULL,
        username TEXT NOT NULL,
        encrypted_password BYTEA NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (UserID, platform)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SyncLog (
        SyncLogID TEXT PRIMARY KEY,
        UserID TEXT NOT NULL REFERENCES Users(UserID),
        TableName TEXT NOT NULL,
        LastSyncedAt TEXT NOT NULL,
        RowsSynced INTEGER NOT NULL DEFAULT 0,
        UNIQUE (UserID, TableName)
    )
    ''')

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_product ON InventoryLedger(ProductName)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_invname ON Products(InvProductName)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fitfb_customer ON FitFeedback(CustomerID)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fitfb_sku ON FitFeedback(ProductSKU)")

    cursor.execute("""
        DELETE FROM PurchaseOrderItems
        WHERE PurchaseItemID NOT IN (
            SELECT MIN(PurchaseItemID)
            FROM PurchaseOrderItems
            GROUP BY UserID, OrderNumber, ProductSKU
        )
    """)

    cursor.execute("""
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'purchaseorderitems'::regclass
          AND conname = 'uq_purchaseorderitems_user_order_sku'
    """)
    if cursor.fetchone() is None:
        cursor.execute("""
            ALTER TABLE PurchaseOrderItems
            ADD CONSTRAINT uq_purchaseorderitems_user_order_sku
            UNIQUE (UserID, OrderNumber, ProductSKU)
        """)

    conn.commit()

    from app.sizing import classify_family, normalize_size as _normalize_size, classify_product_family

    cursor.execute("SELECT COUNT(*) FROM Products WHERE SizingFamily IS NULL")
    needs_backfill = cursor.fetchone()[0]
    if needs_backfill > 0:
        cursor.execute(
            "SELECT ProductID, ProductStyle, ProductSize FROM Products WHERE SizingFamily IS NULL"
        )
        rows = cursor.fetchall()
        for row in rows:
            pid, style, size = row[0], row[1], row[2]
            family = classify_family(style, size)
            norm = _normalize_size(size)
            cursor.execute(
                "UPDATE Products SET SizingFamily=%s, SizeNormalized=%s WHERE ProductID=%s",
                (family, norm, pid)
            )
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM Products WHERE ProductFamily IS NULL")
    needs_family_backfill = cursor.fetchone()[0]
    if needs_family_backfill > 0:
        cursor.execute(
            "SELECT ProductID, ProductName, ProductStyle, SizingFamily FROM Products WHERE ProductFamily IS NULL"
        )
        rows = cursor.fetchall()
        for row in rows:
            pid, name, style, sizing_fam = row[0], row[1], row[2], row[3]
            product_family = classify_product_family(name, style, sizing_fam)
            cursor.execute(
                "UPDATE Products SET ProductFamily=%s WHERE ProductID=%s",
                (product_family, pid)
            )
        conn.commit()

    conn.close()


def upsert_user(conn, user_id, email, name, refresh_token):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Users (UserID, UserEmail, UserName, GoogleRefreshToken, CreatedAt) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (UserEmail) DO UPDATE SET "
        "UserName = EXCLUDED.UserName, "
        "GoogleRefreshToken = COALESCE(EXCLUDED.GoogleRefreshToken, Users.GoogleRefreshToken)",
        (user_id, email, name, refresh_token, datetime.utcnow().isoformat())
    )
    conn.commit()
    cursor.execute("SELECT UserID FROM Users WHERE UserEmail = %s", (email,))
    row = cursor.fetchone()
    return row[0]


def insert_customer(dbconn, user_id, customerrec):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = dbconn.cursor()
    try:
        cursor.execute(
            "SELECT CustomerID FROM Customers WHERE CustomerEmail = %s AND UserID = %s",
            (customerrec[1], user_id)
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO Customers (CustomerID, UserID, CustomerEmail, CustomerName, CustomerType, CustomerPhone) "
                "VALUES (%s, %s, %s, %s, %s, null) ON CONFLICT DO NOTHING",
                (UUID, user_id, customerrec[1], customerrec[0], customerrec[2])
            )
            dbconn.commit()
            logger.warning("adding customer ...")
        logger.debug("customer saved")
    except Exception as e:
        logger.error("Customer failed to save: %s", e)
        dbconn.rollback()


def insert_product(dbconn, user_id, productrec):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = dbconn.cursor()
    cost = float(productrec[2].replace('$', ''))
    try:
        cursor.execute(
            "SELECT ProductID FROM Products WHERE ProductSKU = %s AND UserID = %s",
            (productrec[0], user_id)
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO Products (ProductID, UserID, ProductSKU, ProductName, ProductSize, ProductStyle, UnitPrice, InvProductName) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (UUID, user_id, productrec[0], productrec[1], productrec[4], productrec[3], cost, productrec[5])
            )
            dbconn.commit()
        logger.debug("product saved")
    except Exception as e:
        logger.error("Product failed to save: %s", e)
        dbconn.rollback()


def update_product(dbconn, user_id, translations_path=None):
    import pandas as pd
    cursor = dbconn.cursor()
    if translations_path is None:
        translations_path = os.path.join(os.path.dirname(__file__), "product_name_translations.json")
    with open(translations_path, "r") as f:
        translations = json.load(f)
    df_prod = pd.read_sql_query(
        "SELECT ProductID, ProductName FROM Products WHERE UserID = %s",
        dbconn._conn, params=(user_id,)
    )
    for index, row in df_prod.iterrows():
        ProductID = row['ProductID']
        ProductName = row['ProductName']
        InvProductName = re.sub(r'(?<=)(\w+)(?=)', lambda m: translations.get(m.group(), m.group()), row['ProductName'])
        try:
            cursor.execute("UPDATE Products SET InvProductName=%s WHERE ProductID=%s AND UserID=%s", (InvProductName, ProductID, user_id))
            dbconn.commit()
            logger.debug("product saved")
        except Exception as e:
            logger.error("Product failed to save: %s", e)
            dbconn.rollback()


def insert_purchase_order(dbconn, user_id, purchase_order_rec):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = dbconn.cursor()
    OrderNumber = purchase_order_rec[0]
    OrderEmail = purchase_order_rec[1]
    OrderDate = _parse_datetime(purchase_order_rec[2], ["%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M:%S", "%m/%d/%Y %H:%M:%S"])
    Subtotal = _parse_money(purchase_order_rec[3])
    Shipping = _parse_money(purchase_order_rec[4])
    Taxes = _parse_money(purchase_order_rec[5])
    Total = _parse_money(purchase_order_rec[6])
    Pieces = purchase_order_rec[7]

    try:
        cursor.execute(
            "SELECT OrderID FROM PurchaseOrders WHERE OrderNumber = %s AND UserID = %s",
            (OrderNumber, user_id)
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO PurchaseOrders (OrderID, UserID, OrderNumber, OrderEmail, OrderDate, Subtotal, Shipping, Taxes, Total, Pieces) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (UUID, user_id, OrderNumber, OrderEmail, OrderDate,
                 float(Subtotal), float(Shipping), float(Taxes),
                 float(Total), float(Pieces))
            )
            dbconn.commit()
        logger.debug("purchase order saved")
    except Exception as e:
        logger.error("purchase order failed to save: %s", e)
        dbconn.rollback()


def insert_purchase_order_item(dbconn, user_id, purchasedItemsRec, purchaseOrderNumber):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = dbconn.cursor()
    OrderNumber = purchaseOrderNumber
    ProductSKU = purchasedItemsRec[2]
    ProductName = purchasedItemsRec[3]
    Quantity = purchasedItemsRec[1]
    CostPerUnit = _parse_money(purchasedItemsRec[5])
    TotalCost = _parse_money(purchasedItemsRec[6])
    LlrPieces = purchasedItemsRec[4]
    try:
        cursor.execute(
            "SELECT PurchaseItemID FROM PurchaseOrderItems "
            "WHERE UserID = %s AND OrderNumber = %s AND ProductSKU = %s",
            (user_id, OrderNumber, ProductSKU)
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO PurchaseOrderItems "
                "(PurchaseItemID, UserID, OrderNumber, ProductSKU, ProductName, Quantity, CostPerUnit, TotalCost, LlrPieces) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (UUID, user_id, OrderNumber, ProductSKU, ProductName, Quantity, CostPerUnit, TotalCost, LlrPieces)
            )
            dbconn.commit()
        logger.debug("PO item saved")
    except Exception as e:
        logger.error("PO item failed to save: %s", e)
        dbconn.rollback()


def insert_order(dbconn, user_id, retail_inv_rec, count_items):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = dbconn.cursor()
    OrderNumber = retail_inv_rec[3]
    OrderPopup = retail_inv_rec[4]
    OrderEmail = retail_inv_rec[1]
    d_date = retail_inv_rec[2].replace(' PST', '')
    InvDate = _parse_datetime(d_date, ["%b %d %Y %I:%M %p", "%b %d %Y %I:%M", "%m/%d/%Y %H:%M:%S"])
    InvSubtotal = _parse_money(retail_inv_rec[5])
    InvShipping = _parse_money(retail_inv_rec[7])
    InvTaxes = _parse_money(retail_inv_rec[6])
    InvShippingTaxes = _parse_money(retail_inv_rec[8])
    InvDisc = 0
    InvTotal = _parse_money(retail_inv_rec[9])
    InvPieces = count_items

    try:
        cursor.execute(
            "SELECT OrderID FROM Orders WHERE OrderNumber = %s AND UserID = %s",
            (OrderNumber, user_id)
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO Orders (OrderID, UserID, OrderNumber, OrderPopUp, OrderEmail, InvoiceDate, "
                "InvSubtotal, InvTaxes, InvShipping, InvShippingTaxes, InvDiscount, InvTotal, InvPieces) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (UUID, user_id, OrderNumber, OrderPopup, OrderEmail, InvDate,
                 float(InvSubtotal), float(InvTaxes), float(InvShipping), float(InvShippingTaxes),
                 float(InvDisc), float(InvTotal), float(InvPieces))
            )
            dbconn.commit()
            logger.debug("order saved")
    except Exception as e:
        logger.error("order failed to save: %s", e)
        dbconn.rollback()


def update_paid_order(conn, user_id, summary, numberOfItems, emailTime):
    cursor = conn.cursor()
    d_date = summary[2].replace(' PST', '')
    PaidDate = _parse_datetime(d_date, ["%b %d %Y %I:%M %p", "%b %d %Y %I:%M", "%m/%d/%Y %H:%M:%S"])
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
            """UPDATE Orders SET PaidDate=%s, PaidSubtotal=%s, PaidShipping=%s,
               PaidTaxes=%s, PaidShippingTaxes=%s, PaidDiscount=%s, PaidTotal=%s,
               PaidPieces=%s, ShipAddr1=%s, ShipAddr2=%s, City=%s, State=%s, Zip=%s
               WHERE OrderNumber=%s AND UserID=%s""",
            (PaidDate, float(PaidSubtotal), float(PaidShipping),
             float(PaidTaxes), float(PaidShipTaxes), float(PaidDisc),
             float(PaidTotal), float(PaidPieces), addr1, addr2,
             city, state, zip, summary[3], user_id)
        )
        conn.commit()
        logger.debug("order saved")
    except Exception as e:
        logger.error("order failed to save: %s", e)
        conn.rollback()


def update_transfer_type(conn, user_id, summary, my_email):
    cursor = conn.cursor()
    if summary[1] == my_email:
        cursor.execute("UPDATE TransferOrders SET TransferInOut=%s WHERE OrderNumber=%s AND UserID=%s", ("IN", summary[3], user_id))
        conn.commit()
    else:
        cursor.execute("UPDATE TransferOrders SET TransferInOut=%s WHERE OrderNumber=%s AND UserID=%s", ("OUT", summary[3], user_id))
        conn.commit()
    return


def update_order_type(conn, user_id, orderNumber, type):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Orders SET OrderType=%s WHERE OrderNumber=%s AND UserID=%s", (type, orderNumber, user_id))
        conn.commit()
    except Exception:
        logger.error("order type failed to save")


def insert_order_item(conn, user_id, items, orderNumber):
    cursor = conn.cursor()
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
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
        cursor.execute(
            "INSERT INTO OrderItems (OrderItemID, UserID, OrderNumber, OrderLineItem, ProductName, UnitPrice, DiscountPrice, TotalPrice) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (UUID, user_id, orderNumber, itemLine, itemName, float(itemPrice), float(itemDisc), float(itemTotal))
        )
        conn.commit()
        logger.debug("order item saved")
    except Exception as e:
        logger.error("order item failed to save: %s", e)
        conn.rollback()


def update_task_start_time(conn, task, time):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Tasks SET lastStartTime=%s WHERE taskName=%s", (time, task))
        conn.commit()
        return
    except Exception as e:
        logger.error("task failed to save: %s", e)
        conn.rollback()


def update_task_end_time(conn, task, time):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Tasks SET lastEndTime=%s WHERE taskName=%s", (time, task))
        conn.commit()
        return
    except Exception as e:
        logger.error("task failed to save: %s", e)
        conn.rollback()


def init_task(conn, task):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Tasks (taskID, taskName, lastStartTime, lastEndTime) VALUES (%s, %s, null, null) ON CONFLICT DO NOTHING",
            (UUID, task)
        )
        conn.commit()
        return
    except Exception as e:
        logger.error("task failed to save: %s", e)
        conn.rollback()


def record_inventory_event(conn, user_id, product_name, delta, event_type, order_number, event_date):
    UUID = binascii.b2a_hex(os.urandom(12)).decode()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO InventoryLedger "
            "(LedgerID, UserID, ProductName, Delta, EventType, OrderNumber, EventDate) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (UserID, OrderNumber, ProductName) DO NOTHING",
            (UUID, user_id, product_name, delta, event_type, order_number, event_date),
        )
        conn.commit()
    except Exception as e:
        logger.error("inventory event failed to save: %s", e)
        conn.rollback()
    inserted = cursor.rowcount > 0
    if inserted:
        logger.info(
            "record_inventory_event: %+d '%s' [%s] order=%s",
            delta, product_name, event_type, order_number,
        )
    return inserted


def apply_order_to_inventory(conn, user_id, order_number):
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT OrderType, PaidDate FROM Orders WHERE OrderNumber = %s AND UserID = %s",
            (order_number, user_id)
        )
        row = cursor.fetchone()
    except Exception as e:
        logger.error("inventory failed to save: %s", e)
        conn.rollback()
        return 0

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

    cursor.execute(
        "SELECT ProductName, COUNT(*) AS qty "
        "FROM OrderItems WHERE OrderNumber = %s AND UserID = %s GROUP BY ProductName",
        (order_number, user_id)
    )
    items = cursor.fetchall()

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
            user_id=user_id,
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


def apply_purchase_order_to_inventory(conn, user_id, po_number):
    cursor = conn.cursor()

    cursor.execute(
        "SELECT OrderDate FROM PurchaseOrders WHERE OrderNumber = %s AND UserID = %s",
        (po_number, user_id)
    )
    po_row = cursor.fetchone()

    if po_row is None:
        logger.warning(
            "apply_purchase_order_to_inventory: PO %s not found", po_number
        )
        return 0

    event_date = po_row[0]

    cursor.execute(
        "SELECT ProductName, SUM(Quantity) AS total_qty "
        "FROM PurchaseOrderItems "
        "WHERE OrderNumber = %s AND UserID = %s AND ProductName IS NOT NULL "
        "GROUP BY ProductName",
        (po_number, user_id)
    )
    items = cursor.fetchall()

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
            user_id=user_id,
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


def get_product_quantity(conn, user_id, product_name):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(Delta), 0) FROM InventoryLedger WHERE ProductName = %s AND UserID = %s",
        (product_name, user_id)
    )
    row = cursor.fetchone()
    return int(row[0])


def get_all_inventory_quantities(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ProductName, COALESCE(SUM(Delta), 0) AS qty "
        "FROM InventoryLedger WHERE UserID = %s GROUP BY ProductName",
        (user_id,)
    )
    rows = cursor.fetchall()
    return {row[0]: int(row[1]) for row in rows}


def apply_all_paid_orders_to_inventory(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT OrderNumber FROM Orders "
        "WHERE UserID = %s AND PaidDate IS NOT NULL "
        "  AND OrderType IN ('RETAIL', 'TRANSFER_IN', 'TRANSFER_OUT') "
        "  AND OrderNumber NOT IN ("
        "      SELECT DISTINCT OrderNumber FROM InventoryLedger"
        "      WHERE OrderNumber IS NOT NULL AND UserID = %s)",
        (user_id, user_id)
    )
    rows = cursor.fetchall()

    total = 0
    for (order_number,) in rows:
        total += apply_order_to_inventory(conn, user_id, order_number)

    logger.info(
        "apply_all_paid_orders_to_inventory: %d order(s) processed, "
        "%d ledger row(s) inserted",
        len(rows), total,
    )
    return total


def apply_all_purchase_orders_to_inventory(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT OrderNumber FROM PurchaseOrders "
        "WHERE UserID = %s AND OrderNumber NOT IN ("
        "    SELECT DISTINCT OrderNumber FROM InventoryLedger"
        "    WHERE OrderNumber IS NOT NULL AND UserID = %s)",
        (user_id, user_id)
    )
    rows = cursor.fetchall()

    total = 0
    for (order_number,) in rows:
        total += apply_purchase_order_to_inventory(conn, user_id, order_number)

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


def upsert_transfer_in_product(conn, user_id, product_name, unit_price=None):
    if not product_name:
        return None

    cursor = conn.cursor()

    # 1. Exact InvProductName match
    cursor.execute(
        "SELECT ProductSKU FROM Products WHERE InvProductName = %s AND UserID = %s LIMIT 1",
        (product_name, user_id),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # 2. Exact ProductName match
    cursor.execute(
        "SELECT ProductSKU FROM Products WHERE ProductName = %s AND UserID = %s LIMIT 1",
        (product_name, user_id),
    )
    row = cursor.fetchone()
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
            "(ProductID, UserID, ProductSKU, ProductName, ProductSize, ProductStyle, "
            "UnitPrice, InvProductName) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (prod_id, user_id, sku_placeholder, product_name, size, style, price, product_name),
        )
        conn.commit()
        logger.info(
            "upsert_transfer_in_product: created stub '%s' (SKU=%s, style='%s', size='%s')",
            product_name, sku_placeholder, style, size,
        )
        return sku_placeholder
    except Exception:
        logger.warning(
            "upsert_transfer_in_product: error creating stub for '%s'",
            product_name,
        )
        return None


def upsert_products_from_transfer_in(conn, user_id, order_number):
    cursor = conn.cursor()

    cursor.execute(
        "SELECT OrderType FROM Orders WHERE OrderNumber = %s AND UserID = %s",
        (order_number, user_id),
    )
    row = cursor.fetchone()
    if not row or row[0] != 'TRANSFER_IN':
        return 0

    cursor.execute(
        "SELECT DISTINCT ProductName, UnitPrice FROM OrderItems WHERE OrderNumber = %s AND UserID = %s",
        (order_number, user_id),
    )
    items = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM Products WHERE UserID = %s", (user_id,))
    before = cursor.fetchone()[0]
    for product_name, unit_price in items:
        if product_name:
            upsert_transfer_in_product(conn, user_id, product_name, unit_price)
    cursor.execute("SELECT COUNT(*) FROM Products WHERE UserID = %s", (user_id,))
    after = cursor.fetchone()[0]

    created = after - before
    logger.info(
        "upsert_products_from_transfer_in: order %s — %d new product stub(s) created",
        order_number, created,
    )
    return created


def backfill_products_from_all_transfer_ins(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT OrderNumber FROM Orders "
        "WHERE UserID = %s AND OrderType = 'TRANSFER_IN' AND PaidDate IS NOT NULL",
        (user_id,)
    )
    rows = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM Products WHERE UserID = %s", (user_id,))
    before = cursor.fetchone()[0]

    for (order_number,) in rows:
        cursor.execute(
            "SELECT DISTINCT ProductName, UnitPrice FROM OrderItems WHERE OrderNumber = %s AND UserID = %s",
            (order_number, user_id),
        )
        items = cursor.fetchall()
        for product_name, unit_price in items:
            if product_name:
                upsert_transfer_in_product(conn, user_id, product_name, unit_price)

    cursor.execute("SELECT COUNT(*) FROM Products WHERE UserID = %s", (user_id,))
    after = cursor.fetchone()[0]
    total_created = after - before

    logger.info(
        "backfill_products_from_all_transfer_ins: %d order(s) processed, "
        "%d new product stub(s) created",
        len(rows), total_created,
    )
    return total_created
