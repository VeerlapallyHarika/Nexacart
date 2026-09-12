from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def run_migrations():
    """Apply lightweight, idempotent schema migrations for existing databases.

    ``Base.metadata.create_all`` only creates missing tables; it does NOT add
    columns to tables that already exist. For an existing ``nexacart.db`` we must
    add new columns explicitly. The check-then-ALTER is safe to run repeatedly
    and is a no-op once the column/table exists.
    """
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        cols = {
            row[1] for row in conn.execute(
                text("PRAGMA table_info(audit_events)")
            ).fetchall()
        }
        if "decision_id" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE audit_events "
                    "ADD COLUMN decision_id VARCHAR(50)"
                )
            )

        # Drop old unique index on decision_traces.session_id if present
        try:
            conn.execute(text("DROP INDEX IF EXISTS ix_decision_traces_session_id"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_decision_traces_session_id ON decision_traces (session_id)"))
        except Exception:
            pass

        # Ensure decision_simulations table exists (created by create_all on
        # fresh databases, but explicit CREATE IF NOT EXISTS is harmless).
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS decision_simulations ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "simulation_id VARCHAR(50) UNIQUE NOT NULL,"
                "decision_id VARCHAR(50) NOT NULL,"
                "session_id VARCHAR(100) NOT NULL,"
                "simulation_number INTEGER DEFAULT 1,"
                "label TEXT,"
                "original_constraints JSON,"
                "modified_constraints JSON,"
                "result JSON,"
                "contract_warnings JSON,"
                "status VARCHAR(30) DEFAULT 'COMPLETED',"
                "created_at VARCHAR(50)"
                ")"
            )
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
