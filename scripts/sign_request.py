#!/usr/bin/env python3
"""Sign a request to the Valio front door with RFC 9421 HTTP Message Signatures (Ed25519).

  # 1. once: make a key pair; register the printed public entry in AGENT_SIGNING_KEYS on the server
  python3 scripts/sign_request.py generate --buyer lapland-kitchen --kid kitchen-1 --out agent-signing.key
  # 2. send a signed request (X-Agent-Key from the AGENT_KEY env var; neither secret is printed)
  AGENT_KEY=… python3 scripts/sign_request.py send --key agent-signing.key --kid kitchen-1 \\
      POST https://valio-front-door-api.onrender.com/api/orders '{"requested_date":"2026-11-16","lines":[…]}'

Needs the `cryptography` package (in backend/requirements.txt). The server side is backend/app/httpsig.py; the exact
signature base is documented there and in docs/STANDARDS.md.
"""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

COMPONENTS = ("@method", "@path", "content-digest")


def sign_headers(method: str, url: str, body: bytes, key: Ed25519PrivateKey, kid: str,
                 created: int | None = None, label: str = "sig1") -> dict[str, str]:
    """The three headers that make a request RFC 9421-signed: Content-Digest, Signature-Input, Signature."""
    digest = "sha-256=:" + base64.b64encode(hashlib.sha256(body).digest()).decode() + ":"
    params = ("(" + " ".join(f'"{c}"' for c in COMPONENTS) + ")"
              + f';created={int(time.time()) if created is None else created};keyid="{kid}";alg="ed25519"')
    values = {"@method": method.upper(), "@path": urlsplit(url).path or "/", "content-digest": digest}
    base = "\n".join([f'"{c}": {values[c]}' for c in COMPONENTS] + [f'"@signature-params": {params}']).encode()
    sig = base64.b64encode(key.sign(base)).decode()
    return {"Content-Digest": digest, "Signature-Input": f"{label}={params}", "Signature": f"{label}=:{sig}:"}


def generate(buyer: str, kid: str, out: Path) -> None:
    key = Ed25519PrivateKey.generate()
    out.write_text(base64.b64encode(key.private_bytes_raw()).decode() + "\n")
    out.chmod(0o600)
    pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    print(f"Private key written to {out} (keep it secret, never commit it).")
    print(f"Register on the server (public, safe to share):\n  AGENT_SIGNING_KEYS={buyer}:{kid}:{pub}")


def send(key_file: Path, kid: str, method: str, url: str, body: str) -> int:
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key_file.read_text().strip()))
    raw = body.encode()
    headers = {"Content-Type": "application/json", "X-Agent-Key": os.environ.get("AGENT_KEY", ""),
               "User-Agent": "front-door-signed-client/1", **sign_headers(method, url, raw, key, kid)}
    req = urllib.request.Request(url, data=raw, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status, out = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, out = e.code, e.read()
    print(f"HTTP {status}")
    try:
        print(json.dumps(json.loads(out), indent=2, ensure_ascii=False)[:4000])
    except ValueError:
        print(out[:2000].decode(errors="replace"))
    return 0 if status < 400 else 1


def main(argv: list[str]) -> int:
    def opt(name: str) -> str:
        return argv[argv.index(name) + 1]
    if argv[:1] == ["generate"]:
        generate(opt("--buyer"), opt("--kid"), Path(opt("--out")))
        return 0
    if argv[:1] == ["send"]:
        rest = [a for i, a in enumerate(argv[1:], 1) if not a.startswith("--") and not argv[i - 1].startswith("--")]
        method, url, body = (rest + ["{}"])[:3] if len(rest) >= 2 else (None, None, None)
        if not url:
            print(__doc__)
            return 2
        return send(Path(opt("--key")), opt("--kid"), method, url, body)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
