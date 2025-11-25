import asyncio

import openai

from bot.config import settings
from bot.utils.logging import get_logger
from bot.utils.prompt_loader import load_prompt

# Create logger for this module
openai_logger = get_logger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API with comprehensive logging"""

    def __init__(self):
        self.client: openai.AsyncOpenAI | None = None
        self.settings = settings
        self._initialized = False

    async def init_service(self):
        """Initialize OpenAI client with logging"""
        try:
            openai_logger.info("Initializing OpenAI service...")

            if not self.settings.LLM_API_KEY:
                openai_logger.warning("LLM API key not found in settings, skipping OpenAI service initialization")
                return False

            # Use custom API base URL if provided
            client_params = {"api_key": self.settings.LLM_API_KEY}

            if self.settings.LLM_API_URL and self.settings.LLM_API_URL != "https://api.openai.com/v1":
                client_params["base_url"] = self.settings.LLM_API_URL

            self.client = openai.AsyncOpenAI(**client_params)

            # Test the connection
            await self.client.models.list()

            openai_logger.info(f"Using LLM model: {self.settings.LLM_MODEL}")
            if self.settings.LLM_API_URL != "https://api.openai.com/v1":
                openai_logger.info(f"Using custom API URL: {self.settings.LLM_API_URL}")

            self._initialized = True
            openai_logger.success("OpenAI service initialized successfully")
            return True
        except Exception as e:
            openai_logger.error(f"Failed to initialize OpenAI service: {e}")
            return False

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        llm_overrides: dict | None = None,
    ) -> str | None:
        """Create a chat completion with comprehensive logging"""
        # Resolve model/connection parameters
        override_model = llm_overrides.get("model") if llm_overrides else None
        override_api_key = llm_overrides.get("api_key") if llm_overrides else None
        override_base_url = llm_overrides.get("base_url") if llm_overrides else None

        actual_model = override_model or (model if model != "gpt-3.5-turbo" else self.settings.LLM_MODEL)

        # Decide which client to use
        client = self.client
        if override_api_key or override_base_url:
            client_params = {"api_key": override_api_key or self.settings.LLM_API_KEY}
            if override_base_url:
                client_params["base_url"] = override_base_url
            client = openai.AsyncOpenAI(**client_params)

        if not client:
            openai_logger.error("OpenAI client not available (init missing and no overrides provided)")
            return None

        request_id = f"chat_{hash(str(messages)) % 10000}"
        openai_logger.debug(
            f"[{request_id}] Creating chat completion with model {actual_model}"
            + (" using overrides" if llm_overrides else "")
        )

        start_time = asyncio.get_event_loop().time()

        try:
            params = {
                "model": actual_model,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                params["max_tokens"] = max_tokens

            response = await client.chat.completions.create(**params)

            execution_time = asyncio.get_event_loop().time() - start_time
            content = response.choices[0].message.content if response.choices else ""

            if not content or not str(content).strip():
                openai_logger.warning(
                    f"[{request_id}] Empty response from LLM (model={actual_model}, "
                    f"time={execution_time:.3f}s, choices={len(response.choices) if response.choices else 0})"
                )
                return ""
            else:
                openai_logger.success(
                    f"[{request_id}] Chat completion completed in {execution_time:.3f}s using model {actual_model}, response length: {len(content)} chars"
                )

            return content
        except openai.APIError as e:
            openai_logger.error(f"[{request_id}] OpenAI API error: {e}")
            return None
        except Exception as e:
            openai_logger.error(f"[{request_id}] Unexpected error during chat completion: {e}")
            return None

    async def analyze_vacancy(self, vacancy_data: dict) -> str | None:
        """Analyze a vacancy using OpenAI with comprehensive logging"""
        if not self._initialized:
            openai_logger.error("OpenAI service not initialized")
            return None

        request_id = f"analyze_{vacancy_data.get('id', 'unknown')}"
        openai_logger.info(f"[{request_id}] Analyzing vacancy: {vacancy_data.get('name', 'Unknown')}")

        try:
            # Prepare vacancy information for analysis
            vacancy_info = f"""
            Vacancy: {vacancy_data.get("name", "N/A")}
            Company: {vacancy_data.get("employer", {}).get("name", "N/A") if isinstance(vacancy_data.get("employer"), dict) else "N/A"}
            Salary: {vacancy_data.get("salary", "N/A")}
            Area: {vacancy_data.get("area", {}).get("name", "N/A") if isinstance(vacancy_data.get("area"), dict) else "N/A"}
            Experience: {vacancy_data.get("experience", {}).get("name", "N/A") if isinstance(vacancy_data.get("experience"), dict) else "N/A"}
            Employment: {vacancy_data.get("employment", {}).get("name", "N/A") if isinstance(vacancy_data.get("employment"), dict) else "N/A"}
            Schedule: {vacancy_data.get("schedule", {}).get("name", "N/A") if isinstance(vacancy_data.get("schedule"), dict) else "N/A"}
            Description: {vacancy_data.get("description", "N/A")[0:500]}...
            """

            messages = [
                {
                    "role": "system",
                    "content": load_prompt("analyze_vacancy_system"),
                },
                {
                    "role": "user",
                    "content": f"Please analyze this job vacancy:\n\n{vacancy_info}",
                },
            ]

            analysis = await self.chat_completion(messages, model=self.settings.LLM_MODEL, max_tokens=500)

            if analysis:
                openai_logger.success(f"[{request_id}] Vacancy analysis completed successfully")
            else:
                openai_logger.warning(f"[{request_id}] Failed to get vacancy analysis")

            return analysis
        except Exception as e:
            openai_logger.error(f"[{request_id}] Error analyzing vacancy: {e}")
            return None

    async def generate_response_to_user(self, user_query: str, context: str | None = None) -> str | None:
        """Generate a response to user query using OpenAI with comprehensive logging"""
        if not self._initialized:
            openai_logger.error("OpenAI service not initialized")
            return None

        request_id = f"response_{hash(user_query) % 10000}"
        openai_logger.debug(f"[{request_id}] Generating response to user query: {user_query[:50]}...")

        try:
            messages = [
                {
                    "role": "system",
                    "content": load_prompt("user_response_system"),
                }
            ]

            if context:
                messages.append({"role": "system", "content": f"Context: {context}"})

            messages.append({"role": "user", "content": user_query})

            response = await self.chat_completion(messages, model=self.settings.LLM_MODEL, max_tokens=300)

            if response:
                openai_logger.success(f"[{request_id}] User response generated successfully")
            else:
                openai_logger.warning(f"[{request_id}] Failed to generate user response")

            return response
        except Exception as e:
            openai_logger.error(f"[{request_id}] Error generating response to user: {e}")
            return None


# Global OpenAI service instance
openai_service = OpenAIService()


async def test_openai_connection():
    """Test the OpenAI service connection with comprehensive logging"""
    openai_logger.info("Testing OpenAI service connection...")

    try:
        if not openai_service.settings.LLM_API_KEY:
            openai_logger.warning("LLM API key not configured, skipping connection test")
            return False

        if not openai_service._initialized:
            openai_logger.error("OpenAI service not initialized")
            return False

        # Test with a simple completion
        messages = [
            {
                "role": "system",
                "content": "You are a test assistant. Respond with 'test successful' only.",
            },
            {"role": "user", "content": "test"},
        ]

        result = await openai_service.chat_completion(messages, model=openai_service.settings.LLM_MODEL, max_tokens=10)

        if result and "test" in result.lower():
            openai_logger.success("OpenAI service connection test successful")
            return True
        else:
            openai_logger.error(f"OpenAI service connection test failed, received: {result}")
            return False
    except Exception as e:
        openai_logger.error(f"OpenAI service connection test failed with exception: {e}")
        return False
