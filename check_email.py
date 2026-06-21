import base64
import email as email_lib
import email.policy
import logging
import os
import gmail
import email_parser
import data_management
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from datetime import datetime
import time

logger = logging.getLogger(__name__)


def _fetch_gmail_messages(creds, search_query):
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    result = service.users().messages().list(maxResults=500, userId='me', q=search_query).execute()
    messages = result.get('messages')
    if not messages:
        return
    for msg in messages:
        logger.debug("processing message %s", msg['id'])
        txt = service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
        data = txt['raw'].replace("-", "+").replace("_", "/")
        raw_bytes = base64.b64decode(data)
        msg_obj = email_lib.message_from_bytes(raw_bytes, policy=email.policy.default)
        email_epoch = int(txt['internalDate'][:-3])
        email_time = datetime.fromtimestamp(email_epoch, tz=None)
        yield msg['id'], msg_obj, email_time, service


def get_credentials_from_refresh_token(refresh_token):
    from google.oauth2.credentials import Credentials as GoogleCredentials
    return GoogleCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
        scopes=['https://www.googleapis.com/auth/gmail.readonly'],
    )


def purchaseOrders(creds, search_query, user_id):
    from app.db import get_conn
    for msg_id, decoded_data, _, _ in _fetch_gmail_messages(creds, search_query):
        conn = get_conn()
        try:
            sku_list, summary, POitems = email_parser.get_order_summary(decoded_data)
            try:
                for rows in (sku_list,) if type(sku_list[0]) is not list else sku_list:
                    data_management.insert_product(conn, user_id, rows)
                data_management.insert_purchase_order(conn, user_id, summary)
                for items in (POitems[1:],) if type(POitems[0]) is not list else POitems[1:]:
                    data_management.insert_purchase_order_item(conn, user_id, items, summary[0])
                data_management.apply_purchase_order_to_inventory(conn, user_id, summary[0])
            except Exception:
                logger.error("failed to process message %s", msg_id, exc_info=True)
        finally:
            conn.close()


def retailInvoices(creds, search_query, user_id):
    from app.db import get_conn
    for msg_id, decoded_data, _, _ in _fetch_gmail_messages(creds, search_query):
        conn = get_conn()
        try:
            customer, summary, orderItems = email_parser.get_order_summary(decoded_data)
            data_management.insert_customer(conn, user_id, customer)
            numberOfItems = len(orderItems)
            data_management.insert_order(conn, user_id, summary, numberOfItems)
            data_management.update_order_type(conn, user_id, summary[3], "RETAIL")
        except Exception:
            logger.error("failed to process message %s", msg_id, exc_info=True)
        finally:
            conn.close()


def retailPaid(creds, search_query, user_id):
    from app.db import get_conn
    for msg_id, decoded_data, email_time, _ in _fetch_gmail_messages(creds, search_query):
        conn = get_conn()
        try:
            summary, orderItems = email_parser.get_order_summary(decoded_data)
            numberOfItems = len(orderItems)
            data_management.update_paid_order(conn, user_id, summary, numberOfItems, email_time)
            for items in (orderItems,) if type(orderItems[0]) is not list else orderItems:
                data_management.insert_order_item(conn, user_id, items, summary[3])
            data_management.apply_order_to_inventory(conn, user_id, summary[3])
        except Exception:
            logger.error("failed to process message %s", msg_id, exc_info=True)
        finally:
            conn.close()


def transferInvoices(creds, search_query, user_id):
    from app.db import get_conn
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    my_email = service.users().getProfile(userId='me').execute()['emailAddress']
    for msg_id, decoded_data, _, _ in _fetch_gmail_messages(creds, search_query):
        conn = get_conn()
        try:
            customer, summary, orderItems = email_parser.get_order_summary(decoded_data)
            data_management.insert_customer(conn, user_id, customer)
            numberOfItems = len(orderItems)
            data_management.insert_order(conn, user_id, summary, numberOfItems)
            if summary[1] == my_email:
                data_management.update_order_type(conn, user_id, summary[3], "TRANSFER_IN")
            else:
                data_management.update_order_type(conn, user_id, summary[3], "TRANSFER_OUT")
        except Exception:
            logger.error("failed to process message %s", msg_id, exc_info=True)
        finally:
            conn.close()


def transferPaid(creds, search_query, user_id):
    from app.db import get_conn
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    my_email = service.users().getProfile(userId='me').execute()['emailAddress']
    for msg_id, decoded_data, email_time, _ in _fetch_gmail_messages(creds, search_query):
        conn = get_conn()
        try:
            summary, orderItems = email_parser.get_order_summary(decoded_data)
            numberOfItems = len(orderItems)
            data_management.update_paid_order(conn, user_id, summary, numberOfItems, email_time)
            for items in (orderItems,) if type(orderItems[0]) is not list else orderItems:
                data_management.insert_order_item(conn, user_id, items, summary[3])
            data_management.upsert_products_from_transfer_in(conn, user_id, summary[3])
            data_management.apply_order_to_inventory(conn, user_id, summary[3])
        except Exception:
            logger.error("failed to process message %s", msg_id, exc_info=True)
        finally:
            conn.close()


search_query_retail_invoices = 'in:anywhere from:noreply@lularoebless.com subject:"My LuLaRoe Order Number" after:2026/04/01'
search_query_transfer_invoices = 'in:anywhere from:noreply@lularoebless.com subject:"My LuLaRoe Transfer Order Number" after:2026/04/01'
search_query_purchase = 'from:noreply@lularoe.com subject: "LuLaRoe Wholesale Order Confirmation" after:2026/01/01'
search_query_retail_paid = 'in:anywhere from:noreply@lularoebless.com subject:"Purchase Receipt from LuLaRoe - Order Number" after:2026/05/01'
search_query_transfer_paid = 'in:anywhere from:noreply@lularoebless.com subject:"Transfer Receipt from LuLaRoe - Order Number" after:2026/04/01'


def sync_for_user(user_id, creds):
    """Run all email sync tasks for a specific user."""
    purchaseOrders(creds, search_query_purchase, user_id)
    retailInvoices(creds, search_query_retail_invoices, user_id)
    retailPaid(creds, search_query_retail_paid, user_id)
    transferInvoices(creds, search_query_transfer_invoices, user_id)
    transferPaid(creds, search_query_transfer_paid, user_id)


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    if len(sys.argv) < 2:
        print("Usage: python check_email.py <user_id>")
        sys.exit(1)
    user_id = sys.argv[1]
    from app.db import get_conn
    conn = get_conn()
    row = conn.execute("SELECT GoogleRefreshToken FROM Users WHERE UserID = %s", (user_id,)).fetchone()
    conn.close()
    if not row or not row['GoogleRefreshToken']:
        print(f"No refresh token found for user {user_id}")
        sys.exit(1)
    creds = get_credentials_from_refresh_token(row['GoogleRefreshToken'])
    sync_for_user(user_id, creds)
