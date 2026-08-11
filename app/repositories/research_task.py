from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_task import (
    ResearchTask,
    ResearchTaskStatus,
)


class ResearchTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
            self,
            topic: str,
            knowledge_base_id: int,
    ) -> ResearchTask:
        task = ResearchTask(
            topic=topic,
            knowledge_base_id=knowledge_base_id,
            status=ResearchTaskStatus.PENDING.value,
        )

        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)

        return task

    async def get_by_id(
            self,
            task_id: int,
    ) -> ResearchTask | None:
        return await self.session.get(
            ResearchTask,
            task_id,
        )

    async def list_all(self) -> list[ResearchTask]:
        statement = select(ResearchTask).order_by(
            ResearchTask.id.desc()
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def update_status(
            self,
            task: ResearchTask,
            status: ResearchTaskStatus,
            error_message: str | None = None,
    ) -> None:
        task.status = status.value
        task.error_message = error_message

    async def save_plan(
            self,
            task: ResearchTask,
            plan: str | None,
            thread_id: str,
    ) -> None:
        task.plan = plan
        task.thread_id = thread_id
        task.status = ResearchTaskStatus.AWAITING_APPROVAL.value

    async def save_report(
            self,
            task: ResearchTask,
            report: str,
    ) -> None:
        task.report = report
        task.status = ResearchTaskStatus.COMPLETED.value

    async def save_token_usage(
            self,
            task: ResearchTask,
            token_usage: str | None,
    ) -> None:
        task.token_usage = token_usage
