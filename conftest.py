from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from codeteam.database import Base


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as database_session:
        yield database_session
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "sample-repo"
    repository.mkdir()
    (repository / "auth.py").write_text(
        "class TokenService:\n"
        "    def validate_token(self, token: str) -> bool:\n"
        "        return token == 'valid-token'\n\n"
        "def authenticate(token: str) -> bool:\n"
        "    return TokenService().validate_token(token)\n",
        encoding="utf-8",
    )
    (repository / "test_auth.py").write_text(
        "from auth import authenticate\n\n"
        "def test_authenticate_rejects_invalid_token():\n"
        "    assert not authenticate('invalid')\n",
        encoding="utf-8",
    )
    (repository / "README.md").write_text(
        "# Sample authentication service\n",
        encoding="utf-8",
    )
    return repository
