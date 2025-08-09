# src/dashboard/db_utils.py
from sqlalchemy import create_engine, text

def _to_sqlalchemy_url(db: str) -> str:
    # якщо вже URL — лишаємо
    if "://" in db:
        return db
    # інакше вважаємо, що це шлях до файлу
    return f"sqlite:///{db}"

def update_opportunity_status(db, opportunity_id, new_status):
    """Оновлює поле manual_status для ОДНІЄЇ можливості."""
    try:
        engine = create_engine(_to_sqlalchemy_url(db))
        with engine.connect() as connection:
            stmt = text("UPDATE opportunities SET manual_status = :status WHERE id = :id")
            connection.execute(stmt, {"status": new_status, "id": opportunity_id})
            connection.commit()
            return True
    except Exception as e:
        print(f"Помилка при оновленні статусу: {e}")
        return False

def update_opportunities_status_bulk(db, opportunity_ids, new_status):
    """Масове оновлення manual_status для списку ID."""
    if not opportunity_ids:
        return True
    try:
        engine = create_engine(_to_sqlalchemy_url(db))
        with engine.connect() as connection:
            placeholders = ", ".join([f":id_{i}" for i in range(len(opportunity_ids))])
            stmt = text(f"UPDATE opportunities SET manual_status = :status WHERE id IN ({placeholders})")
            params = {"status": new_status} | {f"id_{i}": v for i, v in enumerate(opportunity_ids)}
            connection.execute(stmt, params)
            connection.commit()
            return True
    except Exception as e:
        print(f"Помилка при масовому оновленні статусів: {e}")
        return False
