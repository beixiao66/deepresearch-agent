from fastapi import APIRouter, File, Path, UploadFile, status, Depends

from typing import Annotated

from app.api.dependencies import (
    DocumentServiceDependency, get_document_service,
)
from app.schemas.document import DocumentResponse
from app.services.document import DocumentService

router = APIRouter(prefix="/knowledge-bases/{knowledge_base_id}/documents",tags=["documents"],)


@router.post(
      "",
      response_model=DocumentResponse,
      status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: int = Path(gt=0),
    file: UploadFile = File(...),
        document_service: Annotated[
            DocumentService,
            Depends(get_document_service),
        ] = None,
) -> DocumentResponse:
    document = await document_service.upload_document(
        knowledge_base_id=knowledge_base_id,
        upload=file,
    )

    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=list[DocumentResponse],
)
async def list_documents(
    knowledge_base_id: int = Path(gt=0),
    document_service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ] = None,
) -> list[DocumentResponse]:
    documents = await document_service.list_by_knowledge_base(
        knowledge_base_id
    )

    return [
        DocumentResponse.model_validate(document)
        for document in documents
    ]


@router.delete(
      "/{document_id}",
      status_code=status.HTTP_204_NO_CONTENT,
  )
async def delete_document(
    knowledge_base_id: int = Path(gt=0),
    document_id: int = Path(gt=0),
    document_service: Annotated[
        DocumentService,
        Depends(get_document_service),
    ] = None,
) -> None:
    await document_service.delete_document(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )