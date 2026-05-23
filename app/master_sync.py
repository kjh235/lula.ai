import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_TABLES = [
    (
        "CUSTOMERS",
        "SELECT CustomerID, CustomerEmail, CustomerName, CustomerType, CustomerPhone FROM CUSTOMERS",
        "INSERT OR REPLACE INTO CUSTOMERS VALUES (?,?,?,?,?)",
    ),
    (
        "Orders",
        "SELECT OrderID, OrderNumber, OrderPopUp, OrderEmail, InvoiceDate, "
        "InvSubtotal, InvTaxes, InvShipping, InvShippingTaxes, InvDiscount, "
        "InvTotal, InvPieces, PaidDate, PaidSubtotal, PaidShipping, PaidTaxes, "
        "PaidShippingTaxes, PaidDiscount, PaidTotal, PaidPieces, "
        "ShipAddr1, ShipAddr2, City, State, Zip, OrderType FROM Orders",
        "INSERT OR REPLACE INTO Orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    ),
    (
        "OrderItems",
        "SELECT OrderItemID, OrderNumber, OrderLineItem, ProductName, UnitPrice, DiscountPrice, TotalPrice FROM OrderItems",
        "INSERT OR REPLACE INTO OrderItems (OrderItemID, OrderNumber, OrderLineItem, ProductName, UnitPrice, DiscountPrice, TotalPrice) VALUES (?,?,?,?,?,?,?)",
    ),
    (
        "Subscriptions",
        "SELECT ID, StripeSubscriptionID, StripeCustomerID, CustomerEmail, Status, CreatedAt FROM Subscriptions",
        "INSERT OR REPLACE INTO Subscriptions VALUES (?,?,?,?,?,?)",
    ),
    (
        "FitFeedback",
        "SELECT FeedbackID, CustomerID, ProductSKU, OrderNumber, SizePurchased, FitOutcome, Source, CreatedAt FROM FitFeedback",
        "INSERT OR REPLACE INTO FitFeedback VALUES (?,?,?,?,?,?,?,?)",
    ),
]


def run_full_sync(source_path, master_path):
    synced_at = datetime.now(timezone.utc).isoformat()
    results = {}

    src = sqlite3.connect(source_path)
    dst = sqlite3.connect(master_path)

    try:
        for table_name, select_sql, insert_sql in _TABLES:
            try:
                rows = src.execute(select_sql).fetchall()
                dst.executemany(insert_sql, rows)
                dst.execute(
                    "INSERT OR REPLACE INTO SyncLog (TableName, LastSyncedAt, RowsSynced) VALUES (?,?,?)",
                    (table_name, synced_at, len(rows)),
                )
                dst.commit()
                results[table_name] = len(rows)
                logger.info("master_sync: %s — %d rows", table_name, len(rows))
            except Exception:
                logger.exception("master_sync: failed syncing %s", table_name)
                results[table_name] = -1
    finally:
        src.close()
        dst.close()

    return {"synced_at": synced_at, "tables": results}
