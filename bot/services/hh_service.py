import asyncio

import httpx

from bot.utils.logging import get_logger

# Create logger for this module
hh_logger = get_logger(__name__)


class HHService:
    """Service for interacting with HH.ru API with comprehensive logging"""

    def __init__(self):
        self.base_url = "https://api.hh.ru"
        self.session: httpx.AsyncClient | None = None

    async def __aenter__(self):
        await self.init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()

    async def init_session(self):
        """Initialize HTTP client session with logging"""
        try:
            hh_logger.info("Initializing HH.ru API session...")
            self.session = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={"User-Agent": "HH-Bot/1.0 (Educational Project)"},
            )
            hh_logger.success("HH.ru API session initialized successfully")
        except Exception as e:
            hh_logger.error(f"Failed to initialize HH.ru API session: {e}")
            raise

    async def close_session(self):
        """Close HTTP client session with logging"""
        if self.session:
            try:
                hh_logger.info("Closing HH.ru API session...")
                await self.session.aclose()
                hh_logger.success("HH.ru API session closed successfully")
            except Exception as e:
                hh_logger.error(f"Error closing HH.ru API session: {e}")

    async def search_vacancies(
        self,
        text: str,
        area: str | None = None,
        page: int = 0,
        per_page: int = 20,
        search_in_name_only: bool = False,
        min_salary: int | None = None,
        remote_only: bool | None = None,
        freshness_days: int | None = None,
        employment: str | None = None,
        experience: str | None = None,
    ) -> dict | None:
        """Search for vacancies with comprehensive logging

        Args:
            text: Search query text
            area: Area/region code (optional)
            page: Page number (0-based)
            per_page: Number of results per page
            search_in_name_only: If True, search only in vacancy names using 'name:' prefix
            min_salary: Minimum salary filter
            remote_only: If True, filter only remote jobs
            freshness_days: Only vacancies published in last N days (HH 'period' param)
            employment: Employment type (full, part, project, volunteer, probation)
            experience: Experience level (no_experience, between1And3, between3And6, moreThan6)
        """
        if not self.session:
            hh_logger.error("HTTP session not initialized")
            return None

        # If search_in_name_only is True, wrap the query with 'name:' prefix
        search_text = f"name:{text}" if search_in_name_only else text

        request_id = f"search_{hash(search_text + str(page)) % 100}"
        hh_logger.info(f"[{request_id}] Searching for vacancies: '{search_text}' (page {page}, per_page {per_page})")

        start_time = asyncio.get_event_loop().time()

        try:
            params = {"text": search_text, "page": page, "per_page": per_page}

            if area:
                params["area"] = area
            if min_salary is not None:
                params["salary"] = min_salary
                params["only_with_salary"] = True
            if remote_only:
                params["schedule"] = "remote"
            if freshness_days:
                params["period"] = freshness_days
            if employment:
                params["employment"] = employment
            if experience:
                params["experience"] = experience

            response = await self.session.get("/vacancies", params=params)
            response.raise_for_status()

            result = response.json()
            execution_time = asyncio.get_event_loop().time() - start_time

            hh_logger.success(
                f"[{request_id}] Search completed in {execution_time:.3f}s, found {result.get('found', 0)} vacancies"
            )

            return result
        except httpx.HTTPStatusError as e:
            hh_logger.error(f"[{request_id}] HTTP error during vacancy search: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            hh_logger.error(f"[{request_id}] Request error during vacancy search: {e}")
            return None
        except Exception as e:
            hh_logger.error(f"[{request_id}] Unexpected error during vacancy search: {e}")
            return None

    async def get_vacancy(self, vacancy_id: str) -> dict | None:
        """Get detailed information about a specific vacancy with logging"""
        if not self.session:
            hh_logger.error("HTTP session not initialized")
            return None

        request_id = f"vacancy_{vacancy_id}"
        hh_logger.debug(f"[{request_id}] Fetching vacancy details...")

        start_time = asyncio.get_event_loop().time()

        try:
            response = await self.session.get(f"/vacancies/{vacancy_id}")
            response.raise_for_status()

            result = response.json()
            execution_time = asyncio.get_event_loop().time() - start_time

            hh_logger.success(f"[{request_id}] Vacancy details fetched in {execution_time:.3f}s")

            return result
        except httpx.HTTPStatusError as e:
            hh_logger.error(f"[{request_id}] HTTP error fetching vacancy: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            hh_logger.error(f"[{request_id}] Request error fetching vacancy: {e}")
            return None
        except Exception as e:
            hh_logger.error(f"[{request_id}] Unexpected error fetching vacancy: {e}")
            return None

    async def get_areas(self) -> list[dict] | None:
        """Get list of available areas with logging"""
        if not self.session:
            hh_logger.error("HTTP session not initialized")
            return None

        request_id = "areas"
        hh_logger.debug(f"[{request_id}] Fetching available areas...")

        start_time = asyncio.get_event_loop().time()

        try:
            response = await self.session.get("/areas")
            response.raise_for_status()

            result = response.json()
            execution_time = asyncio.get_event_loop().time() - start_time

            area_count = len(result) if isinstance(result, list) else 0
            hh_logger.success(f"[{request_id}] Areas fetched in {execution_time:.3f}s, found {area_count} areas")

            return result
        except httpx.HTTPStatusError as e:
            hh_logger.error(f"[{request_id}] HTTP error fetching areas: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            hh_logger.error(f"[{request_id}] Request error fetching areas: {e}")
            return None
        except Exception as e:
            hh_logger.error(f"[{request_id}] Unexpected error fetching areas: {e}")
            return None

    async def find_area_by_name(self, city_name: str) -> str | None:
        """Find HH.ru area ID by city name. Returns area ID or None."""
        if not self.session:
            hh_logger.error("HTTP session not initialized")
            return None

        try:
            # Get all areas
            areas = await self.get_areas()
            if not areas:
                return None

            # Recursive function to search in nested areas
            def search_area(area_list: list[dict], name: str) -> str | None:
                for area in area_list:
                    # Check if area name matches (case-insensitive)
                    if area.get("name", "").lower() == name.lower():
                        return str(area.get("id"))
                    # Search in sub-areas
                    if "areas" in area and area["areas"]:
                        result = search_area(area["areas"], name)
                        if result:
                            return result
                return None

            area_id = search_area(areas, city_name)
            if area_id:
                hh_logger.info(f"Found area ID {area_id} for city '{city_name}'")
            else:
                hh_logger.warning(f"Area not found for city '{city_name}'")
            return area_id
        except Exception as e:
            hh_logger.error(f"Error finding area for city '{city_name}': {e}")
            return None

    async def get_employer(self, employer_id: str) -> dict | None:
        """Get employer information with logging"""
        if not self.session:
            hh_logger.error("HTTP session not initialized")
            return None

        request_id = f"employer_{employer_id}"
        hh_logger.debug(f"[{request_id}] Fetching employer details...")

        start_time = asyncio.get_event_loop().time()

        try:
            response = await self.session.get(f"/employers/{employer_id}")
            response.raise_for_status()

            result = response.json()
            execution_time = asyncio.get_event_loop().time() - start_time

            hh_logger.success(f"[{request_id}] Employer details fetched in {execution_time:.3f}s")

            return result
        except httpx.HTTPStatusError as e:
            hh_logger.error(f"[{request_id}] HTTP error fetching employer: {e.response.status_code} - {e}")
            return None
        except httpx.RequestError as e:
            hh_logger.error(f"[{request_id}] Request error fetching employer: {e}")
            return None
        except Exception as e:
            hh_logger.error(f"[{request_id}] Unexpected error fetching employer: {e}")
            return None


# Global HH service instance
hh_service = HHService()
