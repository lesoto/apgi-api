"""
APGI CLI Commands

Command-line interface for APGI API management tasks.
"""

import logging
import sys

import click

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """APGI API command-line interface."""
    pass


@cli.command()
@click.option("--revision", "-r", default="head", help="Revision to upgrade to")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def migrate(revision: str, verbose: bool):
    """
    Run database migrations.

    Upgrades the database schema to the specified revision.
    """
    try:
        import alembic.config
        from alembic import command

        # Get the alembic configuration
        config = alembic.config.Config("alembic.ini")

        if verbose:
            config.set_main_option("sql", "true")

        # Run the upgrade
        command.upgrade(config, revision)

        logger.info(f"Database migrated to revision: {revision}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--queues", "-Q", default="celery", help="Queues to consume from")
@click.option("--concurrency", "-c", default=1, help="Number of worker processes")
@click.option("--loglevel", "-l", default="info", help="Logging level")
@click.option("--hostname", "-n", help="Worker hostname")
def worker(queues: str, concurrency: int, loglevel: str, hostname: str):
    """
    Start Celery worker.

    Launches a Celery worker process to consume tasks from the specified queues.
    """
    try:
        from app.celery_app import celery_app

        # Prepare worker arguments
        worker_args = [
            "worker",
            f"--queues={queues}",
            f"--concurrency={concurrency}",
            f"--loglevel={loglevel}",
        ]

        if hostname:
            worker_args.append(f"--hostname={hostname}")

        # Start the worker
        logger.info(f"Starting Celery worker with args: {worker_args}")
        celery_app.start(worker_args)

    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--users", "-u", default=10, help="Number of users to create")
@click.option("--templates", "-t", default=5, help="Number of templates to create")
@click.option("--sessions", "-s", default=20, help="Number of sessions to create")
@click.option("--tasks", "-T", default=50, help="Number of tasks to create")
@click.option("--clear", "-c", is_flag=True, help="Clear existing test data first")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def seed(users: int, templates: int, sessions: int, tasks: int, clear: bool, verbose: bool):
    """
    Seed database with test data.

    Creates realistic test data for development and testing purposes.
    """
    try:
        from app.services.seeding_service import DatabaseSeedingService
        from app.database.connection import init_db

        # Initialize database
        init_db()

        # Create seeding service
        seeder = DatabaseSeedingService()

        if clear:
            if verbose:
                logger.info("Clearing existing test data...")
            cleared = seeder.clear_all_data()
            if verbose:
                logger.info(f"Cleared: {cleared}")

        if verbose:
            logger.info(
                f"Seeding database with {users} users, {templates} templates, {sessions} sessions, {tasks} tasks..."
            )

        # Seed all data
        result = seeder.seed_all(
            user_count=users, template_count=templates, session_count=sessions, task_count=tasks
        )

        logger.info("Database seeding completed successfully")
        if verbose:
            for key, value in result.items():
                if isinstance(value, list) and len(value) > 5:
                    logger.info(f"{key}: {len(value)} items created")
                else:
                    logger.info(f"{key}: {value}")

    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--confirm", is_flag=True, help="Confirm clearing of all test data")
def clear_seed_data(confirm: bool):
    """
    Clear all seeded test data from database.

    Removes all test users, sessions, templates, tasks, and dependencies.
    """
    if not confirm:
        logger.error("Use --confirm flag to actually clear the data")
        logger.info(
            "This will delete all test data matching patterns like 'user_*', 'session_*', etc."
        )
        sys.exit(1)

    try:
        from app.services.seeding_service import DatabaseSeedingService
        from app.database.connection import init_db

        # Initialize database
        init_db()

        # Create seeding service
        seeder = DatabaseSeedingService()

        logger.info("Clearing all seeded test data...")
        cleared = seeder.clear_all_data()

        logger.info("Test data cleared successfully")
        for table, count in cleared.items():
            logger.info(f"  {table}: {count} records deleted")

    except Exception as e:
        logger.error(f"Clearing failed: {e}")
        sys.exit(1)
