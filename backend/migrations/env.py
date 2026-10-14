from logging.config import fileConfig

from alembic import context

# Register every table on Base.metadata.
from app.core import household  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base, get_engine
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.consent import models as consent_models  # noqa: F401
from app.modules.lesson_delivery import models as lesson_models  # noqa: F401
from app.session_log import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
