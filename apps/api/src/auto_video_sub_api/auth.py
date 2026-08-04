from __future__ import annotations

import hmac
from ipaddress import ip_address, ip_network
from typing import Annotated, cast

from auto_video_sub_application import IdentityService
from auto_video_sub_domain import AuthenticationError, AuthorizationError, User
from fastapi import Depends, Header, Request


def _is_trusted_proxy(client_host: str, allowed: tuple[str, ...]) -> bool:
    try:
        address = ip_address(client_host)
    except ValueError:
        return client_host in allowed
    for entry in allowed:
        try:
            if address in ip_network(entry, strict=False):
                return True
        except ValueError:
            if hmac.compare_digest(client_host, entry):
                return True
    return False


async def current_user(
    request: Request,
    tailscale_login: Annotated[str | None, Header(alias="X-Forwarded-Tailscale-User-Login")] = None,
    proxy_secret: Annotated[str | None, Header(alias="X-Internal-Proxy-Secret")] = None,
) -> User:
    settings = request.app.state.settings
    if settings.tailscale_auth_enabled:
        client_host = request.client.host if request.client is not None else ""
        if not _is_trusted_proxy(client_host, settings.trusted_identity_proxy_ips):
            raise AuthenticationError("Request did not come through the trusted identity proxy")
        if proxy_secret is None or not hmac.compare_digest(
            proxy_secret,
            settings.internal_proxy_secret,
        ):
            raise AuthenticationError("Trusted proxy credential is missing or invalid")
        if tailscale_login is None:
            raise AuthenticationError("Tailscale identity is missing")
        normalized = tailscale_login.strip().casefold()
        if normalized not in settings.tailscale_allowed_logins:
            raise AuthorizationError("Tailscale identity is not allowed")
    else:
        normalized = settings.dev_auth_login.strip().casefold()
    identity_service = cast(IdentityService, request.app.state.identity_service)
    user = await identity_service.resolve(normalized)
    request.state.user_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(current_user)]
