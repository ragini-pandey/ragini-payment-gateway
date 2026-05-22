"""Standalone receipt-side script: verify an incoming webhook signature.

Usage (drop into your own receiver):

    python scripts/verify_signature.py --secret whsec_... --header 't=...,v1=...' --body '{...}'

Returns exit code 0 on a valid signature, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys

from app.security.hmac_sign import verify


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--secret", required=True)
    p.add_argument("--header", required=True, help="X-Ragini-Signature value")
    p.add_argument("--body", required=True, help="Raw request body")
    p.add_argument("--tolerance", type=int, default=300)
    args = p.parse_args()
    ok = verify(args.secret, args.header, args.body.encode("utf-8"), tolerance_seconds=args.tolerance)
    print("VALID" if ok else "INVALID")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
