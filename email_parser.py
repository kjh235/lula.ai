import json
import logging
import os
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


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
def _load_translations():
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'product_name_translations.json')
    with open(json_path) as f:
        return json.load(f)

def translate_productName_to_invoiceName(sku_list):
    translations = _load_translations()
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
            logger.debug("PO: summary=%s items=%s skus=%s", order_summary, order_items, sku_list)
            return sku_list, order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "CUSTOMER_INV":
            customer, order_summary, order_items = retail_invoice_parse(k, recipient_email)
            logger.debug("CUSTOMER_INV: customer=%s summary=%s items=%s", customer, order_summary, order_items)
            return customer, order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "CUSTOMER_PAID":
            order_summary, order_items = retail_paid_parse(k, recipient_email)
            logger.debug("CUSTOMER_PAID: summary=%s items=%s", order_summary, order_items)
            return order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "TRANSFER_INV":
            customer, order_summary, order_items = transfer_invoice_parse(k, recipient_email)
            logger.debug("TRANSFER_INV: customer=%s summary=%s items=%s", customer, order_summary, order_items)
            return customer, order_summary, order_items

        if EMAIL_TYPE_TO_PROCESS == "TRANSFER_PAID":
            order_summary, order_items = transfer_paid_parse(k, recipient_email)
            logger.debug("TRANSFER_PAID: summary=%s items=%s", order_summary, order_items)
            return order_summary, order_items
    except Exception:
        logger.error("failed to parse email")


def get_index(text_to_find, k):
    if text_to_find in k:
        index = k.index(text_to_find)
        return index
    else:
        return 999


def _lookup_field_indices(k):
    return {
        'CUSTOMER_NAME': get_index("Customer", k),
        'BILL_TO': get_index("Bill To:", k),
        'SHIP_TO': get_index("Ship To:", k),
        'DATE': get_index("Date:", k),
        'ORDER_NUM': get_index("Order #:", k),
        'POPUP_NUM': get_index("Pop-Up #:", k),
        'ORDER_TOTAL': get_index("Order Total:", k),
        'ORDER_SUMMARY': get_index("Order Summary", k),
        'ITEMS_SUBTOTAL': get_index("Items Subtotal", k),
        'ORDER_DISCOUNT': get_index("Order Discount", k),
        'SUBTOTAL': get_index("Subtotal", k),
        'TAXES': get_index("Tax", k),
        'SandH': get_index("S&H", k),
        'SandH_Tax': get_index("S&H Tax", k),
        'TOTAL': get_index("Total", k),
    }


def _extract_order_items(k, order_summary_index, section_index, cols=2):
    num_skus = int((section_index - order_summary_index) / cols)
    order_items = []
    for j in range(num_skus):
        items = []
        for i in range(cols):
            m = int(order_summary_index + 1 + (i + (j * cols)))
            items.append(k[m])
        items.append(j + 1)
        order_items.append(items)
    return order_items


def _compute_section_index(idx, use_discount_fallback=False):
    discount = idx['ORDER_DISCOUNT']
    items_subtotal = idx['ITEMS_SUBTOTAL']
    subtotal = idx['SUBTOTAL']
    if use_discount_fallback:
        if discount == 999:
            if items_subtotal == 999:
                return subtotal
            return items_subtotal
        return min(items_subtotal, discount)
    if discount == 999:
        return subtotal
    return min(items_subtotal, discount)


def _get_tax(k, taxes_index):
    return '$0.00' if taxes_index == 999 else k[taxes_index + 1]


def _parse_shipping_address_retail(k, idx):
    addr_lines = idx['DATE'] - idx['SHIP_TO'] - 3
    addr1 = k[idx['SHIP_TO'] + 2]
    addr2 = ""
    if addr_lines > 1:
        addr2 = k[idx['SHIP_TO'] + 3]
    city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[idx['DATE'] - 1])
    return addr1, addr2, city_state_zip.group(1), city_state_zip.group(2), city_state_zip.group(3)


def _parse_shipping_address_transfer(k, idx):
    addr_lines = idx['DATE'] - idx['SHIP_TO'] - 3
    if addr_lines == 0:
        addr1 = k[idx['SHIP_TO'] + 1]
        addr2 = ""
        city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[idx['SHIP_TO'] + 2])
    elif addr_lines == 1:
        addr1 = k[idx['SHIP_TO'] + 2]
        addr2 = ""
        city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[idx['SHIP_TO'] + 3])
    else:
        addr1 = k[idx['SHIP_TO'] + 2]
        addr2 = k[idx['SHIP_TO'] + 3]
        city_state_zip = re.match(r'^([A-z\s\-\.]*)\s*\,\s([A-Z]{2})\s([0-9]{5})', k[idx['DATE'] - 1])
    return addr1, addr2, city_state_zip.group(1), city_state_zip.group(2), city_state_zip.group(3)


def invoice_parse(k, recipient_email, customer_type):
    idx = _lookup_field_indices(k)
    section_index = _compute_section_index(idx)
    order_items = _extract_order_items(k, idx['ORDER_SUMMARY'], section_index)
    tax = _get_tax(k, idx['TAXES'])
    order_summary = [k[idx['CUSTOMER_NAME'] + 1], recipient_email, k[idx['DATE'] + 1],
                     k[idx['ORDER_NUM'] + 1], k[idx['POPUP_NUM'] + 1],
                     k[idx['SUBTOTAL'] + 1], tax, k[idx['SandH'] + 1],
                     k[idx['SandH_Tax'] + 1], k[idx['TOTAL'] + 1]]
    customer = [k[idx['CUSTOMER_NAME'] + 1], recipient_email, customer_type]
    return customer, order_summary, order_items

transfer_invoice_parse = lambda k, email: invoice_parse(k, email, "TRANSFER")
retail_invoice_parse = lambda k, email: invoice_parse(k, email, "RETAIL")


def paid_parse(k, recipient_email, is_transfer=False):
    idx = _lookup_field_indices(k)
    section_index = _compute_section_index(idx, use_discount_fallback=True)
    order_items = _extract_order_items(k, idx['ORDER_SUMMARY'], section_index)
    if is_transfer:
        addr1, addr2, city, state, zip_code = _parse_shipping_address_transfer(k, idx)
    else:
        addr1, addr2, city, state, zip_code = _parse_shipping_address_retail(k, idx)
    tax = _get_tax(k, idx['TAXES'])
    order_summary = [k[idx['BILL_TO'] + 1], recipient_email, k[idx['DATE'] + 1],
                     k[idx['ORDER_NUM'] + 1], k[idx['POPUP_NUM'] + 1],
                     k[idx['SUBTOTAL'] + 1], tax, k[idx['SandH'] + 1],
                     k[idx['SandH_Tax'] + 1], k[idx['TOTAL'] + 1],
                     addr1, addr2, city, state, zip_code]
    order_items = extract_discount(order_items)
    return order_summary, order_items

retail_paid_parse = lambda k, email: paid_parse(k, email, is_transfer=False)
transfer_paid_parse = lambda k, email: paid_parse(k, email, is_transfer=True)

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