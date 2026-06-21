import os
import logging
import binascii
from datetime import datetime

import stripe
from flask import Blueprint, jsonify, render_template, request, current_app, session

from app.db import get_conn
from app.auth import login_required

logger = logging.getLogger(__name__)

payments = Blueprint('payments', __name__)


def _stripe_keys():
    return current_app.config.get('STRIPE_KEYS', {})


@payments.route("/subscribe")
@login_required
def subscribe():
    keys = _stripe_keys()
    return render_template("subscribe.html", publishable_key=keys.get("publishable_key", ""))


@payments.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    keys = _stripe_keys()
    if not keys.get("secret_key"):
        return jsonify(error="Stripe is not configured"), 500

    user_id = session.get('user_id', '')
    user_email = session.get('user_email', '')

    try:
        checkout_session = stripe.checkout.Session.create(
            success_url=request.host_url + "success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.host_url + "cancel",
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": keys["price_id"], "quantity": 1}],
            metadata={"user_id": user_id},
            customer_email=user_email or None,
        )
        return jsonify({"sessionId": checkout_session["id"]})
    except Exception as e:
        logger.error("Stripe checkout error: %s", e)
        return jsonify(error=str(e)), 403


@payments.route("/success")
def success():
    if 'user_id' in session:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT Status FROM Subscriptions WHERE UserID = %s AND Status = 'active' LIMIT 1",
                (session['user_id'],),
            ).fetchone()
            if row:
                session['subscription_status'] = row['Status']
        finally:
            conn.close()
    return render_template("success.html")


@payments.route("/cancel")
def cancel():
    return render_template("cancel.html")


@payments.route("/webhook", methods=["POST"])
def stripe_webhook():
    keys = _stripe_keys()
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, keys.get("endpoint_secret", "")
        )
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    if event["type"] == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])
    elif event["type"] == "customer.subscription.updated":
        _handle_subscription_updated(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        _handle_subscription_deleted(event["data"]["object"])

    return "OK", 200


def _handle_checkout_completed(session_obj):
    sub_id = session_obj.get("subscription")
    customer_id = session_obj.get("customer")
    customer_email = session_obj.get("customer_details", {}).get("email", "")
    user_id = session_obj.get("metadata", {}).get("user_id")

    if not sub_id:
        logger.warning("checkout.session.completed with no subscription id")
        return

    conn = get_conn()
    try:
        sid = binascii.b2a_hex(os.urandom(12)).decode()
        conn.execute(
            "INSERT INTO Subscriptions "
            "(ID, UserID, StripeSubscriptionID, StripeCustomerID, CustomerEmail, Status, CreatedAt) "
            "VALUES (%s, %s, %s, %s, %s, 'active', %s) "
            "ON CONFLICT (StripeSubscriptionID) DO UPDATE SET "
            "UserID = EXCLUDED.UserID, "
            "StripeCustomerID = EXCLUDED.StripeCustomerID, "
            "CustomerEmail = EXCLUDED.CustomerEmail, "
            "Status = EXCLUDED.Status, "
            "CreatedAt = EXCLUDED.CreatedAt",
            (sid, user_id, sub_id, customer_id, customer_email,
             datetime.utcnow().isoformat()),
        )
        conn.commit()
        logger.info("Subscription %s saved for %s", sub_id, customer_email)
    finally:
        conn.close()


def _handle_subscription_updated(subscription):
    sub_id = subscription.get("id")
    status = subscription.get("status")

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE Subscriptions SET Status=%s WHERE StripeSubscriptionID=%s",
            (status, sub_id),
        )
        conn.commit()
    finally:
        conn.close()


def _handle_subscription_deleted(subscription):
    sub_id = subscription.get("id")

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE Subscriptions SET Status='canceled' WHERE StripeSubscriptionID=%s",
            (sub_id,),
        )
        conn.commit()
    finally:
        conn.close()


def load_stripe_config(app):
    keys = {
        "secret_key": os.environ.get("STRIPE_SECRET_KEY", ""),
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""),
        "price_id": os.environ.get("STRIPE_PRICE_ID", ""),
        "endpoint_secret": os.environ.get("STRIPE_ENDPOINT_SECRET", ""),
    }
    if not keys["secret_key"]:
        logger.warning("STRIPE_SECRET_KEY not set — Stripe features disabled")
        app.config['STRIPE_KEYS'] = {}
        return
    app.config['STRIPE_KEYS'] = keys
    stripe.api_key = keys["secret_key"]
