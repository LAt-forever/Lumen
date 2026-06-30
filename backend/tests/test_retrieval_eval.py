from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.db import Base
from service.models import User
from service.eval.retrieval import (
    load_cases,
    run_retrieval_evaluation,
    seed_retrieval_evaluation_corpus,
)


def test_retrieval_evaluation_seeded_corpus_passes():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    seed_retrieval_evaluation_corpus(db)
    results = run_retrieval_evaluation(db)

    assert db.get(User, 1) is not None
    assert len(results) == len(load_cases())
    assert all(result.passed for result in results)
