
from fastapi import Depends, HTTPException, status, Header
from app.db import neo4j_conn
from typing import Optional

class TokenData:
    def __init__(self, uuid: str, roles: list):
        self.uuid = uuid
        self.roles = roles

async def get_current_user(x_auth_token: Optional[str] = Header(None)) -> TokenData:
    """Resolve the current user from the auth token header."""
    if not x_auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await neo4j_conn.get_user_by_token(x_auth_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uuid = user.get("uuid")
    roles = await neo4j_conn.get_user_roles(uuid)

    if not uuid or not roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User information incomplete.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenData(uuid=uuid, roles=roles)