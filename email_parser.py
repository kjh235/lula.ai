
import email
from email.message import EmailMessage
from bs4 import BeautifulSoup
import re
import numpy as np
import pandas as pd

def remove_patterns(input_text, patterns_to_remove):
    for pattern in patterns_to_remove:
        input_text = re.sub(pattern, '', input_text)
    return input_text.strip()
patterns_to_remove = [r'\=20',r'\=09',r'\=E2',r'\=80',r'\=94',r'\=3D09',r'\=3D99',r'\=3DE2',r'\=3D80',r'\=3D20',r'\=3D',r'\=',r'\\n',r'\\t',r'\'\'',r'\'',r'\"',r'\<[^>]*>',r'\?utf-8\?Q\?']


to_email_address_pattern = r'To\:\s+((.+)@(.+)\.com)X\-'


customer_invoice = 'C:\\Users\kjh23\OneDrive\Documents\Python Scripts\My LuLaRoe Order Number 101665959.eml'
purchase_order = 'C:\\Users\kjh23\OneDrive\Documents\Python Scripts\LuLaRoe Wholesale Order Confirmation.eml'
customer_paid_invoice = 'C:\\Users\kjh23\OneDrive\Documents\Python Scripts\Purchase Receipt from LuLaRoe - Order Number 101677472.eml'
transfer_invoice = 'C:\\Users\kjh23\OneDrive\Documents\Python Scripts\My LuLaRoe Transfer Order Number 101671946.eml'
transfer_paid_invoice_out = 'C:\\Users\kjh23\OneDrive\Documents\Python Scripts\Transfer Receipt from LuLaRoe - Order Number 101671946.eml'
transfer_paid_invoice_in = 'C:\\Users\kjh23\OneDrive\Documents\Python Scripts\Transfer Receipt from LuLaRoe - Order Number 101674649.eml'

with open(transfer_paid_invoice_out) as fp:
    # Create a text/plain message
    msg = EmailMessage()
    msg.set_content(fp.read())
    x = msg.get_payload()
# for part in msg.walk():
#     print(part.get_content_type())
# for part in msg.walk():
#     print(part.get_content_maintype() == 'multipart',
#           part.is_multipart())
# # typ, msgnums = imap.search(None, '(FROM "*@gmail.com")')
# msg = msgnums[0]
# #for num in msgnums[0].split():
# for part in msg.walk():
#     print(part.get_content_maintype() == 'multipart',
#       part.is_multipart())
#     #typ, data = imap.fetch(num, '(RFC822)')
#   # print('Message %s\n%s\n' % (num, data[0][1]))


# for part in msg2.walk():
#     print(part.get_content_type())

soup = BeautifulSoup(x, 'html.parser')
# print(BeautifulSoup(html_doc, "html.parser"))
# #print(soup.find_all("invoice-item"))
# for string in soup.stripped_strings:
#     print(repr(string))
# # print(soup.get_text())
# print (len(soup.contents))

# tables = [
#     [
#         [remove_patterns(td.get_text(strip=True), patterns_to_remove) for td in tr.find_all('td')]
#         for tr in table.find_all('tr')
#     ]
#     for table in soup.find_all('table')
# ]


k = []
for string in soup.stripped_strings:
    if len(string) > 0:
        k.append(remove_patterns(repr(string),patterns_to_remove))

while("" in k):
    k.remove("")



PURCHASE_ORDER_SUBJECT = r'Subject: LuLaRoe Wholesale Order Confirmation'
purchase_invoice_subject = r'Subject: MyLuLaRoeOrderNumber'
customer_paid_invoice_subject = r'Subject: PurchaseReceiptfromLuLaRoe-OrderNumber'
transfer_invoice_subject = r'Subject: MyLuLaRoeTransferOrderNumber'
transfer_paid_invoice_subject = r'Subject: TransferReceiptfromLuLaRoe-OrderNumber'

strings_to_keep = []
for lines in k:
    if (re.search(to_email_address_pattern, lines)):
        recipient_email = re.search(to_email_address_pattern, lines).group(1)
        break
    # If the string is data#'
for lines in k:
    if (re.match(PURCHASE_ORDER_SUBJECT, lines)):
        EMAIL_TYPE_TO_PROCESS = "PO"
        break
    if (re.match(purchase_invoice_subject, lines)):
        EMAIL_TYPE_TO_PROCESS = "CUSTOMER_INV"
        break
    if (re.match(customer_paid_invoice_subject, lines)):
        EMAIL_TYPE_TO_PROCESS = "CUSTOMER_PAID"
        break
    if (re.match(transfer_invoice_subject, lines)):
        EMAIL_TYPE_TO_PROCESS = "TRANSFER_INV"
        break
    if (re.match(transfer_paid_invoice_subject, lines)):
        EMAIL_TYPE_TO_PROCESS = "TRANSFER_PAID"
        break

if EMAIL_TYPE_TO_PROCESS == "PO":
    BIN = "Bin"
    BIN_INDEX = k.index(BIN)
    SUBTOTAL = "Subtotal:"
    SUBTOTAL_INDEX = k.index(SUBTOTAL)
    SHIPPING = "Shipping:"
    SHIPPING_INDEX = k.index(SHIPPING)
    TAXES = "Taxes:"
    TAXES_INDEX = k.index(TAXES)
    TOTAL = "Total:"
    TOTAL_INDEX = k.index(TOTAL)
    AMOUNT_PAID = "Amount Paid:"
    AMOUNT_PAID_INDEX = k.index(AMOUNT_PAID)
    PRICE = "Price:"
    PRICE_INDEX = k.index(PRICE)
    SHOPPING_CART = "Shopping Cart"
    SHOPPING_CART_INDEX = k.index(SHOPPING_CART)
    NUM_OF_SKUS = int((SUBTOTAL_INDEX - BIN_INDEX) / 7) - 1
    ORDER_ITEM_COL = 7

    order_items = []
    j = 0
    while j < (NUM_OF_SKUS):
        i = 0
        items = []
        while i < (ORDER_ITEM_COL):
            m = int(BIN_INDEX + (i + (j * ORDER_ITEM_COL)))
            items.append(k[m])
            i += 1
        order_items.append(items)
        j += 1
    order_summary = []
    sku_list = []
    qty_sum = 0
    for rows in order_items[1:]:
        if rows[0] != '99':
            qty_sum += float(rows[1])
            sku_list.append([rows[2], rows[3], rows[5]])
    # conn = sqlite3.connect('purchase_orders.db')
    # cursor = conn.cursor()
    # # for rows in sku_list:
    # #    cursor.execute('''
    # #    INSERT INTO Products (ProductID, ProductName, UnitPrice)
    # #     VALUES (?, ?, ?)
    # #     ''', (sku_list[0], sku_list[1], sku_list[2]))
    # # Commit changes and close the connection
    # conn.commit()
    # conn.close()

    summary_header = ["order number","email", "date", "subtotal", "shipping", "taxes", "total", "item_qty"]
    order_summary = [k[PRICE_INDEX + 1], recipient_email, k[SHOPPING_CART_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], k[SHIPPING_INDEX + 1],
                     k[TAXES_INDEX + 1], k[TOTAL_INDEX + 1], qty_sum]
    print(sku_list)

if EMAIL_TYPE_TO_PROCESS == "CUSTOMER_INV":
    CUSTOMER_NAME = "Customer"
    CUSTOMER_NAME_INDEX = k.index(CUSTOMER_NAME)
    DATE = "Date:"
    DATE_INDEX = k.index(DATE)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = k.index(ORDER_NUM)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = k.index(POPUP_NUM)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = k.index(ORDER_TOTAL)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = k.index(ORDER_SUMMARY)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = k.index(SUBTOTAL)
    SandH = "S&H"
    SandH_INDEX = k.index(SandH)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = k.index(SandH_Tax)
    TOTAL = "Total"
    TOTAL_INDEX = k.index(TOTAL)
    NUM_OF_SKUS = int((SUBTOTAL_INDEX - ORDER_SUMMARY_INDEX) / 2)
    order_items = []
    ORDER_ITEM_COL = 2
    j = 0
    while j < (NUM_OF_SKUS):
        i = 0
        items = []
        while i < (ORDER_ITEM_COL):
            m = int(ORDER_SUMMARY_INDEX + 1 + (i + (j * ORDER_ITEM_COL)))
            items.append(k[m])
            i += 1
        order_items.append(items)
        j += 1
    order_summary = []
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                      "Shipping Tax", "total"]
    order_summary = [k[CUSTOMER_NAME_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1]
                     ]

if EMAIL_TYPE_TO_PROCESS == "CUSTOMER_PAID":
    BILL_TO = "Bill To:"
    BILL_TO_INDEX = k.index(BILL_TO)
    SHIP_TO = "Ship To:"
    SHIP_TO_INDEX = k.index(SHIP_TO)
    DATE = "Date:"
    DATE_INDEX = k.index(DATE)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = k.index(ORDER_NUM)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = k.index(POPUP_NUM)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = k.index(ORDER_TOTAL)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = k.index(ORDER_SUMMARY)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = k.index(SUBTOTAL)
    SandH = "S&H"
    SandH_INDEX = k.index(SandH)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = k.index(SandH_Tax)
    TOTAL = "Total"
    TOTAL_INDEX = k.index(TOTAL)
    NUM_OF_SKUS = int((SUBTOTAL_INDEX - ORDER_SUMMARY_INDEX) / 2)
    order_items = []
    ORDER_ITEM_COL = 2
    j = 0
    while j < (NUM_OF_SKUS):
        i = 0
        items = []
        while i < (ORDER_ITEM_COL):
            m = int(ORDER_SUMMARY_INDEX + 1 + (i + (j * ORDER_ITEM_COL)))
            items.append(k[m])
            i += 1
        order_items.append(items)
        j += 1

    addr_lines = DATE_INDEX - SHIP_TO_INDEX - 3

    addr1 = k[SHIP_TO_INDEX + 2 + addr_lines - 1]
    addr2 = ""
    if addr_lines > 1:
        addr2 = k[SHIP_TO_INDEX + 2 + addr_lines]
    city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[DATE_INDEX - 1])
    city = city_state_zip.group(1)
    state = city_state_zip.group(2)
    zip = city_state_zip.group(3)

    order_summary = []
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                      "Shipping Tax", "total"
        , "ship addr1", "ship addr2", "ship city", "ship state", "ship zip"]
    order_summary = [k[BILL_TO_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1],
                     addr1, addr2, city, state, zip
                     ]

if EMAIL_TYPE_TO_PROCESS == "TRANSFER_INV":
    CUSTOMER_NAME = "Customer"
    CUSTOMER_NAME_INDEX = k.index(CUSTOMER_NAME)
    DATE = "Date:"
    DATE_INDEX = k.index(DATE)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = k.index(ORDER_NUM)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = k.index(POPUP_NUM)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = k.index(ORDER_TOTAL)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = k.index(ORDER_SUMMARY)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = k.index(SUBTOTAL)
    SandH = "S&H"
    SandH_INDEX = k.index(SandH)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = k.index(SandH_Tax)
    TOTAL = "Total"
    TOTAL_INDEX = k.index(TOTAL)
    NUM_OF_SKUS = int((SUBTOTAL_INDEX - ORDER_SUMMARY_INDEX) / 2)
    order_items = []
    ORDER_ITEM_COL = 2
    j = 0
    while j < (NUM_OF_SKUS):
        i = 0
        items = []
        while i < (ORDER_ITEM_COL):
            m = int(ORDER_SUMMARY_INDEX + 1 + (i + (j * ORDER_ITEM_COL)))
            items.append(k[m])
            i += 1
        order_items.append(items)
        j += 1
    order_summary = []
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                      "Shipping Tax", "total"]
    order_summary = [k[CUSTOMER_NAME_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1]
                     ]

if EMAIL_TYPE_TO_PROCESS == "TRANSFER_PAID":
    BILL_TO = "Bill To:"
    BILL_TO_INDEX = k.index(BILL_TO)
    SHIP_TO = "Ship To:"
    SHIP_TO_INDEX = k.index(SHIP_TO)
    DATE = "Date:"
    DATE_INDEX = k.index(DATE)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = k.index(ORDER_NUM)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = k.index(POPUP_NUM)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = k.index(ORDER_TOTAL)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = k.index(ORDER_SUMMARY)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = k.index(SUBTOTAL)
    SandH = "S&H"
    SandH_INDEX = k.index(SandH)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = k.index(SandH_Tax)
    TOTAL = "Total"
    TOTAL_INDEX = k.index(TOTAL)
    NUM_OF_SKUS = int((SUBTOTAL_INDEX - ORDER_SUMMARY_INDEX) / 2)
    order_items = []
    ORDER_ITEM_COL = 2
    j = 0
    while j < (NUM_OF_SKUS):
        i = 0
        items = []
        while i < (ORDER_ITEM_COL):
            m = int(ORDER_SUMMARY_INDEX + 1 + (i + (j * ORDER_ITEM_COL)))
            items.append(k[m])
            i += 1
        order_items.append(items)
        j += 1

    addr_lines = DATE_INDEX - SHIP_TO_INDEX - 3

    addr1 = k[SHIP_TO_INDEX + 2 + addr_lines - 1]
    addr2 = ""
    if addr_lines > 1:
        addr2 = k[SHIP_TO_INDEX + 2 + addr_lines]
    city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[DATE_INDEX - 1])
    city = city_state_zip.group(1)
    state = city_state_zip.group(2)
    zip = city_state_zip.group(3)

    order_summary = []
    summary_header = ["customer", "date", "order number", "popup number", "subtotal", "shipping",
                      "Shipping Tax", "total"
        , "ship addr1", "ship addr2", "ship city", "ship state", "ship zip"]
    order_summary = [k[BILL_TO_INDEX + 1], k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1],
                     addr1, addr2, city, state, zip
                  ]


def extract_discount(order_items):
    order_items_new = []
    order_items_to_transpose = []
    for t in order_items:
        pp = t[0]
        ll = t[1]
        if (ll[0:1]) == 'D':
            order_items_to_transpose.append(t)
        elif (ll[0:1]) == '-':
            order_items_to_transpose.append(t)
        else:
            order_items_new.append(t)

        if len(order_items_to_transpose) == 2:
            arr_t = np.array(order_items_to_transpose).T.tolist()
            order_items_new.append(arr_t)
            order_items_to_transpose = []
    return order_items_new


order_items = extract_discount(order_items)
print(order_summary)
print(order_items)