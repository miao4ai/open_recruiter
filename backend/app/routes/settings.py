"""Settings routes — API key management, config."""

from fastapi import APIRouter, Depends

from app.auth import get_current_user
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
        gemini_api_key=db.get("gemini_api_key", env.gemini_api_key),
        email_backend=db.get("email_backend", env.email_backend),
        sendgrid_api_key=db.get("sendgrid_api_key", env.sendgrid_api_key),
        email_from=db.get("email_from", env.email_from),
        smtp_host=db.get("smtp_host", env.smtp_host),
        smtp_port=int(db.get("smtp_port", str(env.smtp_port))),
        smtp_username=db.get("smtp_username", env.smtp_username),
        smtp_password=db.get("smtp_password", env.smtp_password),
        recruiter_name=db.get("recruiter_name", ""),
        recruiter_email=db.get("recruiter_email", ""),
        recruiter_company=db.get("recruiter_company", ""),
        imap_host=db.get("imap_host", env.imap_host),
        imap_port=int(db.get("imap_port", str(env.imap_port))),
        imap_username=db.get("imap_username", env.imap_username),
        imap_password=db.get("imap_password", env.imap_password),
        slack_bot_token=db.get("slack_bot_token", env.slack_bot_token),
        slack_app_token=db.get("slack_app_token", env.slack_app_token),
        slack_signing_secret=db.get("slack_signing_secret", env.slack_signing_secret),
        slack_intake_channel=db.get("slack_intake_channel", env.slack_intake_channel),
    )


def get_config() -> Config:
    """Public helper used by other routes to get the active config."""
    return _build_config()


@router.get("/setup-status")
async def setup_status(current_user: dict = Depends(get_current_user)):
    """Check if LLM is configured — used by the onboarding flow."""
    cfg = _build_config()
    provider = cfg.llm_provider
    key_map = {
        "anthropic": cfg.anthropic_api_key,
        "openai": cfg.openai_api_key,
        "gemini": cfg.gemini_api_key,
    }
    has_key = bool(key_map.get(provider, ""))
    has_model = bool(cfg.llm_model)
    return {
        "llm_configured": has_key and has_model,
        "llm_provider": provider,
        "llm_model": cfg.llm_model,
        "has_api_key": has_key,
    }


@router.get("", response_model=Settings)
async def get_settings_route(current_user: dict = Depends(get_current_user)):
    cfg = _build_config()
    # Override email_from and recruiter_email with logged-in user's email
    user_email = current_user["email"]
    return Settings(
        llm_provider=cfg.llm_provider,
        llm_model=cfg.llm_model,
        anthropic_api_key=cfg.anthropic_api_key,
        openai_api_key=cfg.openai_api_key,
        gemini_api_key=cfg.gemini_api_key,
        email_backend=cfg.email_backend,
        sendgrid_api_key=cfg.sendgrid_api_key,
        email_from=user_email,
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_username=cfg.smtp_username,
        smtp_password=cfg.smtp_password,
        recruiter_name=cfg.recruiter_name or current_user.get("name", ""),
        recruiter_email=user_email,
        recruiter_company=cfg.recruiter_company,
        imap_host=cfg.imap_host,
        imap_port=cfg.imap_port,
        imap_username=cfg.imap_username,
        imap_password=cfg.imap_password,
        slack_bot_token=cfg.slack_bot_token,
        slack_app_token=cfg.slack_app_token,
        slack_signing_secret=cfg.slack_signing_secret,
        slack_intake_channel=cfg.slack_intake_channel,
    )


@router.put("")
async def update_settings(s: Settings, _user: dict = Depends(get_current_user)):
    data = s.model_dump()
    # Store all non-empty values; convert non-str to str for DB
    to_store = {k: str(v) for k, v in data.items() if v}
    put_settings(to_store)
    return {"status": "ok"}


@router.post("/test-llm")
async def test_llm(_user: dict = Depends(get_current_user)):
    """Quick connectivity test for the LLM."""
    cfg = _build_config()
    try:
        from app.llm import chat
        resp = chat(cfg, "You are a test bot.", [{"role": "user", "content": "Say hello in one word."}])
        return {"status": "ok", "response": resp.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test-email")
async def test_email(current_user: dict = Depends(get_current_user)):
    """Test email connectivity."""
    cfg = _build_config()
    from app.tools.email_sender import send_email as do_send
    result = do_send(
        backend=cfg.email_backend,
        from_email=current_user["email"],
        to_email=current_user["email"],
        subject="Open Recruiter — Test Email",
        body="This is a test email from Open Recruiter. If you received this, your email is configured correctly!",
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_username=cfg.smtp_username,
        smtp_password=cfg.smtp_password,
    )
    return result


@router.post("/test-slack")
async def test_slack(_user: dict = Depends(get_current_user)):
    """Quick connectivity test for the Slack bot."""
    cfg = _build_config()
    if not cfg.slack_bot_token:
        return {"status": "error", "message": "Slack bot token not configured."}
    try:
        from slack_sdk.web.async_client import AsyncWebClient
        client = AsyncWebClient(token=cfg.slack_bot_token)
        resp = await client.auth_test()
        return {
            "status": "ok",
            "bot_user": resp.get("user"),
            "team": resp.get("team"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
