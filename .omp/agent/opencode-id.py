#!/usr/bin/env python3
"""Mint a structurally-valid OpenCode client id (ses_/msg_ + 12 hex + 14 base62)."""
import secrets
import sys
import time

BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def main() -> None:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "ses"
    # Inverted-timestamp hex like the official client (time value is not validated upstream).
    value = (~((int(time.time() * 1000) & 0xFFFFFFFFFFFF) * 0x1000 + 1)) & 0xFFFFFFFFFFFF
    hex12 = format(value, "012x")
    rand14 = "".join(secrets.choice(BASE62) for _ in range(14))
    print(f"{prefix}_{hex12}{rand14}")


if __name__ == "__main__":
    main()
