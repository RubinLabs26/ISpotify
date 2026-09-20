"""Small ctypes wrapper around Discord's native Social SDK.

Only the presence and public-client authorization surface is exposed here.
The SDK owns its asynchronous work; callers must invoke ``run_callbacks``
regularly from the same worker thread that created the client.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

import keyring


APPLICATION_ID = 1551266524839411752
SDK_VERSION = "1.10.19337"
TOKEN_SERVICE = "iSpotify Discord"
TOKEN_ACCOUNT = str(APPLICATION_ID)


class DiscordSdkError(RuntimeError):
    pass


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
    if "redirect_uri" in lowered:
        return (
            "Discord setup required: add http://127.0.0.1/callback "
            "as an OAuth2 redirect URL"
        )
    if "invalid_client" in lowered:
        return "Discord setup required: enable Public Client on the OAuth2 page"
    return f"Discord login failed: {message}"


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
    ):
        self.on_status = on_status
        self.on_tokens = on_tokens
        self.on_account = on_account
        self._callbacks: list[object] = []
        self._access_token = ""
        self._refresh_token = ""
        self._authorizing = False
        self._closed = False

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
        lib.Discord_AuthorizationArgs_SetCodeChallenge.argtypes = [pointer, pointer]
        lib.Discord_AuthorizationCodeChallenge_Drop.argtypes = [pointer]
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
        lib.Discord_Activity_SetTimestamps.argtypes = [pointer, pointer]
        lib.Discord_ActivityTimestamps_Init.argtypes = [pointer]
        lib.Discord_ActivityTimestamps_Drop.argtypes = [pointer]
        lib.Discord_ActivityTimestamps_SetStart.argtypes = [
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
            if self._authorizing:
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

    def login(self) -> None:
        self._authorizing = True
        verifier = Opaque()
        challenge = Opaque()
        args = Opaque()
        self.lib.Discord_Client_CreateAuthorizationCodeVerifier(
            ctypes.byref(self.client), ctypes.byref(verifier)
        )
        self.lib.Discord_AuthorizationCodeVerifier_Challenge(
            ctypes.byref(verifier), ctypes.byref(challenge)
        )
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
            scopes, scopes_buffer = _input_string(self._default_scopes())
            self.lib.Discord_AuthorizationArgs_SetScopes(
                ctypes.byref(args), scopes
            )
            self.lib.Discord_AuthorizationArgs_SetCodeChallenge(
                ctypes.byref(args), ctypes.byref(challenge)
            )

            @self._remember
            @self.AuthorizationCallback
            def authorized(result, code, redirect_uri, _user_data):
                code_text = self._owned_string(code)
                redirect_text = self._owned_string(redirect_uri)
                successful, message = self._result(result)
                if not successful:
                    self._authorizing = False
                    self.on_account(False, _friendly_login_error(message))
                    return
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
            del scopes_buffer
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
                if source == "login":
                    text = _friendly_login_error(message)
                else:
                    text = f"Discord {source} failed: {message}"
                self.on_account(False, text)
                return
            self._authorizing = False
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
            if payload.get("start"):
                self.lib.Discord_ActivityTimestamps_Init(ctypes.byref(timestamps))
                self.lib.Discord_ActivityTimestamps_SetStart(
                    ctypes.byref(timestamps), int(payload["start"])
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
            if timestamps.opaque:
                self.lib.Discord_ActivityTimestamps_Drop(ctypes.byref(timestamps))
            self.lib.Discord_Activity_Drop(ctypes.byref(activity))

    def clear_presence(self) -> None:
        if not self._closed:
            self.lib.Discord_Client_ClearRichPresence(ctypes.byref(self.client))

    def logout(self) -> None:
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
        self.clear_presence()
        self.lib.Discord_Client_Disconnect(ctypes.byref(self.client))
        self.lib.Discord_Client_Drop(ctypes.byref(self.client))
        self._closed = True
