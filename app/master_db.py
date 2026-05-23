import sqlite3


def init_master_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS CUSTOMERS (
        CustomerID TEXT PRIMARY KEY NOT NULL,
        CustomerEmail TEXT UNIQUE NOT NULL,
        CustomerName TEXT NOT NULL,
        CustomerType TEXT NOT NULL,
        CustomerPhone TEXT NULL
    )
    ''')

    c.execute('''
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
        OrderType TEXT NULL
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS OrderItems (
        OrderItemID TEXT UNIQUE NOT NULL PRIMARY KEY,
        OrderNumber TEXT NOT NULL,
        OrderLineItem TEXT NOT NULL,
        ProductName TEXT,
        UnitPrice REAL,
        DiscountPrice REAL,
        TotalPrice REAL,
        UNIQUE (OrderNumber, OrderLineItem)
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS Subscriptions (
        ID TEXT PRIMARY KEY,
        StripeSubscriptionID TEXT UNIQUE NOT NULL,
        StripeCustomerID TEXT,
        CustomerEmail TEXT,
        Status TEXT NOT NULL DEFAULT 'active',
        CreatedAt TEXT NOT NULL
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS FitFeedback (
        FeedbackID TEXT PRIMARY KEY,
        CustomerID TEXT NOT NULL,
        ProductSKU TEXT NOT NULL,
        OrderNumber TEXT,
        SizePurchased TEXT NOT NULL,
        FitOutcome TEXT NOT NULL CHECK (FitOutcome IN ('too_small','true_to_size','too_large')),
        Source TEXT NOT NULL CHECK (Source IN ('explicit','implicit_repeat')),
        CreatedAt TEXT NOT NULL
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS SyncLog (
        TableName TEXT PRIMARY KEY,
        LastSyncedAt TEXT NOT NULL,
        RowsSynced INTEGER NOT NULL DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()
