"""Safe Cloudflare Workers AI Token Verification Utility.

Verifies Cloudflare API Token validity against:
GET https://api.cloudflare.com/client/v4/user/tokens/verify

Security Guarantees:
1. Loads credentials strictly from local environment (.env).
2. Never prints, logs, or exposes raw API tokens or account secrets.
3. Redacts all sensitive strings in console outputs and exception messages.
4. Validates placeholders before attempting network requests.
"""

import json
import os
from pathlib import Path
import sys
from typing import Any, Optional
import urllib.error
import urllib.request

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import config to ensure .env is automatically loaded into os.environ
import benchmark.config  # noqa: F401


VERIFY_ENDPOINT = "https://api.cloudflare.com/client/v4/user/tokens/verify"
PLACEHOLDER_TOKEN = "paste_your_new_token_here"
PLACEHOLDER_ACCOUNT = "your_cloudflare_account_id"


def redact_secret(secret: Optional[str], show_prefix: int = 3, show_suffix: int = 3) -> str:
    """Safely redact sensitive tokens, preserving only small hints if valid."""
    if not secret:
        return "[NOT SET]"
    s = secret.strip()
    if s == PLACEHOLDER_TOKEN or s == PLACEHOLDER_ACCOUNT:
        return "[PLACEHOLDER - NOT CONFIGURED]"
    if len(s) <= (show_prefix + show_suffix + 2):
        return "[REDACTED - TOO SHORT]"
    return f"{s[:show_prefix]}...{s[-show_suffix:]} ({len(s)} chars)"


def check_local_env() -> dict[str, Any]:
    """Inspect local environment variables without making any network calls."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()

    is_token_placeholder = (token == PLACEHOLDER_TOKEN or not token)
    is_account_placeholder = (account_id == PLACEHOLDER_ACCOUNT or not account_id)

    return {
        "token_present": bool(token) and not is_token_placeholder,
        "token_is_placeholder": is_token_placeholder,
        "account_id_present": bool(account_id) and not is_account_placeholder,
        "account_id_is_placeholder": is_account_placeholder,
        "token_redacted": redact_secret(token),
        "account_id_redacted": redact_secret(account_id, show_prefix=4, show_suffix=4),
    }


def verify_cloudflare_token(
    token: Optional[str] = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Execute safe verification against Cloudflare's token verification endpoint.

    HTTP Request:
      GET https://api.cloudflare.com/client/v4/user/tokens/verify
      Authorization: Bearer <CLOUDFLARE_API_TOKEN>

    Returns:
      dict with status, success, message, and safe redacted diagnostics.
    """
    raw_token = token or os.environ.get("CLOUDFLARE_API_TOKEN", "")
    raw_token = raw_token.strip()

    if not raw_token or raw_token == PLACEHOLDER_TOKEN:
        return {
            "success": False,
            "status": "UNCONFIGURED",
            "message": "CLOUDFLARE_API_TOKEN is not configured or still set to placeholder in .env.",
            "token_preview": redact_secret(raw_token),
        }

    headers = {
        "Authorization": f"Bearer {raw_token}",
        "User-Agent": "Proofline-Benchmark-Verification/1.0",
        "Accept": "application/json",
    }

    req = urllib.request.Request(VERIFY_ENDPOINT, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            body_bytes = resp.read()
            data = json.loads(body_bytes.decode("utf-8"))

            success = data.get("success", False)
            result = data.get("result", {})
            token_status = result.get("status", "unknown")
            messages = data.get("messages", [])
            msg_text = messages[0].get("message", "Token verified.") if messages else "No details returned."

            return {
                "success": success and (token_status == "active"),
                "http_status": status_code,
                "token_status": token_status,
                "token_id": result.get("id", "N/A"),
                "message": msg_text,
                "token_preview": redact_secret(raw_token),
            }

    except urllib.error.HTTPError as e:
        safe_reason = str(e.reason)
        # Redact any accidental token reflections in error body
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            err_data = json.loads(err_body)
            err_msgs = [err.get("message", "") for err in err_data.get("errors", [])]
            detail = "; ".join(err_msgs) if err_msgs else safe_reason
        except Exception:
            detail = safe_reason

        # Ensure raw token is scrubbed from detail
        if raw_token in detail:
            detail = detail.replace(raw_token, "[REDACTED_TOKEN]")

        return {
            "success": False,
            "http_status": e.code,
            "token_status": "HTTP_ERROR",
            "message": f"Cloudflare API rejected token (HTTP {e.code}): {detail}",
            "token_preview": redact_secret(raw_token),
        }

    except urllib.error.URLError as e:
        safe_err = str(e.reason)
        if raw_token in safe_err:
            safe_err = safe_err.replace(raw_token, "[REDACTED_TOKEN]")
        return {
            "success": False,
            "http_status": 0,
            "token_status": "NETWORK_ERROR",
            "message": f"Network transport error connecting to Cloudflare: {safe_err}",
            "token_preview": redact_secret(raw_token),
        }

    except Exception as e:
        safe_exc = str(e)
        if raw_token in safe_exc:
            safe_exc = safe_exc.replace(raw_token, "[REDACTED_TOKEN]")
        return {
            "success": False,
            "http_status": 0,
            "token_status": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during verification: {safe_exc}",
            "token_preview": redact_secret(raw_token),
        }


def main() -> int:
    """CLI runner for Cloudflare token verification."""
    print("\n" + "=" * 70)
    print("CLOUDFLARE WORKERS AI TOKEN VERIFICATION (SAFE REDACTION)")
    print("=" * 70)

    # 1. Local environment inspection
    env_info = check_local_env()
    print(f"Cloudflare Account ID:  {env_info['account_id_redacted']}")
    print(f"Cloudflare API Token:   {env_info['token_redacted']}")
    print("-" * 70)

    if env_info["token_is_placeholder"]:
        print("[STATUS: PENDING CONFIGURATION]")
        print("Please edit .env in the project root and enter your real credentials:")
        print("  CLOUDFLARE_ACCOUNT_ID=<your-account-id>")
        print("  CLOUDFLARE_API_TOKEN=<your-token>")
        print("\nVerification aborted (Zero network calls made).")
        print("=" * 70 + "\n")
        return 1

    # Check for dry-run or inspection only
    if "--check-only" in sys.argv:
        print("[CHECK ONLY] Local environment verified. No network call requested.")
        print("=" * 70 + "\n")
        return 0

    print("Verifying token with Cloudflare API endpoint...")
    res = verify_cloudflare_token()

    print(f"HTTP Status:            {res.get('http_status', 'N/A')}")
    print(f"Token Status:           {res.get('token_status', 'UNKNOWN')}")
    print(f"Message:                {res.get('message')}")
    print("-" * 70)

    if res["success"]:
        print("[SUCCESS] Cloudflare API Token is ACTIVE and valid.")
        print("=" * 70 + "\n")
        return 0
    else:
        print("[FAILURE] Token verification failed. Please check your credentials in .env.")
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
