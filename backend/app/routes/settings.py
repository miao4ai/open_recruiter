"""Settings routes — API key management, config."""

from fastapi import APIRouter

from app.config import Config, load_config_from_env
from app.database import get_settings, put_settings
from app.models import Settings

router = APIRouter()


def _build_config() -> Config:
    """Build Config from DB settings, falling back to env vars."""
    db = get_settings()
    env = load_config_from_env()
    return Config(
        llm_provider=db.get("llm_provider", env.llm_provider),
        llm_model=db.get("llm_model", env.llm_model),
        anthropic_api_key=db.get("anthropic_api_key", env.anthropic_api_key),
        openai_api_key=db.get("openai_api_key", env.openai_api_key),
        email_backend=db.get("email_backend", env.email_backend),
        sendgrid_api_key=db.get("sendgrid_api_key", env.sendgrid_api_key),
        email_from=db.get("email_from", env.email_from),
        recruiter_name=db.get("recruiter_name", ""),
        recruiter_email=db.get("recruiter_email", ""),
        recruiter_company=db.get("recruiter_company", ""),
    )


def get_config() -> Config:
    """Public helper used by other routes to get the active config."""
    return _build_config()


@router.get("", response_model=Settings)
async def get_settings_route():
    cfg = _build_config()
    return Settings(
        llm_provider=cfg.llm_provider,
        llm_model=cfg.llm_model,
        anthropic_api_key=cfg.anthropic_api_key,
        openai_api_key=cfg.openai_api_key,
        email_backend=cfg.email_backend,
        sendgrid_api_key=cfg.sendgrid_api_key,
        email_from=cfg.email_from,
        recruiter_name=cfg.recruiter_name,
        recruiter_email=cfg.recruiter_email,
        recruiter_company=cfg.recruiter_company,
    )


@router.put("")
async def update_settings(s: Settings):
    data = s.model_dump()
    # Store all non-empty values
    to_store = {k: v for k, v in data.items() if v}
    put_settings(to_store)
    return {"status": "ok"}


@router.post("/test-llm")
async def test_llm():
    """Quick connectivity test for the LLM."""
    cfg = _build_config()
    try:
        from app.llm import chat
        resp = chat(cfg, "You are a test bot.", [{"role": "user", "content": "Say hello in one word."}])
        return {"status": "ok", "response": resp.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test-email")
async def test_email():
    """Placeholder for email connectivity test."""
    cfg = _build_config()
    return {"status": "ok", "backend": cfg.email_backend, "message": "Email test not yet implemented."}
