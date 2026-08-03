from fastapi import APIRouter, Path, status

from app.api.dependencies import KnowledgeBaseServiceDependency
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["knowledge-bases"],
)

@router.post(
      "",
      response_model=KnowledgeBaseResponse,
      status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
      data: KnowledgeBaseCreate,
      service: KnowledgeBaseServiceDependency,
) -> KnowledgeBaseResponse:
    knowledge_base = await service.create(data)

    return KnowledgeBaseResponse.model_validate(
        knowledge_base
    )


@router.get(
      "",
      response_model=list[KnowledgeBaseResponse],
)
async def list_knowledge_bases(
      service: KnowledgeBaseServiceDependency,
) -> list[KnowledgeBaseResponse]:
      knowledge_bases = await service.list_all()

      return [
          KnowledgeBaseResponse.model_validate(knowledge_base)
          for knowledge_base in knowledge_bases
      ]


@router.get(
      "/{knowledge_base_id}",
      response_model=KnowledgeBaseResponse,
)
async def get_knowledge_base(
      service: KnowledgeBaseServiceDependency,
      knowledge_base_id: int = Path(gt=0),
) -> KnowledgeBaseResponse:
      knowledge_base = await service.get_by_id(
          knowledge_base_id
      )

      return KnowledgeBaseResponse.model_validate(
          knowledge_base
      )