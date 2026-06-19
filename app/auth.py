import os
import binascii
import logging
from functools import wraps

from flask import Blueprint, redirect, url_for, session, request, current_app
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
]


def _flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ['GOOGLE_CLIENT_ID'],
                "client_secret": os.environ['GOOGLE_CLIENT_SECRET'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [os.environ['OAUTH_REDIRECT_URI']],
            }
        },
        scopes=SCOPES,
        redirect_uri=os.environ['OAUTH_REDIRECT_URI'],
    )


@auth.route('/login')
def login():
    flow = _flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    session['oauth_state'] = state
    return redirect(auth_url)


@auth.route('/oauth/callback')
def oauth_callback():
    import data_management
    from app.db import get_conn
    import requests as req

    flow = _flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    user_info_resp = req.get(
        'https://www.googleapis.com/oauth2/v3/userinfo',
        headers={'Authorization': f'Bearer {credentials.token}'},
    )
    user_info = user_info_resp.json()

    email = user_info.get('email', '')
    name = user_info.get('name', email)
    refresh_token = credentials.refresh_token

    conn = get_conn()
    try:
        tmp_id = binascii.b2a_hex(os.urandom(12)).decode()
        user_id = data_management.upsert_user(conn, tmp_id, email, name, refresh_token)
    finally:
        conn.close()

    session['user_id'] = user_id
    session['user_email'] = email
    session['user_name'] = name

    return redirect(url_for('dashboard'))


@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
