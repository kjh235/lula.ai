"""
Browser automation for the LuLaRoe Bless consultant portal.

Logs in with stored credentials, paginates through each data section,
and upserts rows into the local bless.db.

Selector notes:
  The Bless portal is a React SPA at https://www.lularoebless.com.
  If selectors break after a portal update, inspect the live page and
  update the _SELECTORS dict below — no other code needs to change.
"""

import asyncio
import binascii
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from credential_manager import get_credentials, PLATFORM_BLESS

logger = logging.getLogger(__name__)

PORTAL_URL = "https://www.lularoebless.com"
SESSION_FILE = Path("session_cache/bless_session.json")

# Update these selectors if the portal's markup changes.
_SELECTORS = {
    # Login page
    "login_email":    'input[type="email"], input[name="email"], input[placeholder*="email" i]',
    "login_password": 'input[type="password"]',
    "login_submit":   'button[type="submit"]',
    "login_success":  '[data-testid="dashboard"], .dashboard, nav.main-nav',

    # Navigation links — match href or text
    "nav_inventory":       'a[href*="inventory"]',
    "nav_orders":          'a[href*="orders"]:not([href*="purchase"])',
    "nav_purchase_orders": 'a[href*="purchase"]',
    "nav_customers":       'a[href*="customer"]',

    # Table pagination
    "next_page": 'button[aria-label*="next" i], a[aria-label*="next" i], button:has-text("Next")',

    # Inventory table
    "inventory_rows":    'table tbody tr, [data-testid="inventory-row"]',
    "inv_sku":           '[data-col="sku"], td:nth-child(1)',
    "inv_name":          '[data-col="name"], td:nth-child(2)',
    "inv_style":         '[data-col="style"], td:nth-child(3)',
    "inv_size":          '[data-col="size"], td:nth-child(4)',
    "inv_price":         '[data-col="price"], td:nth-child(5)',
    "inv_quantity":      '[data-col="quantity"], td:nth-child(6)',

    # Retail orders table
    "order_rows":        'table tbody tr, [data-testid="order-row"]',
    "ord_number":        '[data-col="order-number"], td:nth-child(1)',
    "ord_email":         '[data-col="email"], td:nth-child(2)',
    "ord_date":          '[data-col="date"], td:nth-child(3)',
    "ord_total":         '[data-col="total"], td:nth-child(4)',
    "ord_pieces":        '[data-col="pieces"], td:nth-child(5)',

    # Purchase orders table
    "po_rows":           'table tbody tr, [data-testid="po-row"]',
    "po_number":         '[data-col="po-number"], td:nth-child(1)',
    "po_date":           '[data-col="date"], td:nth-child(2)',
    "po_total":          '[data-col="total"], td:nth-child(3)',

    # Customers table
    "customer_rows":     'table tbody tr, [data-testid="customer-row"]',
    "cust_name":         '[data-col="name"], td:nth-child(1)',
    "cust_email":        '[data-col="email"], td:nth-child(2)',
    "cust_phone":        '[data-col="phone"], td:nth-child(3)',
}


class AuthenticationError(Exception):
    pass


class BlessScraper:
    def __init__(self, db_path):
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self):
        creds = get_credentials(self.db_path, PLATFORM_BLESS)
        if not creds:
            logger.warning("No Bless credentials found. Visit /settings/credentials to save them.")
            return {"status": "no_credentials"}

        username, password = creds
        SESSION_FILE.parent.mkdir(exist_ok=True)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await self._load_session(browser)
            page = await context.new_page()

            try:
                if not await self._session_valid(page):
                    await self._login(page, username, password)
                    await self._save_session(context)

                results = {
                    "inventory":       await self._scrape_inventory(page),
                    "retail_orders":   await self._scrape_retail_orders(page),
                    "purchase_orders": await self._scrape_purchase_orders(page),
                    "customers":       await self._scrape_customers(page),
                    "scraped_at":      datetime.now(timezone.utc).isoformat(),
                }
                self._write_sync_log(results)
                logger.info("Bless scrape complete: %s", results)
                return results

            except AuthenticationError:
                # Session was bad and login failed — clear cached session
                if SESSION_FILE.exists():
                    SESSION_FILE.unlink()
                raise
            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    async def _load_session(self, browser):
        if SESSION_FILE.exists():
            try:
                storage = json.loads(SESSION_FILE.read_text())
                return await browser.new_context(storage_state=storage)
            except Exception:
                pass
        return await browser.new_context()

    async def _save_session(self, context):
        storage = await context.storage_state()
        SESSION_FILE.write_text(json.dumps(storage))

    async def _session_valid(self, page):
        await page.goto(PORTAL_URL, timeout=30_000)
        try:
            await page.wait_for_selector(_SELECTORS["login_success"], timeout=5_000)
            return True
        except PWTimeout:
            return False

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def _login(self, page, username, password):
        await page.goto(f"{PORTAL_URL}/login", timeout=30_000)
        await page.wait_for_selector(_SELECTORS["login_email"], timeout=15_000)
        await page.fill(_SELECTORS["login_email"], username)
        await page.fill(_SELECTORS["login_password"], password)
        await page.click(_SELECTORS["login_submit"])

        try:
            await page.wait_for_selector(_SELECTORS["login_success"], timeout=15_000)
        except PWTimeout:
            raise AuthenticationError(
                "Login failed — check credentials or the portal may have changed its layout."
            )
        logger.info("Logged in to Bless portal as %s", username)

    # ------------------------------------------------------------------
    # Generic pagination helper
    # ------------------------------------------------------------------

    async def _each_row(self, page, url, row_selector):
        """Navigate to url, yield rows from every page of results."""
        await page.goto(url, timeout=30_000)
        while True:
            await page.wait_for_load_state("networkidle", timeout=20_000)
            rows = await page.query_selector_all(row_selector)
            for row in rows:
                yield row

            next_btn = await page.query_selector(_SELECTORS["next_page"])
            if not next_btn:
                break
            is_disabled = await next_btn.get_attribute("disabled")
            if is_disabled is not None:
                break
            await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=20_000)

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    async def _scrape_inventory(self, page):
        conn = sqlite3.connect(self.db_path)
        count = 0
        try:
            async for row in self._each_row(page, f"{PORTAL_URL}/inventory", _SELECTORS["inventory_rows"]):
                sku      = await self._cell_text(row, _SELECTORS["inv_sku"])
                name     = await self._cell_text(row, _SELECTORS["inv_name"])
                style    = await self._cell_text(row, _SELECTORS["inv_style"])
                size     = await self._cell_text(row, _SELECTORS["inv_size"])
                price    = _parse_float(await self._cell_text(row, _SELECTORS["inv_price"]))
                quantity = _parse_int(await self._cell_text(row, _SELECTORS["inv_quantity"]))

                if not sku or not name:
                    continue

                _upsert_product(conn, sku, name, style, size, price)
                _upsert_inventory_snapshot(conn, name, quantity)
                count += 1
            conn.commit()
        finally:
            conn.close()

        logger.info("Scraped %d inventory rows", count)
        return count

    # ------------------------------------------------------------------
    # Retail orders
    # ------------------------------------------------------------------

    async def _scrape_retail_orders(self, page):
        conn = sqlite3.connect(self.db_path)
        count = 0
        try:
            async for row in self._each_row(page, f"{PORTAL_URL}/orders", _SELECTORS["order_rows"]):
                order_num = await self._cell_text(row, _SELECTORS["ord_number"])
                email     = await self._cell_text(row, _SELECTORS["ord_email"])
                date      = await self._cell_text(row, _SELECTORS["ord_date"])
                total     = _parse_float(await self._cell_text(row, _SELECTORS["ord_total"]))
                pieces    = _parse_float(await self._cell_text(row, _SELECTORS["ord_pieces"]))

                if not order_num:
                    continue

                _upsert_order(conn, order_num, email, date, total, pieces, "RETAIL")
                count += 1
            conn.commit()
        finally:
            conn.close()

        logger.info("Scraped %d retail orders", count)
        return count

    # ------------------------------------------------------------------
    # Purchase orders
    # ------------------------------------------------------------------

    async def _scrape_purchase_orders(self, page):
        conn = sqlite3.connect(self.db_path)
        count = 0
        try:
            async for row in self._each_row(page, f"{PORTAL_URL}/purchase-orders", _SELECTORS["po_rows"]):
                po_num = await self._cell_text(row, _SELECTORS["po_number"])
                date   = await self._cell_text(row, _SELECTORS["po_date"])
                total  = _parse_float(await self._cell_text(row, _SELECTORS["po_total"]))

                if not po_num:
                    continue

                _upsert_purchase_order(conn, po_num, date, total)
                count += 1
            conn.commit()
        finally:
            conn.close()

        logger.info("Scraped %d purchase orders", count)
        return count

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    async def _scrape_customers(self, page):
        conn = sqlite3.connect(self.db_path)
        count = 0
        try:
            async for row in self._each_row(page, f"{PORTAL_URL}/customers", _SELECTORS["customer_rows"]):
                name  = await self._cell_text(row, _SELECTORS["cust_name"])
                email = await self._cell_text(row, _SELECTORS["cust_email"])
                phone = await self._cell_text(row, _SELECTORS["cust_phone"])

                if not email:
                    continue

                _upsert_customer(conn, name or email, email, phone)
                count += 1
            conn.commit()
        finally:
            conn.close()

        logger.info("Scraped %d customers", count)
        return count

    # ------------------------------------------------------------------
    # Sync log
    # ------------------------------------------------------------------

    def _write_sync_log(self, results):
        conn = sqlite3.connect(self.db_path)
        try:
            synced_at = results["scraped_at"]
            for section, count in results.items():
                if section in ("scraped_at", "status"):
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO SyncLog (TableName, LastSyncedAt, RowsSynced) VALUES (?,?,?)",
                    (f"bless_scrape_{section}", synced_at, count if isinstance(count, int) else -1),
                )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    async def _cell_text(row, selector):
        el = await row.query_selector(selector)
        if not el:
            return ""
        return (await el.inner_text()).strip()


# ------------------------------------------------------------------
# DB upsert helpers (direct SQL, matching existing schema)
# ------------------------------------------------------------------

def _new_id():
    return binascii.b2a_hex(os.urandom(12)).decode()


def _upsert_product(conn, sku, name, style, size, price):
    existing = conn.execute(
        "SELECT ProductID FROM Products WHERE ProductSKU = ?", (sku,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE Products SET ProductName=?, ProductStyle=?, ProductSize=?, UnitPrice=?, InvProductName=? "
            "WHERE ProductSKU=?",
            (name, style or "", size or "", price or 0.0, name, sku),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO Products "
            "(ProductID, ProductSKU, ProductName, ProductStyle, ProductSize, UnitPrice, InvProductName) "
            "VALUES (?,?,?,?,?,?,?)",
            (_new_id(), sku, name, style or "", size or "", price or 0.0, name),
        )


def _upsert_inventory_snapshot(conn, product_name, quantity):
    """Replace the current MANUAL_ADJUSTMENT snapshot for this product."""
    snapshot_order = f"BLESS_SNAPSHOT_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    existing = conn.execute(
        "SELECT LedgerID FROM InventoryLedger WHERE ProductName=? AND EventType='MANUAL_ADJUSTMENT' AND OrderNumber=?",
        (product_name, snapshot_order),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE InventoryLedger SET Delta=?, EventDate=? WHERE LedgerID=?",
            (quantity, datetime.now(timezone.utc).isoformat(), existing[0]),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO InventoryLedger (LedgerID, ProductName, Delta, EventType, OrderNumber, EventDate) "
            "VALUES (?,?,?,?,?,?)",
            (_new_id(), product_name, quantity, "MANUAL_ADJUSTMENT", snapshot_order,
             datetime.now(timezone.utc).isoformat()),
        )


def _upsert_order(conn, order_num, email, date, total, pieces, order_type):
    existing = conn.execute(
        "SELECT OrderID FROM Orders WHERE OrderNumber=?", (order_num,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE Orders SET PaidTotal=?, PaidPieces=?, PaidDate=? WHERE OrderNumber=?",
            (total, pieces, date, order_num),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO Orders "
            "(OrderID, OrderNumber, OrderPopUp, OrderEmail, InvoiceDate, "
            " InvSubtotal, InvTaxes, InvShipping, InvShippingTaxes, InvDiscount, "
            " InvTotal, InvPieces, PaidDate, PaidSubtotal, PaidShipping, PaidTaxes, "
            " PaidShippingTaxes, PaidDiscount, PaidTotal, PaidPieces, OrderType) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_new_id(), order_num, "", email or "", date or "", 0, 0, 0, 0, 0,
             total or 0, pieces or 0, date, 0, 0, 0, 0, 0, total or 0, pieces or 0,
             order_type),
        )


def _upsert_purchase_order(conn, po_num, date, total):
    existing = conn.execute(
        "SELECT OrderID FROM PurchaseOrders WHERE OrderNumber=?", (po_num,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT OR IGNORE INTO PurchaseOrders "
            "(OrderID, OrderNumber, OrderEmail, OrderDate, Subtotal, Shipping, Taxes, Total, Pieces) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (_new_id(), po_num, "", date or "", 0, 0, 0, total or 0, 0),
        )


def _upsert_customer(conn, name, email, phone):
    existing = conn.execute(
        "SELECT CustomerID FROM CUSTOMERS WHERE CustomerEmail=?", (email,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT OR IGNORE INTO CUSTOMERS (CustomerID, CustomerEmail, CustomerName, CustomerType, CustomerPhone) "
            "VALUES (?,?,?,?,?)",
            (_new_id(), email, name, "RETAIL", phone or None),
        )


# ------------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------------

def _parse_float(text):
    if not text:
        return 0.0
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_int(text):
    if not text:
        return 0
    try:
        return int(text.strip())
    except ValueError:
        return 0


# ------------------------------------------------------------------
# CLI entry point for manual runs / testing
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app/bless.db"
    result = asyncio.run(BlessScraper(db_path).run())
    print(json.dumps(result, indent=2))
