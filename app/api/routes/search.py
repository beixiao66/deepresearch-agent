from fastapi import APIRouter, Path

from app.api.dependencies import DocumentRetrieverDependency
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)


router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/search",tags=["search"],)


@router.post("", response_model=SearchResponse)
async def search_documents(
        knowledge_base_id: int = Path(gt=0),
        request: SearchRequest = None,
        retriever: DocumentRetrieverDependency = None,
) -> SearchResponse:
    results = await retriever.retrieve(
        question=request.question,
        knowledge_base_id=knowledge_base_id,
    )

    return SearchResponse(
        results=[
            SearchResultItem(
                document_id=result.document_id,
                chunk_index=result.chunk_index,
                text=result.text,
                score=result.score,
            )
            for result in results
        ]
    )