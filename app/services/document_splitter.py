from dataclasses import dataclass

from langchain_text_splitters import (
      RecursiveCharacterTextSplitter,
)


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int


class DocumentSplitter:
    def __init__(
            self,
            chunk_size: int = 500,
            chunk_overlap: int = 50,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(
            self,
            text: str,
    ) -> list[TextChunk]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
        )

        chunks = splitter.split_text(text)

        return [
            TextChunk(
                text=chunk_text,
                chunk_index=index,
            )
            for index, chunk_text in enumerate(chunks)
        ]