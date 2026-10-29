"""Start / end calls, and the browser's audio WebSocket.

POST /api/session                 create a call, return the WebSocket URL
WS   /ws/call?call_id=            browser audio <-> backend <-> Gemini Live
POST /api/session/{id}/end        stop a running call
POST /api/simulate                start a Simulate-mode call (no mic, no Gemini)

WebSocket messages:
    browser -> backend   binary: mic audio, 16 kHz 16-bit mono PCM
                         text:   {"type": "mute", "muted": true} | {"type": "end"} | {"type": "test_drop"}
    backend -> browser   binary: agent audio, 24 kHz 16-bit mono PCM
                         text:   {"type": "clear_audio"} (barge-in: stop playback) | {"type": "ended"}
Transcript, form state and metrics go over /api/calls/{id}/events, as in Simulate mode.
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import has_api_key
from app.db import SessionLocal, get_db
from app.models import Call, Form
from app.schemas import SessionRequest, SimulateRequest
from app.services.events import bus
from app.services.gemini_live import end_live_call, get_live_call, start_live_call
from app.services.simulate import start_simulation
from app.services.tools import form_state

router = APIRouter()


def _create_call(db: Session, form_id: str, settings: dict, mode: str) -> Call:
    if db.get(Form, form_id) is None:
        raise HTTPException(404, "Form not found")
    call = Call(id=uuid.uuid4().hex[:12], form_id=form_id, mode=mode, status="connecting", settings=settings,
                transcript=[], errors=[])
    db.add(call)
    db.commit()
    return call


@router.post("/api/session")
async def create_session(body: SessionRequest, db: Session = Depends(get_db)):
    if not has_api_key():
        raise HTTPException(400, "GEMINI_API_KEY is not set in backend/.env. Use Simulate mode or add the key.")
    call = _create_call(db, body.form_id, body.settings.model_dump(), "live")
    bus.publish(call.id, "status", {"status": "connecting"})
    bus.publish(call.id, "form_state", form_state(db, call.id))
    return {"call_id": call.id, "ws_url": f"/ws/call?call_id={call.id}", "events_url": f"/api/calls/{call.id}/events"}


@router.websocket("/ws/call")
async def ws_call(websocket: WebSocket, call_id: str = Query(...)):
    await websocket.accept()
    with SessionLocal() as db:
        call = db.get(Call, call_id)
        form = db.get(Form, call.form_id).definition if call else None
    if call is None or call.mode != "live" or call.status == "ended":
        await websocket.close(code=4404, reason="Call not found or already ended")
        return

    # Same call_id again = the browser reconnecting after a network drop: keep the Gemini session.
    live = get_live_call(call_id) or start_live_call(call_id, call.settings, form)
    await live.attach(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes"):
                await live.send_audio(message["bytes"])
            elif message.get("text"):
                control = json.loads(message["text"])
                if control.get("type") == "mute":
                    await live.set_muted(bool(control.get("muted")))
                elif control.get("type") == "test_drop":
                    await live.request_drop()
                elif control.get("type") == "end":
                    await live.end()
                    break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        live.detach(websocket)


@router.post("/api/session/{call_id}/end")
async def end_session(call_id: str):
    stopped = await end_live_call(call_id)
    return {"stopped": stopped}


@router.post("/api/simulate")
async def simulate(body: SimulateRequest, db: Session = Depends(get_db)):
    call = _create_call(db, body.form_id, body.settings.model_dump(), "simulate")
    bus.publish(call.id, "form_state", form_state(db, call.id))
    start_simulation(call.id, body.speed)
    return {"call_id": call.id, "events_url": f"/api/calls/{call.id}/events"}
