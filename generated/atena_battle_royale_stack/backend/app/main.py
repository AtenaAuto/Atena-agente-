from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Atena Firezone Backend", version="0.2.0")


class MatchRequest(BaseModel):
    player_id: str = Field(min_length=3, max_length=64)
    mode: str = Field(default="br", pattern=r"^(br|ranked_br)$")


class MatchTicket(BaseModel):
    ticket_id: str
    player_id: str
    mode: str
    estimated_wait_s: int
    status: str
    created_at: str


QUEUE: dict[str, MatchTicket] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "atena-firezone-backend", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/matchmaking/join", response_model=MatchTicket)
def join_matchmaking(payload: MatchRequest) -> MatchTicket:
    ticket = MatchTicket(
        ticket_id=f"tkt_{uuid4().hex[:12]}",
        player_id=payload.player_id,
        mode=payload.mode,
        estimated_wait_s=12 if payload.mode == "br" else 25,
        status="queued",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    QUEUE[ticket.ticket_id] = ticket
    return ticket


@app.get("/matchmaking/ticket/{ticket_id}", response_model=MatchTicket)
def get_ticket(ticket_id: str) -> MatchTicket:
    ticket = QUEUE.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    return ticket


@app.get("/config/client")
def client_config() -> dict:
    return {
        "tick_rate": 30,
        "max_players": 50,
        "safe_zone_shrink_s": 45,
        "anti_cheat": "heuristic_v1",
        "regions": ["sa-east", "us-east"],
    }
