"""Read-only HTTP projection of local citation passage availability."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from pensieve_api.domain.claim_passages import lookup_claim_passages
from pensieve_api.domain.provenance import NonBlankText, SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_passages import PassageStore, SourcePassage
from pensieve_api.domain.source_registry import ResolutionStatus


class ReferencePassagesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reference: SourceReference
    status: ResolutionStatus
    passages: list[SourcePassage]


class ClaimPassageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    statement: NonBlankText
    references: list[ReferencePassagesResponse]
    all_references_registered: bool
    all_references_have_passages: bool


class LookupUnavailableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    detail: str


def get_passage_store(request: Request) -> PassageStore:
    store = request.app.state.passage_store
    if store is None:
        raise HTTPException(status_code=503, detail="Passage lookup is not configured")
    return store


router = APIRouter()


@router.post(
    "/api/v1/claims/passages/lookup",
    response_model=ClaimPassageResponse,
    responses={503: {"model": LookupUnavailableResponse,
                     "description": "Passage lookup is not configured"}},
)
def lookup_passages(
    claim: SourcedLoreClaim,
    store: Annotated[PassageStore, Depends(get_passage_store)],
) -> ClaimPassageResponse:
    result = lookup_claim_passages(claim, store)
    return ClaimPassageResponse(
        statement=result.statement,
        references=[ReferencePassagesResponse(
            reference=entry.reference, status=entry.status, passages=list(entry.passages),
        ) for entry in result.references],
        all_references_registered=result.all_references_registered,
        all_references_have_passages=result.all_references_have_passages,
    )
