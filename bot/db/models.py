from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_user_id = Column(String(50), unique=True, nullable=False, index=True)  # Telegram user ID
    username = Column(String(100), nullable=True)  # Telegram username
    first_name = Column(String(100), nullable=True)  # Telegram first name
    last_name = Column(String(100), nullable=True)  # Telegram last name
    language_code = Column(String(10), nullable=True)  # Language code
    city = Column(String(100), nullable=True)  # User's preferred city for job search
    hh_area_id = Column(String(20), nullable=True)  # HH.ru area ID for the city
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    preferences = Column(JSON, default={})  # User preferences as JSON


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)  # Foreign key to users table
    query_text = Column(Text, nullable=False)  # The search query
    search_params = Column(JSON, default={})  # Search parameters as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    results_count = Column(Integer, default=0)  # Number of results returned
    response_time = Column(Integer, nullable=True)  # Response time in milliseconds


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hh_vacancy_id = Column(String(50), unique=True, nullable=False, index=True)  # HH.ru vacancy ID
    title = Column(String(500), nullable=False)  # Job title
    company = Column(String(200), nullable=True)  # Company name
    salary_from = Column(Integer, nullable=True)  # Minimum salary
    salary_to = Column(Integer, nullable=True)  # Maximum salary
    salary_currency = Column(String(10), nullable=True)  # Currency code
    location = Column(String(200), nullable=True)  # Job location
    description = Column(Text, nullable=True)  # Job description
    requirements = Column(Text, nullable=True)  # Job requirements
    experience = Column(String(100), nullable=True)  # Required experience
    employment_type = Column(String(100), nullable=True)  # Employment type (full-time, part-time, etc.)
    schedule = Column(String(100), nullable=True)  # Work schedule
    url = Column(String(500), nullable=True)  # Link to the job on HH.ru
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)  # Whether the vacancy is still active


class UserSearchResult(Base):
    __tablename__ = "user_search_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)  # Foreign key to users table
    search_query_id = Column(Integer, nullable=False, index=True)  # Foreign key to search_queries table
    vacancy_id = Column(Integer, nullable=False, index=True)  # Foreign key to vacancies table
    position = Column(Integer, nullable=False)  # Position in search results
    clicked = Column(Boolean, default=False)  # Whether the user clicked on this result
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CV(Base):
    __tablename__ = "cv"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    vacancy_id = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
