import os
from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

from alembic import context

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Custom Setup ---
# Add the project root to the Python path so 'models' can be found
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables from .env file
load_dotenv()

# Import your SQLAlchemy models' Base object so that
# autogenerate can see them
from models import Base
target_metadata = Base.metadata

# --------------------

def include_name(name, type_, parent_names):
    if type_ == "table":
        return name in target_metadata.tables
    return True

def get_url():
    """Constructs the database URL from environment variables."""
    DB_USER = os.getenv("DB_USERNAME")
    DB_PASS = os.getenv("DB_PASSWORD")
    DB_HOST = "192.168.0.130" # As requested
    DB_PORT = "5432"          # As requested
    DB_NAME = os.getenv("DB_NAME")

    if not all([DB_USER, DB_PASS, DB_NAME]):
        raise ValueError(
            "Database credentials (DB_USERNAME, DB_PASSWORD, DB_NAME) "
            "are not set in the .env file."
        )
    
    return f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Set the sqlalchemy.url in the config object
    config.set_main_option('sqlalchemy.url', get_url())
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            include_name=include_name
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()