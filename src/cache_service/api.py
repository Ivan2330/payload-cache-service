"""HTTP layer: routing, status codes, and nothing else."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cache_service import service
from cache_service.db import get_session
from cache_service.dependencies import get_transformer
from cache_service.schemas import PayloadCreated, PayloadRequest, PayloadResponse
from cache_service.transformer import Transformer

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
TransformerDep = Annotated[Transformer, Depends(get_transformer)]


@router.post(
    "/payload",
    response_model=PayloadCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a payload and return its identifier",
)
async def create_payload(
    request: PayloadRequest, session: SessionDep, transformer: TransformerDep
) -> PayloadCreated:
    identifier, created = await service.get_or_create_payload(
        session, transformer, request.list_1, request.list_2
    )
    # 201 either way: the identifier is deterministic, so a repeat is the same
    # resource rather than a conflict. "created" says which happened.
    return PayloadCreated(
        id=identifier,
        created=created,
        message="Payload created" if created else "Payload already existed",
    )


@router.get(
    "/payload/{identifier}",
    response_model=PayloadResponse,
    summary="Read a generated payload",
)
async def read_payload(identifier: str, session: SessionDep) -> PayloadResponse:
    output = await service.get_payload_output(session, identifier)
    if output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payload not found")
    return PayloadResponse(output=output)


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}
