"""Shared FastAPI dependencies reused across feature routers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

# Annotated DB session dependency. Import this in routers instead of
# re-declaring ``Depends(get_db)`` in every feature.
DBSession = Annotated[Session, Depends(get_db)]
