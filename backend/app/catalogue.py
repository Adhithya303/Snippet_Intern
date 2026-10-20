from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import Product


def list_products(session: Session, category=None, max_price_paise=None, page=1, page_size=12):
    filters = []
    if category is not None:
        filters.append(Product.category == category)
    if max_price_paise is not None:
        filters.append(Product.price_paise <= max_price_paise)
    total = session.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
    statement = (select(Product).where(*filters)
                 .order_by(Product.price_paise.asc(), Product.id.asc())
                 .offset((page - 1) * page_size).limit(page_size))
    return list(session.scalars(statement)), total
