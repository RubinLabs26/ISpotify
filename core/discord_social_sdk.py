"""Small ctypes wrapper around Discord's native Social SDK.

Only the presence and public-client authorization surface is exposed here.
The SDK owns its asynchronous work; callers must invoke ``run_callbacks``
regularly from the same worker thread that created the client.
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import secrets
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit

import keyring


APPLICATION_ID = 1551266524839411752
SDK_VERSION = "1.10.19337"
TOKEN_SERVICE = "iSpotify Discord"
TOKEN_ACCOUNT = str(APPLICATION_ID)
DISCORD_AUTHORIZE_ENDPOINT = "https://discord.com/oauth2/authorize"
DESKTOP_REDIRECT_URI = "http://127.0.0.1/callback"


class DiscordSdkError(RuntimeError):
    pass


class OAuthCallbackServer:
    """Receive one Discord OAuth redirect on the registered loopback URI."""

    def __init__(self, redirect_uri: str, expected_state: str):
        parsed = urlsplit(redirect_uri)
        if parsed.scheme != "http" or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
        }:
            raise ValueError("Discord OAuth requires an HTTP loopback redirect")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path or "/"
        self.expected_state = expected_state
        self._results: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        callback = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
                request = urlsplit(self.path)
                if request.path != callback.path:
                    self._reply(
                        HTTPStatus.NOT_FOUND,
                        "This is not an iSpotify authorization callback.",
                    )
                    return
                values = parse_qs(request.query)
                if values.get("state", [""])[0] != callback.expected_state:
                    self._reply(
                        HTTPStatus.BAD_REQUEST,
                        "The authorization state did not match. Return to iSpotify and try again.",
                    )
                    return
                error = values.get("error_description", values.get("error", [""]))[0]
                code = values.get("code", [""])[0]
                if error:
                    callback._submit("", error)
                    self._reply(
                        HTTPStatus.OK,
                        "Discord authorization was cancelled. You can close this tab.",
                    )
                elif code:
                    callback._submit(code, "")
                    self._reply(
                        HTTPStatus.OK,
                        "Discord is connected to iSpotify. You can close this tab and return to the app.",
                    )
                else:
                    self._reply(
                        HTTPStatus.BAD_REQUEST,
                        "Discord did not provide an authorization code. Return to iSpotify and try again.",
                    )

            def _reply(self, status: HTTPStatus, message: str) -> None:
                body = (
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width'>"
                    "<title>iSpotify Discord</title></head>"
                    "<body style='margin:0;background:#090909;color:#fff;"
                    "font:16px system-ui;display:grid;place-items:center;min-height:100vh'>"
                    f"<main style='max-width:520px;padding:32px;text-align:center'>"
                    f"<h1>iSpotify</h1><p>{escape(message)}</p></main></body></html>"
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args) -> None:
                return

        class Server(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._server = Server((self.host, self.port), Handler)
        self.port = int(self._server.server_port)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="discord-oauth-callback",
            daemon=True,
        )
        self._thread.start()

    def _submit(self, code: str, error: str) -> None:
        try:
            self._results.put_nowait((code, error))
        except queue.Full:
            pass

    def poll(self) -> tuple[str, str] | None:
        try:
            return self._results.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)


class DiscordString(ctypes.Structure):
    _fields_ = [("ptr", ctypes.POINTER(ctypes.c_uint8)), ("size", ctypes.c_size_t)]


class Opaque(ctypes.Structure):
    _fields_ = [("opaque", ctypes.c_void_p)]


def _input_string(value: str) -> tuple[DiscordString, ctypes.Array]:
    raw = value.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint8))
    return DiscordString(pointer, len(raw)), buffer


def _copy_string(value: DiscordString) -> str:
    if not value.ptr or not value.size:
        return ""
    return ctypes.string_at(value.ptr, value.size).decode("utf-8", errors="replace")


def _friendly_login_error(message: str) -> str:
    lowered = message.lower()
    if "redirect_uri" in lowered or "redirect uri" in lowered:
        return (
            "Discord rejected the redirect. In application 1551266524839411752, "
            "save http://127.0.0.1/callback under OAuth2 > Redirects."
        )
    if "invalid_client" in lowered:
        return "Discord setup required: enable Public Client on the OAuth2 page"
    return f"Discord login failed: {message}"


def authorization_url(scopes: str, challenge: str, state: str) -> str:
    """Build the browser fallback for the SDK-managed desktop OAuth flow."""
    query = urlencode({
        "client_id": str(APPLICATION_ID),
        "response_type": "code",
        "redirect_uri": DESKTOP_REDIRECT_URI,
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{DISCORD_AUTHORIZE_ENDPOINT}?{query}"


def sdk_library_path() -> Path:
    filename = (
        "discord_partner_sdk.dll"
        if sys.platform == "win32"
        else "libdiscord_partner_sdk.so"
    )
    packaged_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    candidates = [
        packaged_root / "discord_social_sdk" / filename,
        Path(__file__).resolve().parents[1]
        / "vendor"
        / "discord_social_sdk"
        / ("windows-x86_64" if sys.platform == "win32" else "linux-x86_64")
        / filename,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise DiscordSdkError(f"Discord Social SDK {SDK_VERSION} is not packaged")


class TokenStore:
    """Store OAuth credentials in the operating system's credential vault."""

    def load(self) -> dict | None:
        try:
            payload = keyring.get_password(TOKEN_SERVICE, TOKEN_ACCOUNT)
        except Exception:
            return None
        if not payload:
            return None
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict) or not data.get("refresh_token"):
            return None
        return data

    def save(
        self, access_token: str, refresh_token: str, expires_in: int
    ) -> bool:
        payload = json.dumps(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": int(time.time()) + max(0, int(expires_in)),
            },
            separators=(",", ":"),
        )
        try:
            keyring.set_password(TOKEN_SERVICE, TOKEN_ACCOUNT, payload)
        except Exception:
            return False
        return True

    def clear(self) -> None:
        try:
            keyring.delete_password(TOKEN_SERVICE, TOKEN_ACCOUNT)
        except Exception:
            pass


class DiscordSocialClient:
    """Discord Social SDK client used from one background thread."""

    READY = 3
    BEARER = 1
    LISTENING = 2

    def __init__(
        self,
        on_status: Callable[[int, int], None],
        on_tokens: Callable[[str, str, int], None],
        on_account: Callable[[bool, str], None],
        on_authorization_url: Callable[[str], None] | None = None,
    ):
        self.on_status = on_status
        self.on_tokens = on_tokens
        self.on_account = on_account
        self.on_authorization_url = on_authorization_url or (lambda _url: None)
        self._callbacks: list[object] = []
        self._access_token = ""
        self._refresh_token = ""
        self._authorizing = False
        self._oauth_exchange_pending = False
        self._closed = False
        self._oauth_callback: OAuthCallbackServer | None = None
        self._browser_verifier = ""

        path = sdk_library_path()
        if sys.platform == "win32":
            dll_dir = os.add_dll_directory(str(path.parent))
            try:
                self.lib = ctypes.CDLL(str(path))
            finally:
                dll_dir.close()
        else:
            self.lib = ctypes.CDLL(str(path))
        self._bind()
        self.client = Opaque()
        self.lib.Discord_Client_Init(ctypes.byref(self.client))
        if not self.client.opaque:
            raise DiscordSdkError("Discord Social SDK could not start")
        self._install_callbacks()

    def _bind(self) -> None:
        lib = self.lib
        pointer = ctypes.POINTER(Opaque)
        string_pointer = ctypes.POINTER(DiscordString)

        lib.Discord_Free.argtypes = [ctypes.c_void_p]
        lib.Discord_RunCallbacks.argtypes = []
        lib.Discord_Client_Init.argtypes = [pointer]
        lib.Discord_Client_Drop.argtypes = [pointer]
        lib.Discord_Client_Disconnect.argtypes = [pointer]
        lib.Discord_Client_Connect.argtypes = [pointer]
        lib.Discord_Client_ClearRichPresence.argtypes = [pointer]
        lib.Discord_Client_AbortAuthorize.argtypes = [pointer]

        lib.Discord_ClientResult_Successful.argtypes = [pointer]
        lib.Discord_ClientResult_Successful.restype = ctypes.c_bool
        lib.Discord_ClientResult_ToString.argtypes = [pointer, string_pointer]
        lib.Discord_ClientResult_Drop.argtypes = [pointer]

        lib.Discord_Client_GetDefaultPresenceScopes.argtypes = [string_pointer]
        lib.Discord_AuthorizationArgs_Init.argtypes = [pointer]
        lib.Discord_AuthorizationArgs_Drop.argtypes = [pointer]
        lib.Discord_AuthorizationArgs_SetClientId.argtypes = [pointer, ctypes.c_uint64]
        lib.Discord_AuthorizationArgs_SetScopes.argtypes = [pointer, DiscordString]
        lib.Discord_AuthorizationArgs_SetState.argtypes = [
            pointer,
            string_pointer,
        ]
        lib.Discord_AuthorizationArgs_SetCodeChallenge.argtypes = [pointer, pointer]
        lib.Discord_AuthorizationCodeChallenge_Drop.argtypes = [pointer]
        lib.Discord_AuthorizationCodeChallenge_Challenge.argtypes = [
            pointer,
            string_pointer,
        ]
        lib.Discord_AuthorizationCodeVerifier_Drop.argtypes = [pointer]
        lib.Discord_AuthorizationCodeVerifier_Challenge.argtypes = [pointer, pointer]
        lib.Discord_AuthorizationCodeVerifier_Verifier.argtypes = [
            pointer,
            string_pointer,
        ]

        self.TokenCallback = ctypes.CFUNCTYPE(
            None,
            pointer,
            DiscordString,
            DiscordString,
            ctypes.c_int,
            ctypes.c_int32,
            DiscordString,
            ctypes.c_void_p,
        )
        self.AuthorizationCallback = ctypes.CFUNCTYPE(
            None,
            pointer,
            DiscordString,
            DiscordString,
            ctypes.c_void_p,
        )
        self.ResultCallback = ctypes.CFUNCTYPE(None, pointer, ctypes.c_void_p)
        self.StatusCallback = ctypes.CFUNCTYPE(
            None, ctypes.c_int, ctypes.c_int, ctypes.c_int32, ctypes.c_void_p
        )
        self.FetchUserCallback = ctypes.CFUNCTYPE(
            None, pointer, ctypes.c_uint64, DiscordString, ctypes.c_void_p
        )
        self.VoidCallback = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

        lib.Discord_Client_CreateAuthorizationCodeVerifier.argtypes = [
            pointer,
            pointer,
        ]
        lib.Discord_Client_Authorize.argtypes = [
            pointer,
            pointer,
            self.AuthorizationCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_GetToken.argtypes = [
            pointer,
            ctypes.c_uint64,
            DiscordString,
            DiscordString,
            DiscordString,
            self.TokenCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_RefreshToken.argtypes = [
            pointer,
            ctypes.c_uint64,
            DiscordString,
            self.TokenCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_UpdateToken.argtypes = [
            pointer,
            ctypes.c_int,
            DiscordString,
            self.ResultCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_RevokeToken.argtypes = [
            pointer,
            ctypes.c_uint64,
            DiscordString,
            self.ResultCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_FetchCurrentUser.argtypes = [
            pointer,
            ctypes.c_int,
            DiscordString,
            self.FetchUserCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_SetStatusChangedCallback.argtypes = [
            pointer,
            self.StatusCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_SetTokenExpirationCallback.argtypes = [
            pointer,
            self.VoidCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.Discord_Client_SetAuthorizeDeviceScreenClosedCallback.argtypes = [
            pointer,
            self.VoidCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]

        lib.Discord_Activity_Init.argtypes = [pointer]
        lib.Discord_Activity_Drop.argtypes = [pointer]
        lib.Discord_Activity_SetName.argtypes = [pointer, DiscordString]
        lib.Discord_Activity_SetType.argtypes = [pointer, ctypes.c_int]
        lib.Discord_Activity_SetState.argtypes = [pointer, string_pointer]
        lib.Discord_Activity_SetDetails.argtypes = [pointer, string_pointer]
        lib.Discord_Activity_SetApplicationId.argtypes = [
            pointer,
            ctypes.POINTER(ctypes.c_uint64),
        ]
        lib.Discord_ActivityAssets_Init.argtypes = [pointer]
        lib.Discord_ActivityAssets_Drop.argtypes = [pointer]
        lib.Discord_ActivityAssets_SetLargeImage.argtypes = [
            pointer, string_pointer,
        ]
        lib.Discord_ActivityAssets_SetLargeText.argtypes = [
            pointer, string_pointer,
        ]
        lib.Discord_ActivityAssets_SetLargeUrl.argtypes = [
            pointer, string_pointer,
        ]
        lib.Discord_Activity_SetAssets.argtypes = [pointer, pointer]
        lib.Discord_ActivityButton_Init.argtypes = [pointer]
        lib.Discord_ActivityButton_Drop.argtypes = [pointer]
        lib.Discord_ActivityButton_SetLabel.argtypes = [pointer, DiscordString]
        lib.Discord_ActivityButton_SetUrl.argtypes = [pointer, DiscordString]
        lib.Discord_Activity_AddButton.argtypes = [pointer, pointer]
        lib.Discord_Activity_SetTimestamps.argtypes = [pointer, pointer]
        lib.Discord_ActivityTimestamps_Init.argtypes = [pointer]
        lib.Discord_ActivityTimestamps_Drop.argtypes = [pointer]
        lib.Discord_ActivityTimestamps_SetStart.argtypes = [
            pointer,
            ctypes.c_uint64,
        ]
        lib.Discord_ActivityTimestamps_SetEnd.argtypes = [
            pointer,
            ctypes.c_uint64,
        ]
        lib.Discord_Client_UpdateRichPresence.argtypes = [
            pointer,
            pointer,
            self.ResultCallback,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]

    def _remember(self, callback):
        self._callbacks.append(callback)
        return callback

    def _install_callbacks(self) -> None:
        @self._remember
        @self.StatusCallback
        def status_changed(status, error, _detail, _user_data):
            self.on_status(int(status), int(error))

        @self._remember
        @self.VoidCallback
        def token_expired(_user_data):
            if self._refresh_token:
                self.refresh(self._refresh_token)
            else:
                self.on_account(False, "Discord login expired")

        @self._remember
        @self.ResultCallback
        def presence_updated(result, _user_data):
            successful, message = self._result(result)
            if successful:
                self.on_status(self.READY, 0)
            elif message:
                self.on_status(0, 1)

        self._presence_updated = presence_updated

        @self._remember
        @self.VoidCallback
        def authorization_closed(_user_data):
            if (
                self._authorizing
                and self._oauth_callback is None
                and not self._oauth_exchange_pending
            ):
                self._authorizing = False
                self.on_account(False, "Discord authorization was cancelled")

        self.lib.Discord_Client_SetStatusChangedCallback(
            ctypes.byref(self.client), status_changed, None, None
        )
        self.lib.Discord_Client_SetTokenExpirationCallback(
            ctypes.byref(self.client), token_expired, None, None
        )
        self.lib.Discord_Client_SetAuthorizeDeviceScreenClosedCallback(
            ctypes.byref(self.client), authorization_closed, None, None
        )

    def _result(self, result: ctypes.POINTER(Opaque)) -> tuple[bool, str]:
        successful = bool(self.lib.Discord_ClientResult_Successful(result))
        text = DiscordString()
        self.lib.Discord_ClientResult_ToString(result, ctypes.byref(text))
        message = _copy_string(text)
        if text.ptr:
            self.lib.Discord_Free(text.ptr)
        self.lib.Discord_ClientResult_Drop(result)
        return successful, message

    def _owned_string(self, value: DiscordString) -> str:
        copied = _copy_string(value)
        if value.ptr:
            self.lib.Discord_Free(value.ptr)
        return copied

    def _default_scopes(self) -> str:
        value = DiscordString()
        self.lib.Discord_Client_GetDefaultPresenceScopes(ctypes.byref(value))
        return self._owned_string(value)

    def run_callbacks(self) -> None:
        if not self._closed:
            self.lib.Discord_RunCallbacks()
            callback = self._oauth_callback
            result = callback.poll() if callback is not None else None
            if result is not None:
                code, error = result
                verifier = self._browser_verifier
                self._stop_oauth_callback()
                if not self._authorizing:
                    return
                if error:
                    self._authorizing = False
                    self.on_account(False, f"Discord login failed: {error}")
                elif code:
                    self._oauth_exchange_pending = True
                    self._exchange_authorization_code(
                        code,
                        verifier,
                        DESKTOP_REDIRECT_URI,
                    )

    def _stop_oauth_callback(self) -> None:
        callback = self._oauth_callback
        self._oauth_callback = None
        self._browser_verifier = ""
        if callback is not None:
            callback.stop()

    def login(self) -> None:
        self._stop_oauth_callback()
        self._authorizing = True
        self._oauth_exchange_pending = False
        verifier = Opaque()
        challenge = Opaque()
        args = Opaque()
        self.lib.Discord_Client_CreateAuthorizationCodeVerifier(
            ctypes.byref(self.client), ctypes.byref(verifier)
        )
        self.lib.Discord_AuthorizationCodeVerifier_Challenge(
            ctypes.byref(verifier), ctypes.byref(challenge)
        )
        challenge_value = DiscordString()
        self.lib.Discord_AuthorizationCodeChallenge_Challenge(
            ctypes.byref(challenge), ctypes.byref(challenge_value)
        )
        challenge_text = self._owned_string(challenge_value)
        verifier_value = DiscordString()
        self.lib.Discord_AuthorizationCodeVerifier_Verifier(
            ctypes.byref(verifier), ctypes.byref(verifier_value)
        )
        verifier_text = self._owned_string(verifier_value)
        self.lib.Discord_AuthorizationArgs_Init(ctypes.byref(args))
        try:
            self.lib.Discord_AuthorizationArgs_SetClientId(
                ctypes.byref(args), APPLICATION_ID
            )
            scopes_text = self._default_scopes()
            scopes, scopes_buffer = _input_string(scopes_text)
            self.lib.Discord_AuthorizationArgs_SetScopes(
                ctypes.byref(args), scopes
            )
            state_text = secrets.token_urlsafe(32)
            state, state_buffer = _input_string(state_text)
            self.lib.Discord_AuthorizationArgs_SetState(
                ctypes.byref(args), ctypes.byref(state)
            )
            self.lib.Discord_AuthorizationArgs_SetCodeChallenge(
                ctypes.byref(args), ctypes.byref(challenge)
            )

            callback = OAuthCallbackServer(DESKTOP_REDIRECT_URI, state_text)
            try:
                callback.start()
            except OSError as exc:
                self.on_account(
                    False,
                    "Discord browser login could not start its local callback "
                    f"listener on {DESKTOP_REDIRECT_URI}: {exc}",
                )
            else:
                self._oauth_callback = callback
                self._browser_verifier = verifier_text

            @self._remember
            @self.AuthorizationCallback
            def authorized(result, code, redirect_uri, _user_data):
                code_text = self._owned_string(code)
                redirect_text = self._owned_string(redirect_uri)
                successful, message = self._result(result)
                if self._oauth_exchange_pending:
                    return
                if not successful:
                    if self._oauth_callback is None:
                        self._authorizing = False
                        self.on_account(False, _friendly_login_error(message))
                    return
                if not self._authorizing:
                    return
                self._stop_oauth_callback()
                self._oauth_exchange_pending = True
                self._exchange_authorization_code(
                    code_text, verifier_text, redirect_text
                )

            self.lib.Discord_Client_Authorize(
                ctypes.byref(self.client),
                ctypes.byref(args),
                authorized,
                None,
                None,
            )
            if self._oauth_callback is not None:
                self.on_authorization_url(
                    authorization_url(scopes_text, challenge_text, state_text)
                )
            del scopes_buffer, state_buffer
        finally:
            self.lib.Discord_AuthorizationArgs_Drop(ctypes.byref(args))
            self.lib.Discord_AuthorizationCodeChallenge_Drop(
                ctypes.byref(challenge)
            )
            self.lib.Discord_AuthorizationCodeVerifier_Drop(
                ctypes.byref(verifier)
            )

    def _token_callback(self, source: str):
        @self._remember
        @self.TokenCallback
        def tokens_received(
            result,
            access_token,
            refresh_token,
            _token_type,
            expires_in,
            scopes,
            _user_data,
        ):
            access = self._owned_string(access_token)
            refresh = self._owned_string(refresh_token)
            self._owned_string(scopes)
            successful, message = self._result(result)
            if not successful:
                self._authorizing = False
                self._oauth_exchange_pending = False
                if source == "login":
                    text = _friendly_login_error(message)
                else:
                    text = f"Discord {source} failed: {message}"
                self.on_account(False, text)
                return
            self._authorizing = False
            self._oauth_exchange_pending = False
            self._access_token = access
            self._refresh_token = refresh
            self.on_tokens(access, refresh, int(expires_in))
            self._use_access_token(access)

        return tokens_received

    def _exchange_authorization_code(
        self, code: str, verifier: str, redirect_uri: str
    ) -> None:
        code_value, code_buffer = _input_string(code)
        verifier_value, verifier_buffer = _input_string(verifier)
        redirect_value, redirect_buffer = _input_string(redirect_uri)
        self.lib.Discord_Client_GetToken(
            ctypes.byref(self.client),
            APPLICATION_ID,
            code_value,
            verifier_value,
            redirect_value,
            self._token_callback("login"),
            None,
            None,
        )
        del code_buffer, verifier_buffer, redirect_buffer

    def refresh(self, refresh_token: str) -> None:
        self._refresh_token = refresh_token
        refresh, refresh_buffer = _input_string(self._refresh_token)
        self.lib.Discord_Client_RefreshToken(
            ctypes.byref(self.client),
            APPLICATION_ID,
            refresh,
            self._token_callback("session refresh"),
            None,
            None,
        )
        del refresh_buffer

    def restore(self, credentials: dict) -> None:
        self._access_token = str(credentials.get("access_token") or "")
        self._refresh_token = str(credentials.get("refresh_token") or "")
        expires_at = int(credentials.get("expires_at") or 0)
        if self._access_token and expires_at > time.time() + 60:
            self._use_access_token(self._access_token)
        elif self._refresh_token:
            self.refresh(self._refresh_token)

    def _use_access_token(self, access_token: str) -> None:
        token, token_buffer = _input_string(access_token)

        @self._remember
        @self.ResultCallback
        def token_updated(result, _user_data):
            successful, message = self._result(result)
            if not successful:
                self.on_account(False, f"Discord login failed: {message}")
                return
            self.lib.Discord_Client_Connect(ctypes.byref(self.client))
            self._fetch_account(access_token)

        self.lib.Discord_Client_UpdateToken(
            ctypes.byref(self.client),
            self.BEARER,
            token,
            token_updated,
            None,
            None,
        )
        del token_buffer

    def _fetch_account(self, access_token: str) -> None:
        token, token_buffer = _input_string(access_token)

        @self._remember
        @self.FetchUserCallback
        def account_received(result, _user_id, name, _user_data):
            username = self._owned_string(name)
            successful, message = self._result(result)
            if successful:
                self.on_account(True, username or "Discord account")
            else:
                self.on_account(False, f"Discord login failed: {message}")

        self.lib.Discord_Client_FetchCurrentUser(
            ctypes.byref(self.client),
            self.BEARER,
            token,
            account_received,
            None,
            None,
        )
        del token_buffer

    def update_presence(self, payload: dict) -> None:
        activity = Opaque()
        timestamps = Opaque()
        assets = Opaque()
        buttons: list[Opaque] = []
        button_buffers: list[ctypes.Array] = []
        self.lib.Discord_Activity_Init(ctypes.byref(activity))
        try:
            name, name_buffer = _input_string("iSpotify")
            details, details_buffer = _input_string(str(payload["details"]))
            state, state_buffer = _input_string(str(payload["state"]))
            self.lib.Discord_Activity_SetName(ctypes.byref(activity), name)
            self.lib.Discord_Activity_SetType(
                ctypes.byref(activity), self.LISTENING
            )
            self.lib.Discord_Activity_SetDetails(
                ctypes.byref(activity), ctypes.byref(details)
            )
            self.lib.Discord_Activity_SetState(
                ctypes.byref(activity), ctypes.byref(state)
            )
            application_id = ctypes.c_uint64(APPLICATION_ID)
            self.lib.Discord_Activity_SetApplicationId(
                ctypes.byref(activity), ctypes.byref(application_id)
            )
            if payload.get("large_image"):
                self.lib.Discord_ActivityAssets_Init(ctypes.byref(assets))
                large_image, large_image_buffer = _input_string(
                    str(payload["large_image"])
                )
                large_text, large_text_buffer = _input_string(
                    str(payload.get("large_text") or payload["details"])
                )
                self.lib.Discord_ActivityAssets_SetLargeImage(
                    ctypes.byref(assets), ctypes.byref(large_image)
                )
                self.lib.Discord_ActivityAssets_SetLargeText(
                    ctypes.byref(assets), ctypes.byref(large_text)
                )
                large_url_buffer = None
                if payload.get("url"):
                    large_url, large_url_buffer = _input_string(str(payload["url"]))
                    self.lib.Discord_ActivityAssets_SetLargeUrl(
                        ctypes.byref(assets), ctypes.byref(large_url)
                    )
                self.lib.Discord_Activity_SetAssets(
                    ctypes.byref(activity), ctypes.byref(assets)
                )
            for value in payload.get("buttons", [])[:2]:
                if not value.get("label") or not value.get("url"):
                    continue
                button = Opaque()
                self.lib.Discord_ActivityButton_Init(ctypes.byref(button))
                button_label, button_label_buffer = _input_string(str(value["label"]))
                button_url, button_url_buffer = _input_string(str(value["url"]))
                self.lib.Discord_ActivityButton_SetLabel(
                    ctypes.byref(button), button_label
                )
                self.lib.Discord_ActivityButton_SetUrl(
                    ctypes.byref(button), button_url
                )
                self.lib.Discord_Activity_AddButton(
                    ctypes.byref(activity), ctypes.byref(button)
                )
                buttons.append(button)
                button_buffers.extend((button_label_buffer, button_url_buffer))
            if payload.get("start"):
                self.lib.Discord_ActivityTimestamps_Init(ctypes.byref(timestamps))
                self.lib.Discord_ActivityTimestamps_SetStart(
                    ctypes.byref(timestamps), int(payload["start"])
                )
                if payload.get("end"):
                    self.lib.Discord_ActivityTimestamps_SetEnd(
                        ctypes.byref(timestamps), int(payload["end"])
                    )
                self.lib.Discord_Activity_SetTimestamps(
                    ctypes.byref(activity), ctypes.byref(timestamps)
                )

            self.lib.Discord_Client_UpdateRichPresence(
                ctypes.byref(self.client),
                ctypes.byref(activity),
                self._presence_updated,
                None,
                None,
            )
            del name_buffer, details_buffer, state_buffer
        finally:
            for button in buttons:
                self.lib.Discord_ActivityButton_Drop(ctypes.byref(button))
            if assets.opaque:
                self.lib.Discord_ActivityAssets_Drop(ctypes.byref(assets))
            if timestamps.opaque:
                self.lib.Discord_ActivityTimestamps_Drop(ctypes.byref(timestamps))
            self.lib.Discord_Activity_Drop(ctypes.byref(activity))

    def clear_presence(self) -> None:
        if not self._closed:
            self.lib.Discord_Client_ClearRichPresence(ctypes.byref(self.client))

    def logout(self) -> None:
        self._authorizing = False
        self._oauth_exchange_pending = False
        self._stop_oauth_callback()
        self.clear_presence()
        if self._access_token:
            token, token_buffer = _input_string(self._access_token)

            @self._remember
            @self.ResultCallback
            def revoked(result, _user_data):
                self._result(result)

            self.lib.Discord_Client_RevokeToken(
                ctypes.byref(self.client),
                APPLICATION_ID,
                token,
                revoked,
                None,
                None,
            )
            del token_buffer
        self.lib.Discord_Client_Disconnect(ctypes.byref(self.client))
        self._access_token = ""
        self._refresh_token = ""
        self.on_account(False, "Not connected")

    def close(self) -> None:
        if self._closed:
            return
        self._authorizing = False
        self._oauth_exchange_pending = False
        self._stop_oauth_callback()
        self.clear_presence()
        self.lib.Discord_Client_Disconnect(ctypes.byref(self.client))
        self.lib.Discord_Client_Drop(ctypes.byref(self.client))
        self._closed = True
