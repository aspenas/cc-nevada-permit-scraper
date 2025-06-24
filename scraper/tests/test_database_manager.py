from sqlalchemy import text
from scraper.database.manager import DatabaseManager
from scraper.database.unified_schema import Permit, Base


def test_database_manager_sqlite():
    db_manager = DatabaseManager('sqlite:///:memory:')
    with db_manager.engine.connect() as conn:
        conn.execute(text('PRAGMA foreign_keys=ON'))
    # Create tables
    Base.metadata.create_all(db_manager.engine)
    # Insert a permit
    session = db_manager.SessionLocal()
    permit = Permit(permit_number='TEST-123', status='Open')
    session.add(permit)
    session.commit()
    # Retrieve the permit
    result = session.query(Permit).filter_by(permit_number='TEST-123').first()
    assert result is not None
    assert result.permit_number == 'TEST-123'
    session.close() 