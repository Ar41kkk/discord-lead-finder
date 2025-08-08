# src/dashboard/db_utils.py

from sqlalchemy import create_engine, text


def update_opportunity_status(db_path, opportunity_id, new_status):
    """Оновлює поле manual_status для ОДНІЄЇ можливості в базі даних."""
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.connect() as connection:
            stmt = text("UPDATE opportunities SET manual_status = :status WHERE id = :id")
            connection.execute(stmt, {"status": new_status, "id": opportunity_id})
            connection.commit()
            return True
    except Exception as e:
        print(f"Помилка при оновленні статусу: {e}")
        return False


def update_opportunities_status_bulk(db_path, opportunity_ids, new_status):
    """Оновлює поле manual_status для СПИСКУ можливостей (масове оновлення)."""
    if not opportunity_ids:
        return True  # Нічого оновлювати, вважаємо успіхом
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.connect() as connection:
            # Створюємо плейсхолдери для безпечної передачі списку ID
            placeholders = ', '.join([':id_' + str(i) for i in range(len(opportunity_ids))])
            stmt = text(f"UPDATE opportunities SET manual_status = :status WHERE id IN ({placeholders})")

            # Створюємо словник параметрів
            params = {"status": new_status}
            for i, opp_id in enumerate(opportunity_ids):
                params['id_' + str(i)] = opp_id

            connection.execute(stmt, params)
            connection.commit()
            return True
    except Exception as e:
        print(f"Помилка при масовому оновленні статусів: {e}")
        return False