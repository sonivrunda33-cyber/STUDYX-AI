from logging.config import fileConfig

from alembic import context
from flask import current_app


config = context.config
config.set_main_option(
    "sqlalchemy.url",
    current_app.extensions["migrate"].db.engine.url.render_as_string(hide_password=False).replace("%", "%%"),
)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = current_app.extensions["migrate"].db.metadata


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connection = current_app.extensions["migrate"].db.engine.connect()
    try:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
