"""FastAPI backend for the CloudForge incident-investigation UI."""

import logging
import os
from pathlib import Path
import re
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

import incident_agent


LOGGER = logging.getLogger("cloudforge.api")
THINKING_BLOCK = re.compile(r"<thinking>.*?</thinking>\s*", re.IGNORECASE | re.DOTALL)
WEB_DIST = Path(__file__).parent / "web" / "dist"


class InvestigationRequest(BaseModel):
    """One incident question from the browser."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)


class TokenUsage(BaseModel):
    """Bedrock token counts reported by Strands."""

    input: int
    output: int
    total: int


class InvestigationResponse(BaseModel):
    """Diagnosis and verifiable execution metadata for the UI."""

    diagnosis: str
    tools_used: list[str]
    model_turns: int
    tokens: TokenUsage
    stop_reason: str


def clean_diagnosis(text: str) -> str:
    """Remove model-specific thinking blocks from the user-facing answer."""
    return THINKING_BLOCK.sub("", text).strip()


def create_app(
    investigator: Callable[..., Any] = incident_agent.investigate,
) -> FastAPI:
    """Create the API, optionally with an injected investigator for tests."""
    app = FastAPI(title="CloudForge", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/investigate", response_model=InvestigationResponse)
    async def investigate(request: InvestigationRequest) -> InvestigationResponse:
        profile = os.environ.get("AWS_PROFILE")
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        mcp_url = os.environ.get("CLOUDFORGE_MCP_URL", incident_agent.DEFAULT_MCP_URL)
        model_id = os.environ.get("CLOUDFORGE_MODEL_ID", incident_agent.DEFAULT_MODEL_ID)

        try:
            result = await run_in_threadpool(
                investigator,
                request.question,
                profile=profile,
                region=region,
                mcp_url=mcp_url,
                model_id=model_id,
            )
        except Exception as error:
            LOGGER.exception("Incident investigation failed")
            raise HTTPException(
                status_code=502,
                detail="Investigation failed. Check that the MCP server and AWS session are available.",
            ) from error

        usage = result.metrics.accumulated_usage
        return InvestigationResponse(
            diagnosis=clean_diagnosis(str(result)),
            tools_used=sorted(result.metrics.tool_metrics),
            model_turns=result.metrics.cycle_count,
            tokens=TokenUsage(
                input=usage["inputTokens"],
                output=usage["outputTokens"],
                total=usage["totalTokens"],
            ),
            stop_reason=str(result.stop_reason),
        )

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")

    return app


app = create_app()
