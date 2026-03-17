"""
Google OAuth2 Authentication Handler
Handles OAuth code exchange, token generation, and validation
"""

import logging
import os
import json
import jwt
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

class GoogleOAuth:
    def __init__(self, client_id, client_secret, redirect_uri):
        """Initialize Google OAuth client"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_endpoint = "https://oauth2.googleapis.com/token"
        self.userinfo_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
        self.jwt_secret = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")

    def get_auth_endpoints(self):
        """Return client_id and configuration for frontend OAuth"""
        return {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "scope": "openid email profile"
        }

    def exchange_code_for_token(self, auth_code):
        """
        Exchange auth code for access token.
        Returns: (access_token, user_info) on success, (None, None) on failure
        """
        try:
            response = requests.post(self.token_endpoint, data={
                "code": auth_code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code"
            })

            if response.status_code != 200:
                log.warning(f"Token exchange failed: {response.text}")
                return None, None

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                return None, None

            # Get user info
            user_info = self.get_user_info(access_token)
            return access_token, user_info

        except Exception as e:
            log.error(f"Error exchanging code: {e}")
            return None, None

    def get_user_info(self, access_token):
        """
        Fetch user profile info from Google.
        Returns: dict with email, name, picture, id
        """
        try:
            response = requests.get(
                self.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return {
                "google_id": data.get("id"),
                "email": data.get("email"),
                "name": data.get("name", "Manager"),
                "picture": data.get("picture"),
            }

        except Exception as e:
            log.error(f"Error fetching user info: {e}")
            return None

    def verify_google_credential(self, credential):
        """
        Verify a Google One-Tap / Sign-In Button credential (ID token JWT).
        Uses Google's tokeninfo endpoint for verification.
        Returns: dict with google_id, email, name, picture on success, None on failure
        """
        try:
            response = requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
            )
            if response.status_code != 200:
                log.warning(f"Credential verification failed: {response.text}")
                return None

            data = response.json()

            # Verify audience matches our client_id
            if data.get("aud") != self.client_id:
                log.warning(f"Credential audience mismatch: {data.get('aud')} != {self.client_id}")
                return None

            return {
                "google_id": data.get("sub"),
                "email": data.get("email"),
                "name": data.get("name", "Manager"),
                "picture": data.get("picture"),
            }

        except Exception as e:
            log.error(f"Error verifying credential: {e}")
            return None

    def generate_auth_token(self, manager_id, google_id):
        """
        Generate JWT token for session.
        Token expires in 30 days.
        """
        payload = {
            "manager_id": manager_id,
            "google_id": google_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=30)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_auth_token(self, token):
        """
        Verify JWT token and extract manager_id.
        Returns: manager_id on success, None on failure
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload.get("manager_id"), payload.get("google_id")
        except jwt.ExpiredSignatureError:
            log.warning("Token expired")
            return None, None
        except jwt.InvalidTokenError:
            log.warning("Invalid token")
            return None, None
        except Exception as e:
            log.error(f"Error verifying token: {e}")
            return None, None


def init_oauth():
    """Initialize OAuth client from environment variables"""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    domain = os.getenv("DOMAIN", "localhost")
    http_port = os.getenv("HTTP_PORT", "8080")
    default_redirect = f"http://{domain}:{http_port}/auth/callback"
    redirect_uri = os.getenv("REDIRECT_URI", default_redirect)

    if not client_id or not client_secret:
        raise ValueError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in environment. "
            "Create a .env file with these values."
        )

    return GoogleOAuth(client_id, client_secret, redirect_uri)


