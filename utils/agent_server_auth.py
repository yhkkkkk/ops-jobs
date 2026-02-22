import hashlib
import hmac
from urllib.parse import urlparse


def compute_agent_server_hmac(secret: str, method: str, url: str, ts: str, body: bytes) -> str:
    """
    Compute HMAC signature for agent-server requests.

    message = timestamp + "\n" + method + "\n" + path + "\n" + body
    path is the URL path without query string.
    """
    parsed = urlparse(url)
    path = parsed.path or "/"

    mac = hmac.new(secret.encode("utf-8"), digestmod=hashlib.sha256)
    mac.update(ts.encode("utf-8"))
    mac.update(b"\n")
    mac.update(method.upper().encode("utf-8"))
    mac.update(b"\n")
    mac.update(path.encode("utf-8"))
    mac.update(b"\n")
    mac.update(body)
    return mac.hexdigest()
