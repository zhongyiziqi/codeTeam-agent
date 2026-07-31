import math
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from codeteam.indexing.embeddings import TOKEN_PATTERN, create_embeddings
from codeteam.models import CodeChunk


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    file_path: str
    language: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


class HybridCodeRetriever:
    def __init__(self, session: Session):
        self.session = session
        self.embeddings = create_embeddings()

    def search(
        self,
        repository_id: str,
        query: str,
        limit: int = 8,
        path_filter: str | None = None,
        symbol_filter: str | None = None,
    ) -> list[RetrievalResult]:
        statement = select(CodeChunk).where(CodeChunk.repository_id == repository_id)
        if path_filter:
            statement = statement.where(CodeChunk.file_path.contains(path_filter))
        if symbol_filter:
            statement = statement.where(CodeChunk.symbol_name.contains(symbol_filter))
        query_embedding = self.embeddings.embed_query(query)
        is_postgres = (
            self.session.bind is not None and self.session.bind.dialect.name == "postgresql"
        )
        vector_scores: dict[str, float] = {}
        if is_postgres:
            distance = CodeChunk.embedding.op("<=>")(query_embedding)
            candidate_limit = max(limit * 8, 40)
            rows = self.session.execute(
                statement.add_columns(distance.label("distance"))
                .where(CodeChunk.embedding.is_not(None))
                .order_by(distance)
                .limit(candidate_limit)
            ).all()
            chunks = [row[0] for row in rows]
            vector_scores = {row[0].id: max(0.0, 1.0 - float(row[1])) for row in rows}
        else:
            chunks = self.session.scalars(statement).all()
        query_tokens = set(TOKEN_PATTERN.findall(query.lower()))

        scored = []
        for chunk in chunks:
            vector_score = vector_scores.get(
                chunk.id, _cosine(query_embedding, list(chunk.embedding or []))
            )
            searchable = f"{chunk.file_path} {chunk.symbol_name or ''} {chunk.content}".lower()
            searchable_tokens = set(TOKEN_PATTERN.findall(searchable))
            keyword_score = len(query_tokens & searchable_tokens) / max(len(query_tokens), 1)
            exact_bonus = 0.15 if any(token in searchable for token in query_tokens) else 0.0
            score = 0.55 * vector_score + 0.45 * keyword_score + exact_bonus
            scored.append(
                RetrievalResult(
                    chunk_id=chunk.id,
                    file_path=chunk.file_path,
                    language=chunk.language,
                    symbol_name=chunk.symbol_name,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    score=round(score, 4),
                )
            )
        return sorted(scored, key=lambda result: result.score, reverse=True)[:limit]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator