from sqlalchemy import create_engine
# from sqlalchemy import URL
# import sqlalchemy as db
#
# url_object = URL.create(
#     "postgresql",
#     username="consultant",
#     password="lularoe",  # plain (unescaped) text
#     host="localhost",
#     database="bless",
# )
# engine = create_engine(url_object)
# connection = engine.connect()
# metadata = db.MetaData()
#
# customer = db.Table('Customer', metadata,
#             db.Column('Id', db.Integer()),
#             db.Column('CustomerName', db.String(255), nullable=False),
#             db.Column('CustomerEmail', db.String(255), nullable=False),
#             db.Column('CustomerType', db.String(255), nullable=False),
#             db.Column('CustomerPhoneNumber', db.String(255), nullable=True)
#             )
#
# metadata.create_all(engine) #Creates the table
#
# customerrec = ['Amanda Olanna', 'Mandaaa012@gmail.com', 'RETAIL']
# productrec = ['610-13', 'Peyton S', '$32.50', 'Peyton', 'S']
# purchase_order_rec = ['94390994', 'lularoekristenhickman@gmail.com', '9/22/2023 12:20:57 PM', '$1,418.35', '$0.00', '$0.00', '$1,418.35', 67.0]
# # query = db.insert(customer).values(Id=1, CustomerName=customerrec[0], CustomerEmail=customerrec[1], CustomerType=customerrec[2])
# # ResultProxy = connection.execute(query)
# ['0', '14', '143-39', 'Single Solid Black Leggings T/C 2', '7.00', '$12.00', '$168.00']

def insert_customer(dbconn, customerrec):
    # Inserting record one by one
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    try:
        cursor.execute("INSERT INTO Customers VALUES (?, ?, ?, ?, null)",
                       (UUID, customerrec[0], customerrec[1], customerrec[2])
                       )
        dbconn.commit()
        print("customer saved")
    except:
        print("customer failed to save")
        pass


def insert_product(dbconn,productrec):
    global cursor
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    try:
        cursor.execute("INSERT INTO Products VALUES (?, ?, ?, ?, ?, ?, ?, null)",
                   (UUID, productrec[0], productrec[1], productrec[4], productrec[3], productrec[2],  productrec[5])
                   )
        dbconn.commit()
        print("product saved")
    except:
        print("product failed to save")
        pass
def update_product(dbconn):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    translations = {
        "HW23": "Witchful Thinking Halloween",
        "CZY23": "Cozy Cozy",
        "CZY22": "Cozy",
        "CZY21": "Cozy",
        "CZY20": "Cozy",
        "Flare Jean": "Denim Flared",
        # "Single Solid" : "Solid",
        "OTD23": "Great Outdoors 2023",
        "Single Print Leggings": "Single Pack Leggings - Prints",
        "RSRT22": "Resort 2022",
        "RSRT23 ": "",
        "CRER23": "Career Career",
        "CRER22": "Career 2022",
        "4J23": "Americana 2023",
        "4J22": "Americana 2022",
        "DREAM22": "",
        "DREAM21": "",
        "High Rise Slim Straight": "",
        "SP22 ": "",
        "VL22 ": "",
        "HW22": "Halloween 2022",
        "HW21": "Halloween 2021",
        "BOHO22 ": "",
        "LUXE21 ": "",
        "DNM21 ": "",
        "DR21 ": "",
        "BCA21": "BCA 2021",
        "ATR23": "Animal"
    }
    df_prod = pd.read_sql_query("SELECT ProductID, ProductName from Products", dbconn)
    for index, row in df_prod.iterrows():
        ProductID = row['ProductID']
        ProductName = row['ProductName']
        InvProductName = re.sub(r'(?<=)(\w+)(?=)', lambda m: translations.get(m.group(), m.group()), row['ProductName'])
        try:
            cursor.execute("UPDATE Products SET InvProductName=? WHERE ProductID =?", (InvProductName, ProductID))
            dbconn.commit()
            print("product saved")
        except:
            print("product failed to save")
            pass
def insert_purchase_order(dbconn, purchase_order_rec):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = purchase_order_rec[0]
    OrderEmail = purchase_order_rec[1]
    OrderDate = datetime.strptime(purchase_order_rec[2], "%m/%d/%Y %I:%M:%S %p")
    Subtotal = purchase_order_rec[3].lstrip("$").replace(',','')
    Shipping = purchase_order_rec[4].lstrip("$").replace(',','')
    Taxes = purchase_order_rec[5].lstrip("$").replace(',','')
    Total = purchase_order_rec[6].lstrip("$").replace(',','')
    Pieces = purchase_order_rec[7]

    try:
        cursor.execute("INSERT INTO PurchaseOrders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (UUID, OrderNumber, OrderEmail, OrderDate,
                        Subtotal, Shipping, Taxes,
                        Total, Pieces)
                       )
        dbconn.commit()
        print("purchase order saved")
    except:
        print("purchase order failed to save")
        pass
def insert_purchase_order_item(dbconn,purchasedItemsRec, purchaseOrderNumber):
    global cursor
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = purchaseOrderNumber
    ProductSKU = purchasedItemsRec[2]
    ProductName = purchasedItemsRec[3]
    Quantity = purchasedItemsRec[1]
    CostPerUnit = purchasedItemsRec[5].lstrip("$").replace(',','')
    TotalCost = purchasedItemsRec[6].lstrip("$").replace(',','')
    LlrPieces = purchasedItemsRec[4]
    try:
        cursor.execute("INSERT INTO PurchaseOrderItems VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (UUID, OrderNumber, ProductSKU, ProductName, Quantity, CostPerUnit,
                    TotalCost, LlrPieces)
                   )
        dbconn.commit()
        print("PO item saved")
    except:
        print("PO item failed to save")
        pass
def insert_retail_order(dbconn, retail_inv_rec, count_items):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = retail_inv_rec[3]
    OrderPopup = retail_inv_rec[4]
    OrderEmail = retail_inv_rec[1]
    d_date = retail_inv_rec[2].replace(' PST','')
    InvDate = datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    InvSubtotal = retail_inv_rec[5].lstrip("$").replace(',','')
    InvShipping = retail_inv_rec[7].lstrip("$").replace(',','')
    InvTaxes = retail_inv_rec[6].lstrip("$").replace(',','')
    InvShippingTaxes = retail_inv_rec[8].lstrip("$").replace(',','')
    InvDisc = 0 #retail_inv_rec[1]
    InvTotal = retail_inv_rec[9].lstrip("$").replace(',','')
    InvPieces = count_items

    try:
        cursor.execute("INSERT INTO RetailOrders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, null,"
                       "null, null, null, null, null, null, null, null, null, null, null, null)",
                       (UUID, OrderNumber, OrderPopup, OrderEmail, InvDate,
                        InvSubtotal, InvTaxes, InvShipping, InvShippingTaxes,
                        InvDisc, InvTotal, InvPieces)
                       )
        dbconn.commit()
        print("order saved")
    except:
        print("order failed to save")
        pass

def insert_order(dbconn, retail_inv_rec, count_items):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = retail_inv_rec[3]
    OrderPopup = retail_inv_rec[4]
    OrderEmail = retail_inv_rec[1]
    d_date = retail_inv_rec[2].replace(' PST', '')
    InvDate = datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    InvSubtotal = retail_inv_rec[5].lstrip("$").replace(',', '')
    InvShipping = retail_inv_rec[7].lstrip("$").replace(',', '')
    InvTaxes = retail_inv_rec[6].lstrip("$").replace(',', '')
    InvShippingTaxes = retail_inv_rec[8].lstrip("$").replace(',', '')
    InvDisc = 0  # retail_inv_rec[1]
    InvTotal = retail_inv_rec[9].lstrip("$").replace(',', '')
    InvPieces = count_items

    try:
        cursor.execute("INSERT INTO Orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, null,"
                       "null, null, null, null, null, null, null, null, null, null, null, null, null)",
                       (UUID, OrderNumber, OrderPopup, OrderEmail, InvDate,
                        InvSubtotal, InvTaxes, InvShipping, InvShippingTaxes,
                        InvDisc, InvTotal, InvPieces)
                       )
        dbconn.commit()
        print("order saved")
    except:
        print("order failed to save")
        pass
def insert_paid_retail_order(conn, summary, numberOfItems, emailTime):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = conn.cursor()

    d_date = summary[2].replace(' PST', '')
    PaidDate = emailTime # datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    PaidSubtotal = summary[5].lstrip("$").replace(',', '')
    PaidShipping = summary[7].lstrip("$").replace(',', '')
    PaidTaxes = summary[6].lstrip("$").replace(',', '')
    PaidShipTaxes = summary[8].lstrip("$").replace(',', '')
    PaidDisc = 0  # retail_inv_rec[1]
    PaidTotal = summary[9].lstrip("$").replace(',', '')
    PaidPieces = numberOfItems
    addr1 = summary[10]
    addr2 = summary[11]
    city = summary[12]
    state = summary[13]
    zip = summary[14]

    try:
        cursor.execute("UPDATE RetailOrders SET PaidDate=? WHERE OrderNumber =?",(PaidDate, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidSubtotal=? WHERE OrderNumber =?", (PaidSubtotal, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidShipping=? WHERE OrderNumber =?", (PaidShipping, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidTaxes=? WHERE OrderNumber =?", (PaidTaxes, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidShippingTaxes=? WHERE OrderNumber =?", (PaidShipTaxes, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidDiscount=? WHERE OrderNumber =?", (PaidDisc, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidTotal=? WHERE OrderNumber =?", (PaidTotal, summary[3]))
        cursor.execute("UPDATE RetailOrders SET PaidPieces=? WHERE OrderNumber =?", (PaidPieces, summary[3]))
        cursor.execute("UPDATE RetailOrders SET ShipAddr1=? WHERE OrderNumber =?", (addr1, summary[3]))
        cursor.execute("UPDATE RetailOrders SET ShipAddr2=? WHERE OrderNumber =?", (addr2, summary[3]))
        cursor.execute("UPDATE RetailOrders SET City=? WHERE OrderNumber =?", (city, summary[3]))
        cursor.execute("UPDATE RetailOrders SET State=? WHERE OrderNumber =?", (state, summary[3]))
        cursor.execute("UPDATE RetailOrders SET Zip=? WHERE OrderNumber =?", (zip, summary[3]))

            # , PaidSubtotal=?, PaidShipping=?, PaidTaxes=?,"
                       # "PaidDisc=?, PaidTotal=?, PaidPieces=?, ShipAddr1=?, ShipAddr2=?,"
                       # "City=?, State=?, Zip=?"
        #                # "WHERE OrderNumber =?"
        #                ,
        #                (PaidDate, # PaidSubtotal, PaidShipping, PaidTaxes,
        #                 # PaidDisc, PaidTotal, PaidPieces, addr1, addr2,
        #                 # city, state, zip,
        #                 summary[3])
        #                )
        conn.commit()
        print("order saved")
    except:
        print("order failed to save")
        pass
def insert_transfer_order(dbconn, retail_inv_rec, count_items):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = dbconn.cursor()
    OrderNumber = retail_inv_rec[3]
    OrderPopup = retail_inv_rec[4]
    OrderEmail = retail_inv_rec[1]
    d_date = retail_inv_rec[2].replace(' PST','')
    InvDate = datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    InvSubtotal = retail_inv_rec[5].lstrip("$").replace(',','')
    InvShipping = retail_inv_rec[6].lstrip("$").replace(',','')
    InvTaxes = 0 #retail_inv_rec[6].lstrip("$").replace(',','')
    InvShippingTaxes = retail_inv_rec[7].lstrip("$").replace(',','')
    InvDisc = 0 #retail_inv_rec[1]
    InvTotal = retail_inv_rec[8].lstrip("$").replace(',','')
    InvPieces = count_items

    try:
        cursor.execute("INSERT INTO TransferOrders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, null,"
                       "null, null, null, null, null, null, null, null, null, null, null, null, null)",
                       (UUID, OrderNumber, OrderPopup, OrderEmail, InvDate,
                        InvSubtotal, InvTaxes, InvShipping, InvShippingTaxes,
                        InvDisc, InvTotal, InvPieces)
                       )
        dbconn.commit()
        print("order saved")
    except:
        print("order failed to save")
        pass
def insert_paid_transfer_order(conn, summary, numberOfItems, emailTime):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = conn.cursor()

    d_date = summary[2].replace(' PST', '')
    PaidDate = emailTime # datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    PaidSubtotal = summary[5].lstrip("$").replace(',', '')
    PaidShipping = summary[7].lstrip("$").replace(',', '')
    PaidTaxes = summary[6].lstrip("$").replace(',', '')
    PaidShipTaxes = summary[8].lstrip("$").replace(',', '')
    PaidDisc = 0  # retail_inv_rec[1]
    PaidTotal = summary[9].lstrip("$").replace(',', '')
    PaidPieces = numberOfItems
    addr1 = summary[10]
    addr2 = summary[11]
    city = summary[12]
    state = summary[13]
    zip = summary[14]

    try:
        cursor.execute("UPDATE TransferOrders SET PaidDate=? WHERE OrderNumber =?",(PaidDate, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidSubtotal=? WHERE OrderNumber =?", (PaidSubtotal, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidShipping=? WHERE OrderNumber =?", (PaidShipping, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidTaxes=? WHERE OrderNumber =?", (PaidTaxes, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidShippingTaxes=? WHERE OrderNumber =?", (PaidShipTaxes, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidDiscount=? WHERE OrderNumber =?", (PaidDisc, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidTotal=? WHERE OrderNumber =?", (PaidTotal, summary[3]))
        cursor.execute("UPDATE TransferOrders SET PaidPieces=? WHERE OrderNumber =?", (PaidPieces, summary[3]))
        cursor.execute("UPDATE TransferOrders SET ShipAddr1=? WHERE OrderNumber =?", (addr1, summary[3]))
        cursor.execute("UPDATE TransferOrders SET ShipAddr2=? WHERE OrderNumber =?", (addr2, summary[3]))
        cursor.execute("UPDATE TransferOrders SET City=? WHERE OrderNumber =?", (city, summary[3]))
        cursor.execute("UPDATE TransferOrders SET State=? WHERE OrderNumber =?", (state, summary[3]))
        cursor.execute("UPDATE TransferOrders SET Zip=? WHERE OrderNumber =?", (zip, summary[3]))

        conn.commit()
        print("order saved")
    except:
        print("order failed to save")
        pass
def update_paid_order(conn, summary, numberOfItems, emailTime):
    # Inserting record one by one
    from datetime import datetime
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = conn.cursor()

    d_date = summary[2].replace(' PST', '')
    PaidDate = emailTime # datetime.strptime(d_date, "%b %d %Y %I:%M %p")
    PaidSubtotal = summary[5].lstrip("$").replace(',', '')
    PaidShipping = summary[7].lstrip("$").replace(',', '')
    PaidTaxes = summary[6].lstrip("$").replace(',', '')
    PaidShipTaxes = summary[8].lstrip("$").replace(',', '')
    PaidDisc = 0  # retail_inv_rec[1]
    PaidTotal = summary[9].lstrip("$").replace(',', '')
    PaidPieces = numberOfItems
    addr1 = summary[10]
    addr2 = summary[11]
    city = summary[12]
    state = summary[13]
    zip = summary[14]

    try:
        cursor.execute("UPDATE Orders SET PaidDate=? WHERE OrderNumber =?",(PaidDate, summary[3]))
        cursor.execute("UPDATE Orders SET PaidSubtotal=? WHERE OrderNumber =?", (PaidSubtotal, summary[3]))
        cursor.execute("UPDATE Orders SET PaidShipping=? WHERE OrderNumber =?", (PaidShipping, summary[3]))
        cursor.execute("UPDATE Orders SET PaidTaxes=? WHERE OrderNumber =?", (PaidTaxes, summary[3]))
        cursor.execute("UPDATE Orders SET PaidShippingTaxes=? WHERE OrderNumber =?", (PaidShipTaxes, summary[3]))
        cursor.execute("UPDATE Orders SET PaidDiscount=? WHERE OrderNumber =?", (PaidDisc, summary[3]))
        cursor.execute("UPDATE Orders SET PaidTotal=? WHERE OrderNumber =?", (PaidTotal, summary[3]))
        cursor.execute("UPDATE Orders SET PaidPieces=? WHERE OrderNumber =?", (PaidPieces, summary[3]))
        cursor.execute("UPDATE Orders SET ShipAddr1=? WHERE OrderNumber =?", (addr1, summary[3]))
        cursor.execute("UPDATE Orders SET ShipAddr2=? WHERE OrderNumber =?", (addr2, summary[3]))
        cursor.execute("UPDATE Orders SET City=? WHERE OrderNumber =?", (city, summary[3]))
        cursor.execute("UPDATE Orders SET State=? WHERE OrderNumber =?", (state, summary[3]))
        cursor.execute("UPDATE Orders SET Zip=? WHERE OrderNumber =?", (zip, summary[3]))

        conn.commit()
        print("order saved")
    except:
        print("order failed to save")
        pass


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
    except:
        print("order item failed to save")
        pass

def insert_order_item(conn, items, orderNumber):
    cursor = conn.cursor()
    UUID = binascii.b2a_hex(os.urandom(12))
    if type(items[0]) is str:
        itemName = items[0]
        itemPrice = items[1].lstrip("$").replace(',', '')
        itemDisc = 0
        itemTotal = itemPrice
        itemLine = items[2]
    else:
        itemName = items[0][0]
        itemPrice = items[0][1].lstrip("$").replace(',', '')
        itemDisc = items[1][1].lstrip("-").lstrip("$").replace(',', '')
        itemTotal = float(itemPrice) - float(itemDisc)
        itemLine = items[0][2]
    try:
        cursor.execute("INSERT INTO OrderItems VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (UUID, orderNumber, itemLine, itemName, itemPrice, itemDisc, itemTotal))
        conn.commit()
        print("order item saved")
    except:
        print("order item failed to save")
        pass


def update_task_start_time(conn, task, time):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Task SET lastStartTime=? WHERE taskName =?", (time, task))
        conn.commit()
        return
    except:
        print("task failed to save")
        pass
def update_task_end_time(conn, task, time):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Task SET lastEndTime=? WHERE taskName =?", (time, task))
        conn.commit()
        return
    except:
        print("task failed to save")
        pass

def init_task(conn, task):
    UUID = binascii.b2a_hex(os.urandom(12))
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Tasks VALUES (?, ?, null, null)",
                    (UUID, task))
        conn.commit()
        return
    except:
        print("task exist")
        pass


import sqlite3
import os,binascii
import pandas as pd
import re
import datetime
import openpyxl


conn = sqlite3.connect("app/bless.db")
#
cursor = conn.cursor()
# Create Customers table
# cursor.execute('''
# DROP TABLE CUSTOMERS
# ''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS CUSTOMERS (
    CustomerID TEXT PRIMARY KEY NOT NULL,
    CustomerEmail TEXT UNIQUE NOT NULL,
    CustomerName TEXT NOT NULL,
    CustomerType TEXT NOT NULL,
    CustomerPhone TEXT NULL
)
''')
conn.commit()
#
# Create Products table
#  CategoryList JSON DEFAULT('[]') NULL
# UPDATE myTbl
# SET linkList = json_insert(linkList, '$[#]', "www.test.com")
# WHERE domain="blah";
# cursor.execute('''
# DROP TABLE Products
# ''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS Products (
    ProductID TEXT PRIMARY KEY NOT NULL,
    ProductSKU TEXT UNIQUE NOT NULL,
    ProductName TEXT NOT NULL,
    ProductSize TEXT NOT NULL,
    ProductStyle TEXT NOT NULL,
    UnitPrice REAL NOT NULL,
    InvProductName TEXT NOT NULL,
    ProductCategory TEXT NULL
)
''')
conn.commit()
#
# cursor.execute('''
# DROP TABLE PurchaseOrders
# ''')
# Create PurchaseOrders table
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
conn.commit()
# cursor.execute('''
# DROP TABLE PurchaseOrderItems
# ''')

# Create PurchaseOrderItems table
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
conn.commit()

# cursor.execute('''
# DROP TABLE RetailOrders
# ''')

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
conn.commit()


# cursor.execute('''
# DROP TABLE TransferOrders
# ''')
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
conn.commit()

# cursor.execute('''
# DROP TABLE OrderItems
# ''')

# Create OrderItems table
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
conn.commit()

# cursor.execute('''
# DROP TABLE OrderItems
# ''')

# Create Tasks table
cursor.execute('''
CREATE TABLE IF NOT EXISTS Tasks (
    taskID TEXT UNIQUE NOT NULL PRIMARY KEY,
    taskName TEXT UNIQUE NOT NULL,
    lastStartTime TEXT NULL,
    lastEndTime TEXT NULL
)
''')
conn.commit()

# Add sizing columns to Products (idempotent)
try:
    cursor.execute("ALTER TABLE Products ADD COLUMN SizeNormalized TEXT")
    conn.commit()
except:
    pass
try:
    cursor.execute("ALTER TABLE Products ADD COLUMN SizingFamily TEXT")
    conn.commit()
except:
    pass

# Create FitFeedback table
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
except:
    pass
try:
    cursor.execute("CREATE INDEX idx_fitfb_sku ON FitFeedback(ProductSKU)")
    conn.commit()
except:
    pass

# Backfill SizingFamily and SizeNormalized where missing
from app.sizing import classify_family, normalize_size as _normalize_size
_needs_backfill = cursor.execute(
    "SELECT COUNT(*) FROM Products WHERE SizingFamily IS NULL"
).fetchone()[0]
if _needs_backfill > 0:
    _rows = cursor.execute(
        "SELECT ProductID, ProductStyle, ProductSize FROM Products WHERE SizingFamily IS NULL"
    ).fetchall()
    for _row in _rows:
        _pid, _style, _size = _row[0], _row[1], _row[2]
        _family = classify_family(_style, _size)
        _norm = _normalize_size(_size)
        cursor.execute(
            "UPDATE Products SET SizingFamily=?, SizeNormalized=? WHERE ProductID=?",
            (_family, _norm, _pid)
        )
    conn.commit()

#insert_customer(conn, customerrec)
# insert_product(conn,productrec)
# insert_purchase_order(conn,purchase_order_rec)
df_cust = pd.read_sql_query("SELECT * from Customers", conn)
# print(df_cust.count())
df_retail_cust = df_cust[df_cust.CustomerType == "RETAIL"]
# print(df_retail_cust.count())
df_prod = pd.read_sql_query("SELECT * from Products", conn)
# print(df_prod.head())
df_po = pd.read_sql_query("SELECT * from PurchaseOrders", conn)

df_po_items = pd.read_sql_query("SELECT * from PurchaseOrderItems", conn)
df_monthToDate_po_paid = df_po.loc[(pd.to_datetime(df_po['OrderDate'],format='%Y-%m-%d %H:%M:%S').dt.month == 8)].loc[(pd.to_datetime(df_po['OrderDate'],format='%Y-%m-%d %H:%M:%S').dt.year == 2024)]
# Commit changes and close the connectionRetailOrders
df_orders = pd.read_sql_query("SELECT * from Orders", conn)
df_retail_orders = df_orders[df_orders.OrderType == "RETAIL"]
df_open_retail_invoice = df_retail_orders[df_retail_orders.PaidDate.isnull()]
df_transfer_orders = df_orders[df_orders.OrderType == "TRANSFER_OUT"]
df_monthToDate_paid = df_retail_orders.loc[pd.to_datetime(df_retail_orders['PaidDate'],format='%Y-%m-%d %H:%M:%S').dt.month == 8].loc[(pd.to_datetime(df_retail_orders['PaidDate'],format='%Y-%m-%d %H:%M:%S').dt.year == 2024)]
df_monthToDateTransfers_paid = df_transfer_orders.loc[pd.to_datetime(df_transfer_orders['PaidDate'],format='%Y-%m-%d %H:%M:%S').dt.month == 8].loc[df_transfer_orders['OrderType'] == "TRANSFER_OUT"].loc[(pd.to_datetime(df_transfer_orders['PaidDate'],format='%Y-%m-%d %H:%M:%S').dt.year == 2024)]
df_order_items = pd.read_sql_query("SELECT * from OrderItems", conn)
# print(df_monthToDate_paid['PaidSubtotal'].sum())
# print(df_monthToDate_paid['PaidTotal'].sum())
# print(df_monthToDate_paid['PaidPieces'].sum())
# print(df_monthToDateTransfers_paid['PaidSubtotal'].sum())
# print(df_monthToDateTransfers_paid['PaidTotal'].sum())
# print(df_monthToDate_po_paid['Total'].sum())
df_order_COGS = pd.read_sql_query("SELECT * from OrderItems LEFT JOIN Products on Products.InvProductName = OrderItems.ProductName ORDER BY OrderItems.OrderNumber", conn)
Month_to_date = [["", "Retail","Wholesale"],
                 ["(Field Report) Subtotal",df_monthToDate_paid['PaidSubtotal'].sum(),df_monthToDateTransfers_paid['PaidSubtotal'].sum()],
                 ["Revenue",df_monthToDate_paid['PaidTotal'].sum(),df_monthToDateTransfers_paid['PaidTotal'].sum()],
                 ["Pieces",df_monthToDate_paid['PaidPieces'].sum(), df_monthToDateTransfers_paid['PaidPieces'].sum()]
]
df_customer_LTV = pd.read_sql_query("SELECT CUSTOMERS.CustomerName, Sum(RetailOrders.PaidTotal) AS SumOfPaidTotal, Sum(RetailOrders.PaidPieces) AS SumOfPaidPieces"
                                    " FROM CUSTOMERS INNER JOIN RetailOrders ON CUSTOMERS.CustomerEmail = RetailOrders.OrderEmail"
                                    " GROUP BY CUSTOMERS.CustomerName;", conn)
df_prod.to_excel("product.xlsx")
print (Month_to_date)
# df_monthToDate_paid = df_retail_orders[pd.Timestamp(df_retail_orders.PaidDate) > pd.Timestamp('2023-10-01')]TransferOrders

conn.commit()
conn.close()
#
# print("Database schema created.")