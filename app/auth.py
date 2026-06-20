import binascii
import logging
import os
import secrets
from functools import wraps
from urllib.parse import urlencode

from flask import Blueprint, redirect, url_for, session, request
import requests as req

logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

_AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
_TOKEN_URI = 'https://oauth2.googleapis.com/token'
_USERINFO_URI = 'https://www.googleapis.com/oauth2/v3/userinfo'

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly',
]


@auth.route('/login')
def login():
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    params = {
        'client_id': os.environ['GOOGLE_CLIENT_ID'],
        'redirect_uri': os.environ['OAUTH_REDIRECT_URI'],
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent',
    }
    return redirect(f'{_AUTH_URI}?{urlencode(params)}')


@auth.route('/oauth/callback')
def oauth_callback():
    import data_management
    from app.db import get_conn

    state = request.args.get('state')
    if state != session.pop('oauth_state', None):
        return 'State mismatch — please try logging in again.', 400

    code = request.args.get('code')
    token_resp = req.post(_TOKEN_URI, data={
        'code': code,
        'client_id': os.environ['GOOGLE_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
        'redirect_uri': os.environ['OAUTH_REDIRECT_URI'],
        'grant_type': 'authorization_code',
    })
    token_data = token_resp.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')

    if not access_token:
        logger.error('Token exchange failed: %s', token_data)
        return f'Token exchange failed: {token_data.get("error_description", token_data)}', 500

    user_info = req.get(
        _USERINFO_URI,
        headers={'Authorization': f'Bearer {access_token}'},
    ).json()

    email = user_info.get('email', '')
    name = user_info.get('name', email)

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
