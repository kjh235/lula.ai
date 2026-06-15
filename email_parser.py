from bs4 import BeautifulSoup
import re


def remove_patterns(input_text, patterns_to_remove):
    for pattern in patterns_to_remove:
        input_text = re.sub(pattern, '', input_text)
    return input_text.strip()

patterns_to_remove = [r'\=20',r'\=09',r'\=E2',r'\=80',r'\=94',r'\=3D09',r'\=3D99',r'\=3DE2',r'\=3D80',r'\=3D20',r'\=3D',r'\=',r'\\n',r'\\r',r'\\t',r'\'\'',r'\'',r'\"',r'\<[^>]*>',r'\?utf-8\?Q\?']

invoice_link = r'<a href="(.*?)"(.*?)\s+Pay Invoice'


def message_parse(x, patterns_to_remove):
    soup = BeautifulSoup(x, 'html.parser')
    parsed_text = []
    for string in soup.stripped_strings:
        if len(string) > 0:
            parsed_text.append(remove_patterns(repr(string), patterns_to_remove))
    while ("" in parsed_text):
        parsed_text.remove("")
    return parsed_text

def get_to_email(input_email_txt):
    to_email_address_pattern = r'To\:\s+([a-zA-Z0-9._]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*)X\-'
    for rows in input_email_txt:
        if (re.search(to_email_address_pattern, rows)):
            to_email = re.search(to_email_address_pattern, rows).group(1)
            return to_email
def translate_productName_to_invoiceName(sku_list):
    translations = {
        "HW23":"Witchful Thinking Halloween",
        "CZY23" :"Cozy",
        "CZY20": "Cozy",
        "Flare Jean":"Denim Flared",
        #"Single Solid" : "Solid",
        "OTD23" : "Great Outdoors 2023",
        "Single Print Leggings":"Single Pack Leggings - Prints",
        "RSRT22":"Resort 2022",
        "RSRT23 ": "",
        "CRER23":"Career Career",
        "CRER22": "Career 2022",
        "4J23":"Americana 2023",
        "4J22": "Americana 2022",
        "DREAM22 ":"",
        "DREAM21 ": "",
        "High Rise Slim Straight":"",
        "SP22 ":"",
        "VL22 ":"",
        "HW22":"Halloween 2022",
        "HW21": "Halloween 2021",
        "BOHO22 ":"",
        "LUXE21 ":"",
        "DNM21 ":"",
        "DR21 ": "",
        "BCA21":"BCA 2021",
        "ATR23":"Animal"
        }
    new_sku_list = []
    for i in sku_list:
        sku = i
        invProductName = re.sub(r'(?<=)(\w+)(?=)', lambda m: translations.get(m.group(), m.group()), i[1])
        sku.append(invProductName)
        new_sku_list.append(sku)
    return new_sku_list

def get_email_type(k):
    PURCHASE_ORDER_SUBJECT = r'Subject\:\s+LuLaRoe\s+Wholesale\s+Order\s+Confirmation'
    purchase_invoice_subject = r'Subject: MyLuLaRoeOrderNumber'
    customer_paid_invoice_subject = r'Subject: PurchaseReceiptfromLuLaRoe-OrderNumber'
    transfer_invoice_subject = r'Subject: MyLuLaRoeTransferOrderNumber'
    transfer_paid_invoice_subject = r'Subject: TransferReceiptfromLuLaRoe-OrderNumber'
    for lines in k:
        if re.search(PURCHASE_ORDER_SUBJECT, lines):
            return "PO"
        if (re.search(purchase_invoice_subject, lines)):
            return "CUSTOMER_INV"
        if (re.search(customer_paid_invoice_subject, lines)):
            return "CUSTOMER_PAID"
        if (re.search(transfer_invoice_subject, lines)):
            return "TRANSFER_INV"
        if (re.search(transfer_paid_invoice_subject, lines)):
            return "TRANSFER_PAID"

def extract_discount(order_items):
        order_items_new = []
        order_items_to_transpose = []
        for t in order_items:
            pp = t[0]
            ll = t[1]
            if (ll[0:1]) == 'D':
                order_items_to_transpose.append(t)
                item_number = t[2]
            elif (ll[0:1]) == '-':
                order_items_to_transpose.append(t)
            else:
                order_items_new.append(t)


            if len(order_items_to_transpose) == 2:
                test = order_items_to_transpose.copy()
                a = order_items_to_transpose[1][0]
                b = order_items_to_transpose[0][1]
                c = order_items_to_transpose[0][2]
                test[0][1] = a
                test[1][0] = b
                test[1][2] = c
                order_items_new.append(test)
                order_items_to_transpose = []
        return order_items_new




def get_order_summary(x):
    try:
        k = message_parse(x, patterns_to_remove)
        recipient_email = get_to_email(k)
        EMAIL_TYPE_TO_PROCESS = get_email_type(k)

        if EMAIL_TYPE_TO_PROCESS == "PO":
            order_summary, order_items, sku_list = purchase_order_parse(k, recipient_email)
            print(order_summary)
            print(order_items)
            print(sku_list)
            return sku_list, order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "CUSTOMER_INV":
            customer, order_summary, order_items = retail_invoice_parse(k, recipient_email)
            print(customer)
            print(order_summary)
            print(order_items)
            return customer, order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "CUSTOMER_PAID":
            order_summary, order_items = retail_paid_parse(k, recipient_email)
            print(order_summary)
            print(order_items)
            return order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "TRANSFER_INV":
            customer, order_summary, order_items = transfer_invoice_parse(k, recipient_email)
            print(customer)
            print(order_summary)
            print(order_items)
            return customer, order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "TRANSFER_PAID":
            order_summary, order_items = transfer_paid_parse(k, recipient_email)
            print(order_summary)
            print(order_items)
            return order_summary, order_items
    except:
        print("err")


def get_index(text_to_find, k):
    if text_to_find in k:
        index = k.index(text_to_find)
        return index
    else:
        return 999


def transfer_invoice_parse(k, recipient_email):
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
    ITEMS_SUBTOTAL = "Items Subtotal"
    ITEMS_SUBTOTAL_INDEX = get_index(ITEMS_SUBTOTAL, k)
    ORDER_DISCOUNT = "Order Discount"
    ORDER_DISCOUNT_INDEX = get_index(ORDER_DISCOUNT, k)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = k.index(SUBTOTAL)
    TAXES = "Tax"
    TAXES_INDEX = get_index(TAXES, k)
    SandH = "S&H"
    SandH_INDEX = k.index(SandH)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = k.index(SandH_Tax)
    TOTAL = "Total"
    TOTAL_INDEX = k.index(TOTAL)
    if ORDER_DISCOUNT_INDEX == 999:
        SECTION_INDEX = SUBTOTAL_INDEX
    else:
        SECTION_INDEX = min(ITEMS_SUBTOTAL_INDEX, ORDER_DISCOUNT_INDEX)
    NUM_OF_SKUS = int((SECTION_INDEX - ORDER_SUMMARY_INDEX) / 2)
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
        items.append(j + 1)
        order_items.append(items)
        j += 1
    if TAXES_INDEX == 999:
        tax = '$0.00'
    else:
        tax = k[TAXES_INDEX + 1]
    order_summary = []
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                      "Shipping Tax", "total"]
    order_summary = [k[CUSTOMER_NAME_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], tax, k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1]
                     ]
    customer = [k[CUSTOMER_NAME_INDEX + 1], recipient_email, "TRANSFER"]
    return customer, order_summary, order_items


def retail_invoice_parse(k, recipient_email):
    CUSTOMER_NAME = "Customer"
    CUSTOMER_NAME_INDEX = get_index(CUSTOMER_NAME, k)
    DATE = "Date:"
    DATE_INDEX = get_index(DATE, k)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = get_index(ORDER_NUM, k)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = get_index(POPUP_NUM, k)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = get_index(ORDER_TOTAL, k)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = get_index(ORDER_SUMMARY, k)
    ITEMS_SUBTOTAL = "Items Subtotal"
    ITEMS_SUBTOTAL_INDEX = get_index(ITEMS_SUBTOTAL, k)
    ORDER_DISCOUNT = "Order Discount"
    ORDER_DISCOUNT_INDEX = get_index(ORDER_DISCOUNT, k)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = get_index(SUBTOTAL, k)
    TAXES = "Tax"
    TAXES_INDEX = get_index(TAXES, k)
    SandH = "S&H"
    SandH_INDEX = get_index(SandH, k)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = get_index(SandH_Tax, k)
    TOTAL = "Total"
    TOTAL_INDEX = get_index(TOTAL, k)
    if ORDER_DISCOUNT_INDEX == 999 :
        SECTION_INDEX = SUBTOTAL_INDEX
    else:
        SECTION_INDEX = min(ITEMS_SUBTOTAL_INDEX,ORDER_DISCOUNT_INDEX)
    NUM_OF_SKUS = int((SECTION_INDEX - ORDER_SUMMARY_INDEX) / 2)
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
        items.append(j + 1)
        order_items.append(items)
        j += 1
    if TAXES_INDEX == 999:
        tax = '$0.00'
    else:
        tax = k[TAXES_INDEX + 1]
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                      "Tax", "Shipping Tax", "total"]
    order_summary = [k[CUSTOMER_NAME_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], tax, k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1]
                     ]
    customer = [k[CUSTOMER_NAME_INDEX + 1], recipient_email, "RETAIL"]
    return customer, order_summary, order_items


def retail_paid_parse(k, recipient_email):
    BILL_TO = "Bill To:"
    BILL_TO_INDEX = get_index(BILL_TO, k)
    SHIP_TO = "Ship To:"
    SHIP_TO_INDEX = get_index(SHIP_TO, k)
    DATE = "Date:"
    DATE_INDEX = get_index(DATE, k)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = get_index(ORDER_NUM, k)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = get_index(POPUP_NUM, k)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = get_index(ORDER_TOTAL, k)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = get_index(ORDER_SUMMARY, k)
    ITEMS_SUBTOTAL = "Items Subtotal"
    ITEMS_SUBTOTAL_INDEX = get_index(ITEMS_SUBTOTAL, k)
    DISCOUNT = "Order Discount"
    DISCOUNT_INDEX = get_index(DISCOUNT, k)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = get_index(SUBTOTAL, k)
    TAXES = "Tax"
    TAXES_INDEX = get_index(TAXES, k)
    SandH = "S&H"
    SandH_INDEX = get_index(SandH, k)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = get_index(SandH_Tax, k)
    TOTAL = "Total"
    TOTAL_INDEX = get_index(TOTAL, k)

    if DISCOUNT_INDEX == 999:
        if ITEMS_SUBTOTAL_INDEX == 999:
            SECTION_INDEX = SUBTOTAL_INDEX
        else:
            SECTION_INDEX = ITEMS_SUBTOTAL_INDEX
    else:
        SECTION_INDEX = min(ITEMS_SUBTOTAL_INDEX, DISCOUNT_INDEX)
    NUM_OF_SKUS = int((SECTION_INDEX - ORDER_SUMMARY_INDEX) / 2)
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
        items.append(j + 1)
        order_items.append(items)
        j += 1
    addr_lines = DATE_INDEX - SHIP_TO_INDEX - 3
    addr1 = k[SHIP_TO_INDEX + 2]
    addr2 = ""
    if addr_lines > 1:
        addr2 = k[SHIP_TO_INDEX + 3]
    city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[DATE_INDEX - 1])
    city = city_state_zip.group(1)
    state = city_state_zip.group(2)
    zip = city_state_zip.group(3)
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                       "Tax", "Shipping Tax", "total"
        , "ship addr1", "ship addr2", "ship city", "ship state", "ship zip"]
    if TAXES_INDEX == 999:
        tax = '$0.00'
    else:
        tax = k[TAXES_INDEX + 1]
    order_summary = [k[BILL_TO_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], tax, k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1],
                     addr1, addr2, city, state, zip
                     ]
    order_items = extract_discount(order_items)
    return order_summary, order_items
def transfer_paid_parse(k, recipient_email):
    BILL_TO = "Bill To:"
    BILL_TO_INDEX = get_index(BILL_TO, k)
    SHIP_TO = "Ship To:"
    SHIP_TO_INDEX = get_index(SHIP_TO, k)
    DATE = "Date:"
    DATE_INDEX = get_index(DATE, k)
    ORDER_NUM = "Order #:"
    ORDER_NUM_INDEX = get_index(ORDER_NUM, k)
    POPUP_NUM = "Pop-Up #:"
    POPUP_NUM_INDEX = get_index(POPUP_NUM, k)
    ORDER_TOTAL = "Order Total:"
    ORDER_TOTAL_INDEX = get_index(ORDER_TOTAL, k)
    ORDER_SUMMARY = "Order Summary"
    ORDER_SUMMARY_INDEX = get_index(ORDER_SUMMARY, k)
    ITEMS_SUBTOTAL = "Items Subtotal"
    ITEMS_SUBTOTAL_INDEX = get_index(ITEMS_SUBTOTAL, k)
    DISCOUNT = "Order Discount"
    DISCOUNT_INDEX = get_index(DISCOUNT, k)
    SUBTOTAL = "Subtotal"
    SUBTOTAL_INDEX = get_index(SUBTOTAL, k)
    TAXES = "Tax"
    TAXES_INDEX = get_index(TAXES, k)
    SandH = "S&H"
    SandH_INDEX = get_index(SandH, k)
    SandH_Tax = "S&H Tax"
    SandH_Tax_INDEX = get_index(SandH_Tax, k)
    TOTAL = "Total"
    TOTAL_INDEX = get_index(TOTAL, k)

    if DISCOUNT_INDEX == 999:
        if ITEMS_SUBTOTAL_INDEX == 999:
            SECTION_INDEX = SUBTOTAL_INDEX
        else:
            SECTION_INDEX = ITEMS_SUBTOTAL_INDEX
    else:
        SECTION_INDEX = min(ITEMS_SUBTOTAL_INDEX, DISCOUNT_INDEX)
    NUM_OF_SKUS = int((SECTION_INDEX - ORDER_SUMMARY_INDEX) / 2)
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
        items.append(j+1)
        order_items.append(items)
        j += 1
    addr_lines = DATE_INDEX - SHIP_TO_INDEX - 3
    if addr_lines == 0:
        addr1 = k[SHIP_TO_INDEX + 1]
        addr2 = ""
        city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[SHIP_TO_INDEX + 2])
    if addr_lines == 1:
        addr1 = k[SHIP_TO_INDEX + 2]
        addr2 = ""
        city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[SHIP_TO_INDEX + 3])
    if addr_lines > 1:
        addr1 = k[SHIP_TO_INDEX + 2]
        addr2 = k[SHIP_TO_INDEX + 3]
        city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[DATE_INDEX - 1])
    city = city_state_zip.group(1)
    state = city_state_zip.group(2)
    zip = city_state_zip.group(3)
    summary_header = ["customer", "email", "date", "order number", "popup number", "subtotal", "shipping",
                       "Tax", "Shipping Tax", "total"
        , "ship addr1", "ship addr2", "ship city", "ship state", "ship zip"]
    if TAXES_INDEX == 999:
        tax = '$0.00'
    else:
        tax = k[TAXES_INDEX + 1]
    order_summary = [k[BILL_TO_INDEX + 1], recipient_email, k[DATE_INDEX + 1],
                     k[ORDER_NUM_INDEX + 1], k[POPUP_NUM_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], tax, k[SandH_INDEX + 1],
                     k[SandH_Tax_INDEX + 1], k[TOTAL_INDEX + 1],
                     addr1, addr2, city, state, zip
                     ]
    order_items = extract_discount(order_items)
    return order_summary, order_items

def purchase_order_parse(k, recipient_email):
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
            items.append(k[m].replace("T/C 2","T/C2"))
            i += 1
        order_items.append(items)
        j += 1
    order_summary = []
    sku_list = []
    qty_sum = 0
    ptn = r'(.*)\s([A-z0-9]+[\/]?[A-z0-9]*)$'
    for rows in order_items[1:]:
        if rows[0] != '99':
            qty_sum += float(rows[1])
            size = re.search(ptn, rows[3])
            sku_list.append([rows[2], rows[3], rows[5], size[1], size[2]])
    summary_header = ["order number", "email", "date", "subtotal", "shipping", "taxes", "total", "item_qty"]
    order_summary = [k[PRICE_INDEX + 1], recipient_email, k[SHOPPING_CART_INDEX + 1],
                     k[SUBTOTAL_INDEX + 1], k[SHIPPING_INDEX + 1],
                     k[TAXES_INDEX + 1], k[TOTAL_INDEX + 1], qty_sum]
    sku_list = translate_productName_to_invoiceName(sku_list)
    return order_summary, order_items, sku_list