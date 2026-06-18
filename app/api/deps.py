from typing import Annotated

from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlmodel import Session

from app.api.v1.users.models import User
from app.core.database import get_db
from app.shared.constants import DEFAULT_PAGE_NUM, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.shared.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
SessionDep = Annotated[Session, Depends(get_db)]


class PaginationParams:
    """对外 pageNum/pageSize，对内 offset/limit。"""

    def __init__(
        self,
        page_num: Annotated[int, Query(alias="pageNum", ge=1)] = DEFAULT_PAGE_NUM,
        page_size: Annotated[
            int, Query(alias="pageSize", ge=1, le=MAX_PAGE_SIZE)
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.page_num = page_num
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page_num - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]


def get_current_user(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
) -> User:
    """校验 token 并返回当前登录用户。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        subject = payload.get("sub")
        user_id = int(subject)
        user = session.get(User, user_id)
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user


CurrentUser = Annotated[User, Security(get_current_user)]
