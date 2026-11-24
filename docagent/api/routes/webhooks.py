"""GitHub Webhook API route handler with signature verification and event dispatching."""

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel
from typing import Any, Dict, Optional

from docagent.core.config import settings
from docagent.core.exceptions import WebhookVerificationError
from docagent.core.logging import logger
from docagent.integrations.github_app import GitHubAppClient
from docagent.orchestration.workflow import build_docagent_graph

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
github_client = GitHubAppClient()


def process_github_event_background(
    event_type: str,
    delivery_id: str,
    payload: Dict[str, Any]
) -> None:
    """Background processor for GitHub webhook events."""
    logger.info(f"Processing GitHub event: {event_type} (Delivery: {delivery_id})")
    
    repo_data = payload.get("repository", {})
    repo_name = repo_data.get("full_name")
    
    # If push event, track commit range
    if event_type == "push":
        before_sha = payload.get("before")
        after_sha = payload.get("after")
        ref = payload.get("ref", "")
        logger.info(f"Push on {repo_name} ({ref}): {before_sha} -> {after_sha}")


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def handle_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """Secure receiver for GitHub webhook events."""
    raw_body = await request.body()

    # 1. Verify HMAC Signature
    try:
        github_client.verify_webhook_signature(raw_body, x_hub_signature_256)
    except WebhookVerificationError as e:
        logger.warning(f"Webhook signature rejection: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    # 2. Check for Duplicate Delivery ID (Idempotency)
    if github_client.is_duplicate_event(x_github_delivery):
        logger.info(f"Ignoring duplicate webhook delivery: {x_github_delivery}")
        return {"status": "ignored", "reason": "duplicate_delivery"}

    # 3. Parse JSON Payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # 4. Schedule Background Task
    background_tasks.add_task(
        process_github_event_background,
        x_github_event,
        x_github_delivery,
        payload
    )

    return {
        "status": "accepted",
        "event": x_github_event,
        "delivery_id": x_github_delivery,
    }
