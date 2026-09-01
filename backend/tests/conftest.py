import os
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_path}"

from backend.main import app as flask_app, engine  # noqa: E402
from backend.models import Base  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.create_all(engine)
    with flask_app.test_client() as test_client:
        yield test_client
    Base.metadata.drop_all(engine)