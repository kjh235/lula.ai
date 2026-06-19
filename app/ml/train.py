"""Offline training script for the recommendation models.

Usage:
    python -m app.ml.train              # train and save artifacts
    python -m app.ml.train --eval       # train with holdout evaluation
    python -m app.ml.train --seed       # generate implicit feedback from repeat purchases
"""

import argparse
import logging
import os
import pickle
import sqlite3
import binascii
from collections import defaultdict
from datetime import datetime

from app.sizing import classify_family, normalize_size
from app.ml.similarity import build_similarity_index
from app.ml.size_model import SizeFitModel

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bless.db')
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artifacts')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_products(conn):
    rows = conn.execute(
        "SELECT ProductSKU, ProductName, ProductStyle, ProductSize, "
        "UnitPrice, InvProductName, SizingFamily, SizeNormalized FROM Products"
    ).fetchall()
    return [dict(r) for r in rows]


def load_order_items(conn):
    rows = conn.execute(
        "SELECT oi.OrderNumber, oi.ProductName, p.ProductSKU "
        "FROM OrderItems oi "
        "LEFT JOIN Products p ON p.InvProductName = oi.ProductName"
    ).fetchall()
    return [dict(r) for r in rows]


def load_fit_feedback(conn):
    rows = conn.execute(
        "SELECT CustomerID, ProductSKU, SizePurchased, FitOutcome, Source "
        "FROM FitFeedback"
    ).fetchall()
    return [
        {
            'customer_id': r['CustomerID'],
            'product_sku': r['ProductSKU'],
            'size_purchased': r['SizePurchased'],
            'fit_outcome': r['FitOutcome'],
        }
        for r in rows
    ]


def seed_implicit_feedback(conn):
    """Generate implicit true_to_size feedback from repeat purchases."""
    rows = conn.execute(
        "SELECT c.CustomerID, p.ProductSKU, p.SizingFamily, p.SizeNormalized, "
        "COUNT(*) as cnt "
        "FROM Orders o "
        "JOIN OrderItems oi ON o.OrderNumber = oi.OrderNumber "
        "JOIN Products p ON p.InvProductName = oi.ProductName "
        "JOIN Customers c ON c.CustomerEmail = o.OrderEmail "
        "WHERE p.SizingFamily IS NOT NULL "
        "GROUP BY c.CustomerID, p.SizingFamily, p.SizeNormalized "
        "HAVING cnt >= 2"
    ).fetchall()

    cursor = conn.cursor()
    inserted = 0
    for r in rows:
        fid = binascii.b2a_hex(os.urandom(12)).decode()
        try:
            cursor.execute(
                "INSERT INTO FitFeedback VALUES (?, ?, ?, NULL, ?, 'true_to_size', 'implicit_repeat', ?)",
                (fid, r['CustomerID'], r['ProductSKU'], r['SizeNormalized'],
                 datetime.utcnow().isoformat())
            )
            inserted += 1
        except Exception:
            pass
    conn.commit()
    logger.info("Seeded %d implicit feedback records", inserted)
    return inserted


def train_similarity(products, order_items):
    logger.info("Training similarity model on %d products, %d order items...", len(products), len(order_items))
    index = build_similarity_index(products, order_items, alpha=0.6, top_k=20)
    logger.info("Similarity index built for %d products", len(index))
    return index


def train_size_models(feedback, products):
    product_families = {p['ProductSKU']: p.get('SizingFamily', 'clothing') for p in products}

    feedback_by_family = defaultdict(list)
    for rec in feedback:
        family = product_families.get(rec['product_sku'], 'clothing')
        feedback_by_family[family].append(rec)

    models = {}
    for family, records in feedback_by_family.items():
        logger.info("Training size model for '%s' with %d feedback records...", family, len(records))
        model = SizeFitModel()
        model.fit(records, family)
        models[family] = model
        n_customers = len(model.customer_size)
        n_products = len(model.product_offset)
        logger.info("  -> %d customers, %d products", n_customers, n_products)

    return models


def evaluate_size_models(feedback, products, holdout_ratio=0.1):
    import random
    product_families = {p['ProductSKU']: p.get('SizingFamily', 'clothing') for p in products}

    feedback_by_family = defaultdict(list)
    for rec in feedback:
        family = product_families.get(rec['product_sku'], 'clothing')
        feedback_by_family[family].append(rec)

    for family, records in feedback_by_family.items():
        if len(records) < 10:
            logger.info("'%s': too few records (%d) for evaluation", family, len(records))
            continue

        random.shuffle(records)
        split = max(1, int(len(records) * holdout_ratio))
        test = records[:split]
        train = records[split:]

        model = SizeFitModel()
        model.fit(train, family)

        correct = 0
        total = 0
        for rec in test:
            pred_size, _ = model.predict_best_size(rec['customer_id'], rec['product_sku'], family)
            if pred_size is None:
                continue
            actual = normalize_size(rec['size_purchased'])
            if rec['fit_outcome'] == 'true_to_size' and pred_size == actual:
                correct += 1
            total += 1

        if total > 0:
            acc = correct / total
            logger.info("'%s': accuracy %.2f%% (%d/%d on holdout)", family, acc * 100, correct, total)
        else:
            logger.info("'%s': no testable holdout records", family)


def main():
    parser = argparse.ArgumentParser(description='Train recommendation models')
    parser.add_argument('--eval', action='store_true', help='Run holdout evaluation')
    parser.add_argument('--seed', action='store_true', help='Seed implicit feedback from repeat purchases')
    args = parser.parse_args()

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    conn = get_conn()

    if args.seed:
        seed_implicit_feedback(conn)

    products = load_products(conn)
    order_items = load_order_items(conn)
    feedback = load_fit_feedback(conn)

    logger.info("Loaded %d products, %d order items, %d feedback records",
                len(products), len(order_items), len(feedback))

    sim_index = train_similarity(products, order_items)
    with open(os.path.join(ARTIFACTS_DIR, 'similarity.pkl'), 'wb') as f:
        pickle.dump(sim_index, f)
    logger.info("Saved similarity index to %s/similarity.pkl", ARTIFACTS_DIR)

    size_models = train_size_models(feedback, products)
    with open(os.path.join(ARTIFACTS_DIR, 'size_model.pkl'), 'wb') as f:
        pickle.dump(size_models, f)
    logger.info("Saved size models to %s/size_model.pkl", ARTIFACTS_DIR)

    if args.eval and feedback:
        logger.info("--- Holdout Evaluation ---")
        evaluate_size_models(feedback, products)

    conn.close()
    logger.info("Training complete.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    main()
