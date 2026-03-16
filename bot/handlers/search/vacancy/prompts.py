from bot.db import CVType
from bot.utils.prompt_loader import load_prompt
from bot.utils.search import format_vacancy_details


def build_cv_prompt(
    vacancy: dict,
    user_resume: str | None,
    user_skills: list[str] | None,
    user_contacts: str | None,
    user_prompt: str | None = None,
    candidate_name: str | None = None,
    lang: str = "en",
) -> list[dict[str, str]]:
    vacancy_text = format_vacancy_details(vacancy, 1, 1, lang)
    skills_text = ", ".join(user_skills or [])
    resume_text = user_resume or ""

    prompt_template = load_prompt("cv_prompt")
    extra = f"\nUser additional requirements: {user_prompt}" if user_prompt else ""
    prompt = prompt_template.format(user_prompt_extra=extra)

    user_context_parts = []
    if candidate_name:
        user_context_parts.append(f"Candidate name: {candidate_name}")
    if user_contacts:
        user_context_parts.append(f"Candidate contacts:\n{user_contacts}")
    user_context_parts.append(
        f"User skills: {skills_text}" if skills_text else "User skills not provided"
    )
    if resume_text:
        user_context_parts.append(f"User base resume:\n{resume_text}")
    user_context = "\n".join(user_context_parts)

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Вакансия:\n{vacancy_text}\n\n{user_context}"},
    ]


def build_cover_letter_prompt(
    vacancy: dict,
    user_resume: str | None,
    user_skills: list[str] | None,
    user_contacts: str | None,
    user_prompt: str | None = None,
    candidate_name: str | None = None,
    lang: str = "en",
) -> list[dict[str, str]]:
    vacancy_text = format_vacancy_details(vacancy, 1, 1, lang)
    skills_text = ", ".join(user_skills or [])
    resume_text = user_resume or ""

    prompt_template = load_prompt("cover_letter_prompt")
    extra = f"\nUser additional requirements: {user_prompt}" if user_prompt else ""
    prompt = prompt_template.format(user_prompt_extra=extra)

    context_parts = []
    if candidate_name:
        context_parts.append(f"Candidate name: {candidate_name}")
    if skills_text:
        context_parts.append(f"User skills: {skills_text}")
    if resume_text:
        context_parts.append(f"User short resume:\n{resume_text}")

    user_context = (
        "\n".join(context_parts) if context_parts else "User skills not provided"
    )

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Вакансия:\n{vacancy_text}\n\n{user_context}"},
    ]


DOCUMENT_META = {
    CVType.CV: {
        "generating_key": "search.vacancy_detail.generating",
        "empty_key": "search.vacancy_detail.cv_empty",
        "no_cache_key": "search.vacancy_detail.cv_no_cache",
        "failed_key": "search.vacancy_detail.cv_failed",
        "prompt_builder": build_cv_prompt,
        "max_tokens": 700,
    },
    CVType.COVER_LETTER: {
        "generating_key": "search.vacancy_detail.generating_cover_letter",
        "empty_key": "search.vacancy_detail.cover_letter_empty",
        "no_cache_key": "search.vacancy_detail.cover_letter_no_cache",
        "failed_key": "search.vacancy_detail.cover_letter_failed",
        "prompt_builder": build_cover_letter_prompt,
        "max_tokens": 350,
    },
}
