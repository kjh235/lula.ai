import email.utils
import json
import logging
import os
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


invoice_link = r'<a href="(.*?)"(.*?)\s+Pay Invoice'


def _get_html_body(msg_obj):
    if msg_obj.is_multipart():
        for part in msg_obj.walk():
            if part.get_content_type() == 'text/html':
                return part.get_content()
    elif msg_obj.get_content_type() == 'text/html':
        return msg_obj.get_content()
    return ""


def message_parse(msg_obj):
    soup = BeautifulSoup(_get_html_body(msg_obj), 'html.parser')
    return [s for s in soup.stripped_strings if s]


def get_to_email(msg_obj):
    return email.utils.parseaddr(msg_obj['To'])[1]


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

def get_email_type(subject):
    if not subject:
        return None
    if re.search(r'LuLaRoe\s+Wholesale\s+Order\s+Confirmation', subject):
        return "PO"
    if re.search(r'My\s+LuLaRoe\s+Order\s+Number', subject):
        return "CUSTOMER_INV"
    if re.search(r'Purchase\s+Receipt\s+from\s+LuLaRoe', subject):
        return "CUSTOMER_PAID"
    if re.search(r'My\s+LuLaRoe\s+Transfer\s+Order\s+Number', subject):
        return "TRANSFER_INV"
    if re.search(r'Transfer\s+Receipt\s+from\s+LuLaRoe', subject):
        return "TRANSFER_PAID"
    return None

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




def get_order_summary(msg_obj):
    try:
        k = message_parse(msg_obj)
        recipient_email = get_to_email(msg_obj)
        EMAIL_TYPE_TO_PROCESS = get_email_type(msg_obj['Subject'])

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

def _lookup_po_field_indices(k):
    return {
        'BIN': get_index("Bin", k),
        'SUBTOTAL': get_index("Subtotal:", k),
        'SHIPPING': get_index("Shipping:", k),
        'TAXES': get_index("Taxes:", k),
        'TOTAL': get_index("Total:", k),
        'AMOUNT_PAID': get_index("Amount Paid:", k),
        'PRICE': get_index("Price:", k),
        'SHOPPING_CART': get_index("Shopping Cart", k),
    }


def purchase_order_parse(k, recipient_email):
    idx = _lookup_po_field_indices(k)
    ORDER_ITEM_COL = 7
    num_of_skus = int((idx['SUBTOTAL'] - idx['BIN']) / ORDER_ITEM_COL) - 1
    order_items = []
    for j in range(num_of_skus):
        items = []
        for i in range(ORDER_ITEM_COL):
            m = int(idx['BIN'] + (i + (j * ORDER_ITEM_COL)))
            items.append(k[m].replace("T/C 2", "T/C2"))
        order_items.append(items)
    sku_list = []
    qty_sum = 0
    ptn = r'(.*)\s([A-z0-9]+[\/]?[A-z0-9]*)$'
    for rows in order_items[1:]:
        if rows[0] != '99':
            qty_sum += float(rows[1])
            size = re.search(ptn, rows[3])
            if size is None:
                logger.warning("purchase_order_parse: could not parse size from %r, skipping row", rows[3])
                continue
            sku_list.append([rows[2], rows[3], rows[5], size[1], size[2]])
    order_summary = [k[idx['PRICE'] + 1], recipient_email, k[idx['SHOPPING_CART'] + 1],
                     k[idx['SUBTOTAL'] + 1], k[idx['SHIPPING'] + 1],
                     k[idx['TAXES'] + 1], k[idx['TOTAL'] + 1], qty_sum]
    sku_list = translate_productName_to_invoiceName(sku_list)
    return order_summary, order_items, sku_list