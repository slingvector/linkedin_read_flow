"""
read_flow/auth.py
---------------------------
Auth for the read account.

Priority:
  1. LINKEDIN_LI_AT cookie   — preferred, password never touched
  2. LINKEDIN_EMAIL + LINKEDIN_PASSWORD — fallback

.env keys:
    LINKEDIN_LI_AT=AQEDATd2...

    # fallback only if no cookie:
    LINKEDIN_EMAIL=you@example.com
    LINKEDIN_PASSWORD=yourpassword
"""

import logging
import os

from dotenv import load_dotenv
from linkedin_api import Linkedin
from linkedin_api.client import ChallengeException, UnauthorizedException

from .clients.voyager_client import VoyagerClient

load_dotenv()
logger = logging.getLogger(__name__)


def build_voyager_client() -> VoyagerClient:
    """
    Authenticates with LinkedIn and returns a VoyagerClient.
    This is the only place linkedin_api.Linkedin is instantiated
    outside of voyager_client.py.

    Raises SystemExit with a clear message on auth failure —
    auth errors are unrecoverable at startup.
    """
    li_at = os.environ.get("LINKEDIN_LI_AT", "").strip()
    email = os.environ.get("LINKEDIN_EMAIL", "").strip()
    password = os.environ.get("LINKEDIN_PASSWORD", "").strip()

    api: Linkedin | None = None

    # 1. Cookie auth — preferred
    if li_at:
        logger.info(
            "Auth method: li_at cookie",
            extra={"layer": "auth", "method": "cookie"},
        )
        try:
            api = Linkedin("", "", cookies={"li_at": li_at})
        except Exception as exc:
            logger.warning(
                "Cookie auth failed, trying email/password fallback",
                extra={"layer": "auth", "error": str(exc)},
            )
            api = None

    # 2. Email/password fallback
    if api is None:
        if not email or not password:
            raise SystemExit(
                "No valid LinkedIn credentials found.\n"
                "Add to your .env file:\n\n"
                "  # Option 1 — recommended\n"
                "  LINKEDIN_LI_AT=AQEDATd2...\n\n"
                "  # Option 2 — fallback\n"
                "  LINKEDIN_EMAIL=you@example.com\n"
                "  LINKEDIN_PASSWORD=yourpassword\n\n"
                "Get li_at: Chrome DevTools → Application → Cookies → www.linkedin.com"
            )
        logger.info(
            "Auth method: email/password",
            extra={"layer": "auth", "method": "password", "email": email},
        )
        try:
            api = Linkedin(email, password)
        except ChallengeException:
            raise SystemExit(
                "LinkedIn triggered a 2FA/CAPTCHA challenge.\n"
                "Log in manually in a browser, complete the challenge, then retry.\n"
                "Tip: grab the fresh li_at cookie after solving and use that instead."
            )
        except UnauthorizedException:
            raise SystemExit(
                "Bad credentials — check LINKEDIN_EMAIL / LINKEDIN_PASSWORD in .env"
            )

    logger.info("LinkedIn auth successful", extra={"layer": "auth"})
    return VoyagerClient(api)
