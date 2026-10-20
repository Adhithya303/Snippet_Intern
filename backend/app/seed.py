"""Idempotently insert missing synthetic records; never overwrite user edits."""
import json
from sqlalchemy.orm import Session
from .config import PROJECT_ROOT, Settings
from .database import Base, make_engine
from .models import Product
from .schemas import ProductOut


def read_seed():
    raw = json.loads((PROJECT_ROOT / "data" / "products.json").read_text(encoding="utf-8"))
    items = [ProductOut.model_validate(item) for item in raw]
    if len({p.id for p in items}) != len(items):
        raise ValueError("Seed product IDs must be unique")
    return items


def seed(session: Session):
    inserted = 0
    for item in read_seed():
        if session.get(Product, item.id) is None:
            session.add(Product(**item.model_dump()))
            inserted += 1
    session.commit()
    return inserted


def main():
    engine = make_engine(Settings().database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        count = seed(session)
    engine.dispose()
    print(f"Database initialized. Inserted {count} synthetic products. Existing records preserved.")


if __name__ == "__main__":
    main()
