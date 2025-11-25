import asyncio
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings
from bot.utils.logging import get_logger

logger = get_logger(__name__)

engine = None
SessionLocal = None


async def init_database():
    global engine, SessionLocal

    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("No DATABASE_URL provided")
        return False

    # Replace postgres:// or postgresql:// with postgresql+asyncpg://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Parse URL to extract query parameters for connect_args
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

    logger.info(f"Connecting to Neon at: {db_url_clean.split('@')[-1].split('/')[0]}")

    engine = create_async_engine(
        db_url_clean,
        echo=False,
        pool_size=3,  # Neon-friendly
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=180,
        connect_args=connect_args if connect_args else {},
    )

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Try connecting (Neon cold start → retry)
    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.success("Connected to Neon successfully")
            return True
        except OperationalError as e:
            logger.warning(f"Neon cold start, retrying {attempt + 1}/5: {e}")
            await asyncio.sleep(1.5)

    logger.error("Failed to connect to Neon after retries")
    return False


async def close_database():
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def get_db_session() -> AsyncSession:
    if not SessionLocal:
        logger.error("SessionLocal not initialized")
        return None
    return SessionLocal()
