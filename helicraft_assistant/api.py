"""FastAPI integration. Model credentials stay on the server."""
import asyncio
import base64
from collections import defaultdict, deque
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlparse
from typing import List, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .core import ChatRequest, PROMPT_VERSION, VERSION, make_messages, validate_reply, ModelOutputError

LOGGER = logging.getLogger("uvicorn.error")

COOKIE = "helicraft_ai_session"
SESSION_SECONDS = 8 * 3600


def session_key():
    value = os.getenv("HELICRAFT_AI_SESSION_SECRET", "")
    return value.encode() if len(value) >= 32 else None


def issue_session(identity: str) -> Optional[str]:
    key = session_key()
    if key is None:
        return None
    subject = hmac.new(key, identity.encode(), hashlib.sha256).hexdigest()
    body = f"{subject}.{int(time.time()) + SESSION_SECONDS}.{secrets.token_hex(8)}"
    signature = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{body}.{signature}".encode()).decode()


def read_session(token: Optional[str]) -> Optional[str]:
    key = session_key()
    if not key or not token or len(token) > 512:
        return None
    try:
        subject, expiry, nonce, signature = base64.urlsafe_b64decode(token).decode().split(".")
        body = f"{subject}.{expiry}.{nonce}"
        expected = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        now = time.time()
        if not now < int(expiry) <= now + SESSION_SECONDS + 60:
            return None
        return subject
    except (ValueError, UnicodeError):
        return None


def login_response(payload: dict, identity: str):
    """Call only after the existing email verification and user lookup succeed."""
    response = JSONResponse(payload)
    token = issue_session(identity)
    if token:
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=os.getenv("HELICRAFT_AI_COOKIE_SECURE", "1") != "0",
                            samesite="strict", path="/")
    return response


def settings():
    endpoint = os.getenv("HELICRAFT_AI_BASE_URL", "https://api.deepseek.com").rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise ValueError("Model endpoint must be an HTTPS base URL")
    key = os.getenv("HELICRAFT_AI_API_KEY", "")
    model = os.getenv("HELICRAFT_AI_MODEL", "")
    if not key or not model or not session_key():
        raise ValueError("AI not configured")
    return endpoint, key, model


class Limits:
    """Bounded, per-process quotas; deployment uses one worker (see README)."""
    def __init__(self):
        self.users = defaultdict(deque)
        self.global_calls = deque()
        self.active = 0

    def reserve(self, subject: str):
        now = time.monotonic()
        for key, calls in list(self.users.items()):
            while calls and calls[0] < now - 3600:
                calls.popleft()
            if not calls:
                del self.users[key]
        while self.global_calls and self.global_calls[0] < now - 3600:
            self.global_calls.popleft()
        if self.active >= 2:
            raise HTTPException(429, "The assistant is busy. Please try again shortly.")
        quota = 30
        if len(self.global_calls) >= 200 or len(self.users) >= 10000 or len(self.users[subject]) >= quota:
            raise HTTPException(429, "The hourly assistant limit has been reached. Please try again later.")
        self.users[subject].append(now)
        self.global_calls.append(now)
        self.active += 1


async def provider_call(messages: List[dict], config: Tuple[str, str, str]) -> dict:
    endpoint, key, model = config
    payload = {"model": model, "messages": messages, "temperature": 0,
               "max_tokens": 1800, "response_format": {"type": "json_object"}, "stream": False}
    # V4 defaults to thinking mode; keep short parameter chats within this
    # assistant's output budget. Do not send vendor options to other providers.
    if urlparse(endpoint).hostname == "api.deepseek.com" and model in {
        "deepseek-flash", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp", "deepseek-v4-pro"
    }:
        payload["thinking"] = {"type": "disabled"}
    # No automatic retries: avoid duplicate charges after ambiguous failures.
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10), follow_redirects=False) as client:
        async with client.stream("POST", endpoint + "/chat/completions",
                                 headers={"Authorization": "Bearer " + key}, json=payload) as response:
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 128000:
                    raise ValueError("Model response too large")
    body = json.loads(content)
    choice = body["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Incomplete model response")
    return json.loads(choice["message"]["content"])


def parse_provider_response(content):
    """Separate transport-envelope, empty/truncated output, JSON and schema failures."""
    try:
        body = json.loads(content)
    except (ValueError, UnicodeError):
        raise ModelOutputError("MODEL_ENVELOPE_INVALID_JSON") from None
    try:
        choice = body["choices"][0]
        finish = choice.get("finish_reason")
        if finish != "stop":
            raise ModelOutputError("MODEL_OUTPUT_TRUNCATED" if finish == "length" else "MODEL_OUTPUT_INCOMPLETE")
        output = choice["message"]["content"]
    except ModelOutputError:
        raise
    except (TypeError, KeyError, IndexError, AttributeError):
        raise ModelOutputError("MODEL_ENVELOPE_INVALID_SHAPE") from None
    if output is None or (isinstance(output, str) and not output.strip()):
        raise ModelOutputError("MODEL_OUTPUT_EMPTY")
    if not isinstance(output, str):
        raise ModelOutputError("MODEL_OUTPUT_INVALID_CONTENT_TYPE")
    try:
        raw = json.loads(output)
    except ValueError:
        raise ModelOutputError("MODEL_OUTPUT_INVALID_JSON") from None
    if not isinstance(raw, dict):
        raise ModelOutputError("MODEL_OUTPUT_NOT_OBJECT")
    return raw


def output_error_response(error, request_id):
    # Fields are produced by the allowlisted classifier; never log raw exceptions,
    # request messages, provider responses, sessions, or configuration.
    LOGGER.warning("Jack output rejected request_id=%s code=%s fields=%s",
                   request_id, error.code, ",".join(error.fields) or "none")
    return JSONResponse({
        "status": "error",
        "detail": "The model returned an invalid suggestion. Your form is unchanged. Please rephrase your request.",
        "error_code": error.code, "error_fields": list(error.fields), "request_id": request_id,
    }, status_code=502, headers={"Cache-Control": "no-store", "X-HeliCraft-Request-ID": request_id})



def require_session(request):
    identity = read_session(request.cookies.get(COOKIE))
    if not identity:
        raise HTTPException(401, "Please log in to use the modeling workspace.")
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin', '').rstrip('/')
        expected = os.getenv('HELICRAFT_AI_PUBLIC_ORIGIN', str(request.base_url).rstrip('/')).rstrip('/')
        if origin != expected or request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(403, "Request origin does not match the modeling workspace.")
    return identity


def install(app):
    from release_info import RELEASE
    # Fail closed for all modeling API routes, including any added in future.
    public_paths = {'/api/auth/send_code', '/api/auth/login', '/api/auth/register',
                    '/api/assistant/status', '/api/release'}
    @app.middleware('http')
    async def modeling_auth(request, call_next):
        path = request.url.path.rstrip('/')
        if path.startswith('/api/') and path not in public_paths:
            try: require_session(request)
            except HTTPException as exc:
                return JSONResponse({'status': 'error', 'message': exc.detail}, status_code=exc.status_code)
        return await call_next(request)

    @app.get('/api/release')
    async def release_manifest():
        path = Path(__file__).resolve().parents[1] / 'release_manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'components': RELEASE}
        return JSONResponse(manifest, headers={'Cache-Control': 'no-store'})

    router = APIRouter(prefix="/api/assistant")
    limits = Limits()

    @router.get("/status")
    async def status(request: Request):
        try:
            settings()
            configured = True
        except ValueError:
            configured = False
        return JSONResponse({"configured": configured, "authenticated": bool(read_session(request.cookies.get(COOKIE))),
                "version": VERSION, "release": RELEASE, "provider": "DeepSeek-compatible API"}, headers={"Cache-Control": "no-store"})

    @router.post("/chat")
    async def chat(request: Request):
        # Reject cross-site paid calls even though the legacy app permits broad CORS.
        origin = request.headers.get("origin", "").rstrip("/")
        expected = os.getenv("HELICRAFT_AI_PUBLIC_ORIGIN", str(request.base_url).rstrip("/"))
        if origin != expected or request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Please use the assistant from the HeliCraft website.")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 64000:
                raise HTTPException(413, "The conversation is too long. Please start a new chat.")
        try:
            body = ChatRequest.model_validate_json(raw)
            if not body.message.strip():
                raise ValueError("Empty message")
        except (ValidationError, ValueError):
            raise HTTPException(422, "Invalid message or form data. Check the values and try again.") from None
        identity = require_session(request)
        try:
            config = settings()
        except ValueError:
            raise HTTPException(503, "The model service is not configured. Please contact the site administrator.") from None
        limits.reserve(identity)
        request_id = secrets.token_hex(12)
        try:
            try:
                raw_reply = await asyncio.wait_for(provider_call(make_messages(body), config), timeout=50)
                result = validate_reply(raw_reply, body)
            except (httpx.TimeoutException, asyncio.TimeoutError, TimeoutError):
                raise HTTPException(504, "The model request timed out. Your form is unchanged. Please try again.") from None
            except httpx.HTTPStatusError:
                raise HTTPException(502, "The model service rejected the request. Ask the administrator to check the model and account quota.") from None
            except httpx.RequestError:
                raise HTTPException(502, "Unable to reach the model service. Please try again.") from None
            except ModelOutputError as error:
                return output_error_response(error, request_id)
            except (ValueError, TypeError, KeyError, IndexError, ValidationError):
                return output_error_response(ModelOutputError("MODEL_OUTPUT_UNCLASSIFIED"), request_id)
            result.update(status="success", request_id=request_id, model=config[2],
                          prompt_version=PROMPT_VERSION, version=VERSION, release=RELEASE)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        finally:
            limits.active -= 1

    app.include_router(router)
    app.mount("/assistant-assets", StaticFiles(directory=Path(__file__).parent / "assets"), name="assistant-assets")
