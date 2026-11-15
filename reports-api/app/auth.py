from __future__ import annotations

import logging

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError, PyJWTError

from app.config import KEYCLOAK_ISSUER, KEYCLOAK_JWKS_URL

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_jwks = PyJWKClient(KEYCLOAK_JWKS_URL, cache_keys=True)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Требуется Bearer-токен")

    try:
        signing_key = _jwks.get_signing_key_from_jwt(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            issuer=KEYCLOAK_ISSUER,
            options={"verify_aud": False},
        )
    except PyJWTError as exc:
        logger.info("Rejected token: %s", exc)
        raise HTTPException(status_code=401, detail="Недействительный токен") from exc
    except PyJWKClientError as exc:
        logger.warning("Keycloak JWKS unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail="Сервис аутентификации недоступен"
        ) from exc

    username = payload.get("preferred_username")
    if not isinstance(username, str) or not username:
        raise HTTPException(status_code=401, detail="В токене нет пользователя")
    return username
