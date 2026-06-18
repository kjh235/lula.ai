import base64
import sqlite3
import os,binascii
import gmail, email_parser, data_management
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from datetime import datetime
import time


def _fetch_gmail_messages(creds, search_query):
    service = build('gmail', 'v1', credentials=creds)
    result = service.users().messages().list(maxResults=500, userId='me', q=search_query).execute()
    messages = result.get('messages')
    for msg in messages:
        print(msg['id'])
        txt = service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
        data = txt['raw'].replace("-", "+").replace("_", "/")
        decoded_data = base64.b64decode(data)
        email_epoch = int(txt['internalDate'][:-3])
        email_time = datetime.fromtimestamp(email_epoch, tz=None)
        yield msg['id'], decoded_data, email_time, service


def purchaseOrders(creds, search_query):
    for msg_id, decoded_data, _, _ in _fetch_gmail_messages(creds, search_query):
        with sqlite3.connect("app/bless.db") as conn:
            sku_list, summary, POitems = email_parser.get_order_summary(decoded_data)
            try:
                for rows in (sku_list,) if type(sku_list[0]) is not list else sku_list:
                    data_management.insert_product(conn, rows)
                data_management.insert_purchase_order(conn, summary)
                for items in (POitems[1:],) if type(POitems[0]) is not list else POitems[1:]:
                    data_management.insert_purchase_order_item(conn, items, summary[0])
                data_management.apply_purchase_order_to_inventory(conn, summary[0])
            except Exception:
                print(msg_id)


def retailInvoices(creds, search_query):
    for msg_id, decoded_data, _, _ in _fetch_gmail_messages(creds, search_query):
        with sqlite3.connect("app/bless.db") as conn:
            try:
                customer, summary, orderItems = email_parser.get_order_summary(decoded_data)
                data_management.insert_customer(conn, customer)
                numberOfItems = len(orderItems)
                data_management.insert_order(conn, summary, numberOfItems)
                data_management.update_order_type(conn, summary[3], "RETAIL")
            except Exception:
                print(msg_id)


def retailPaid(creds, search_query):
    for msg_id, decoded_data, email_time, _ in _fetch_gmail_messages(creds, search_query):
        with sqlite3.connect("app/bless.db") as conn:
            summary, orderItems = email_parser.get_order_summary(decoded_data)
            numberOfItems = len(orderItems)
            try:
                data_management.update_paid_order(conn, summary, numberOfItems, email_time)
                for items in (orderItems,) if type(orderItems[0]) is not list else orderItems:
                    data_management.insert_order_item(conn, items, summary[3])
                data_management.apply_order_to_inventory(conn, summary[3])
            except Exception:
                print(msg_id)


def transferInvoices(creds, search_query):
    service = build('gmail', 'v1', credentials=creds)
    my_email = service.users().getProfile(userId='me').execute()['emailAddress']
    for msg_id, decoded_data, _, _ in _fetch_gmail_messages(creds, search_query):
        with sqlite3.connect("app/bless.db") as conn:
            try:
                customer, summary, orderItems = email_parser.get_order_summary(decoded_data)
                data_management.insert_customer(conn, customer)
                numberOfItems = len(orderItems)
                data_management.insert_order(conn, summary, numberOfItems)
                if summary[1] == my_email:
                    data_management.update_order_type(conn, summary[3], "TRANSFER_IN")
                else:
                    data_management.update_order_type(conn, summary[3], "TRANSFER_OUT")
            except Exception:
                print(msg_id)


def transferPaid(creds, search_query):
    service = build('gmail', 'v1', credentials=creds)
    my_email = service.users().getProfile(userId='me').execute()['emailAddress']
    for msg_id, decoded_data, email_time, _ in _fetch_gmail_messages(creds, search_query):
        with sqlite3.connect("app/bless.db") as conn:
            try:
                summary, orderItems = email_parser.get_order_summary(decoded_data)
                numberOfItems = len(orderItems)
                data_management.update_paid_order(conn, summary, numberOfItems, email_time)
                for items in (orderItems,) if type(orderItems[0]) is not list else orderItems:
                    data_management.insert_order_item(conn, items, summary[3])
                data_management.upsert_products_from_transfer_in(conn, summary[3])
                data_management.apply_order_to_inventory(conn, summary[3])
            except Exception:
                print(msg_id)


search_query_retail_invoices = 'in:anywhere from:noreply@lularoebless.com subject:"My LuLaRoe Order Number" after:2026/04/01'
search_query_transfer_invoices = 'in:anywhere from:noreply@lularoebless.com subject:"My LuLaRoe Transfer Order Number" after:2026/04/01'
search_query_purchase = 'from:noreply@lularoe.com subject: "LuLaRoe Wholesale Order Confirmation" after:2026/01/01'
search_query_retail_paid = 'in:anywhere from:noreply@lularoebless.com subject:"Purchase Receipt from LuLaRoe - Order Number" after:2026/05/01'
search_query_transfer_paid = 'in:anywhere from:noreply@lularoebless.com subject:"Transfer Receipt from LuLaRoe - Order Number" after:2026/04/01'

if __name__ == '__main__':
    data_management.init_db()
    with sqlite3.connect("app/bless.db", timeout=10) as conn:
        data_management.init_task(conn, "CHECK_EMAILS")
        data_management.update_task_start_time(conn, "CHECK_EMAILS", time.time())
    creds = gmail.gmail_creds()
    with sqlite3.connect("app/bless.db", timeout=10) as conn:
        purchaseOrders(creds, search_query_purchase)
        #retailInvoices(creds, search_query_retail_invoices)
        #retailPaid(creds, search_query_retail_paid)
        #transferInvoices(creds, search_query_transfer_invoices)
        #transferPaid(creds, search_query_transfer_paid)
    with sqlite3.connect("app/bless.db", timeout=10) as conn:
        data_management.update_task_end_time(conn, "CHECK_EMAILS", time.time())
