#!/usr/bin/env python3
"""
Script to clear all data from the database by deleting all rows from all tables.
"""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from bot.config import settings


async def clear_database():
    """Clear all data from the database."""
    db_url = settings.DATABASE_URL
    if not db_url:
        print("Error: No DATABASE_URL provided in settings")
        return False

    # Replace postgres:// or postgresql:// with postgresql+asyncpg:// for async operations
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Parse URL to extract query parameters for connect_args (similar to database.py)
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)

    # Extract SSL-related parameters for asyncpg connect_args
    connect_args = {}
    ssl_params = ["sslmode", "sslcert", "sslkey", "sslrootcert"]
    remaining_params = {}

    for key, value_list in query_params.items():
        if key.lower() in ssl_params:
            # asyncpg uses 'ssl' parameter (boolean or SSL context), not 'sslmode'
            if key.lower() == "sslmode":
                # Convert sslmode to asyncpg's ssl parameter
                sslmode = value_list[0].lower()
                if sslmode in ["require", "prefer"]:
                    # For asyncpg, ssl=True enables SSL
                    connect_args["ssl"] = True
                elif sslmode == "allow":
                    # 'allow' means try SSL but fallback to non-SSL
                    connect_args["ssl"] = "allow"
                # 'disable' means no SSL, so we don't set it
            else:
                # Other SSL parameters can be passed through
                connect_args[key.lower()] = value_list[0]
        else:
            remaining_params[key] = value_list[0]

    # Rebuild URL without SSL parameters (they'll be in connect_args)
    if remaining_params:
        new_query = urlencode(remaining_params)
        parsed = parsed._replace(query=new_query)
    else:
        parsed = parsed._replace(query="")

    db_url_clean = urlunparse(parsed)

    engine = create_async_engine(db_url_clean, connect_args=connect_args if connect_args else {})

    try:
        async with engine.begin() as conn:
            # Get all table names
            result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public';"))
            tables = [row[0] for row in result.fetchall()]

            print(f"Found tables: {tables}")

            # Delete all data from each table
            # We'll handle foreign key constraints by deleting tables in the correct order
            # or temporarily disabling them if we have sufficient privileges
            try:
                # Try to disable foreign key checks temporarily
                await conn.execute(text("SET session_replication_role = replica;"))

                # Delete all data from each table
                for table in tables:
                    if table != "alembic_version":  # Skip alembic version table to preserve migration history
                        print(f"Clearing table: {table}")
                        await conn.execute(text(f"DELETE FROM {table};"))

                # Re-enable foreign key checks
                await conn.execute(text("SET session_replication_role = DEFAULT;"))
            except Exception as e:
                print(f"Could not disable foreign key checks: {e}")
                print("Attempting to delete tables in dependency order...")

                # Since the transaction is aborted, we need to rollback and start fresh transactions
                await conn.execute(text("ROLLBACK;"))

                # If we can't disable foreign key checks, try deleting in order that respects dependencies
                # The order should be from child tables to parent tables:
                # 1. user_search_results (depends on users, search_queries, vacancies)
                # 2. search_queries (depends on users)
                # 3. vacancies (no dependencies)
                # 4. users (no dependencies)

                ordered_tables = [
                    "user_search_results",
                    "search_queries",
                    "vacancies",
                    "users",
                ]

                for table in ordered_tables:
                    if table in tables and table != "alembic_version":
                        print(f"Clearing table: {table}")
                        await conn.execute(text("BEGIN;"))
                        await conn.execute(text(f"DELETE FROM {table};"))
                        await conn.execute(text("COMMIT;"))

                # Handle any remaining tables
                for table in tables:
                    if table not in ordered_tables and table != "alembic_version":
                        print(f"Clearing table: {table}")
                        await conn.execute(text("BEGIN;"))
                        await conn.execute(text(f"DELETE FROM {table};"))
                        await conn.execute(text("COMMIT;"))

                print("Note: alembic_version table was preserved to maintain migration history")

                print("Database cleared successfully!")
                return True

    except Exception as e:
        print(f"Error clearing database: {e}")
        return False
    finally:
        await engine.dispose()


def main():
    """Main function to run the database clearing script."""
    print("Starting database clearing process...")

    success = asyncio.run(clear_database())

    if success:
        print("Database has been successfully cleared!")
        sys.exit(0)
    else:
        print("Failed to clear database!")
        sys.exit(1)


if __name__ == "__main__":
    main()
