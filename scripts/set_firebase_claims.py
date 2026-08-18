#!/usr/bin/env python3
"""Grant Firebase custom claims for Neo Fabel operators.

Usage (from repo root, with GOOGLE_APPLICATION_CREDENTIALS set to an ADC
or service-account JSON file, or with FIREBASE_CREDENTIALS_PATH set):

  python scripts/set_firebase_claims.py --uid <FIREBASE_UID> --signal-admin
  python scripts/set_firebase_claims.py --email you@example.com --signal-admin --trading-admin

After setting claims the user must sign out and sign in again so the ID token
picks up signal_admin / trading_admin.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (".env.local", ".env"):
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, _, value = text.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Set Neo Fabel Firebase custom claims")
    parser.add_argument("--uid", help="Firebase Auth UID")
    parser.add_argument("--email", help="Look up UID by email")
    parser.add_argument("--signal-admin", action="store_true", help="Set signal_admin=true")
    parser.add_argument("--trading-admin", action="store_true", help="Set trading_admin=true")
    parser.add_argument("--clear-signal-admin", action="store_true", help="Remove signal_admin")
    parser.add_argument("--clear-trading-admin", action="store_true", help="Remove trading_admin")
    parser.add_argument("--show", action="store_true", help="Print current claims only")
    args = parser.parse_args()

    if not args.signal_admin and not args.trading_admin and not args.clear_signal_admin and not args.clear_trading_admin and not args.show:
        parser.error("pass --signal-admin and/or --trading-admin (or --show)")

    project_id = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("VITE_FIREBASE_PROJECT_ID")
    google_application_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    legacy_credentials_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    if not project_id:
        print("FIREBASE_PROJECT_ID is required", file=sys.stderr)
        return 2

    try:
        import firebase_admin
        from firebase_admin import auth, credentials
    except ImportError:
        print("Install firebase-admin: pip install firebase-admin", file=sys.stderr)
        return 2

    app_name = "neo-fabel-claims"
    try:
        firebase_admin.get_app(app_name)
    except ValueError:
        options = {"projectId": project_id}
        # Let the Google ADC resolver handle GOOGLE_APPLICATION_CREDENTIALS so
        # an ADC file from `gcloud auth application-default login` works just
        # as well as a service-account key without exposing one in the repo.
        if google_application_credentials:
            firebase_admin.initialize_app(credentials.ApplicationDefault(), options, name=app_name)
        elif legacy_credentials_path and Path(legacy_credentials_path).is_file():
            firebase_admin.initialize_app(credentials.Certificate(legacy_credentials_path), options, name=app_name)
        else:
            firebase_admin.initialize_app(credentials.ApplicationDefault(), options, name=app_name)

    if args.email and not args.uid:
        user_rec = auth.get_user_by_email(args.email, app=firebase_admin.get_app(app_name))
        uid = user_rec.uid
        print(f"Resolved {args.email} → uid={uid}")
    else:
        uid = args.uid
    if not uid:
        parser.error("--uid or --email is required")

    user = auth.get_user(uid, app=firebase_admin.get_app(app_name))
    claims = dict(user.custom_claims or {})
    print(f"Current claims for {uid}: {claims or '{}'}")

    if args.show and not (args.signal_admin or args.trading_admin or args.clear_signal_admin or args.clear_trading_admin):
        return 0

    if args.signal_admin:
        claims["signal_admin"] = True
    if args.clear_signal_admin:
        claims.pop("signal_admin", None)
    if args.trading_admin:
        claims["trading_admin"] = True
    if args.clear_trading_admin:
        claims.pop("trading_admin", None)

    auth.set_custom_user_claims(uid, claims, app=firebase_admin.get_app(app_name))
    refreshed = auth.get_user(uid, app=firebase_admin.get_app(app_name)).custom_claims or {}
    print(f"Updated claims: {refreshed}")
    print("Sign out and sign in again in the Neo Fabel UI so the ID token refreshes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
