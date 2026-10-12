import os
import time
import requests
from datetime import datetime

from flask import (
    Blueprint, request, jsonify, session, render_template, redirect, url_for
)

from app import db
from app.models import User, Conversation, ChatMessage

ai_bp = Blueprint("ai", __name__)

PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")


def get_user():
    uid = session.get("user")
    return db.session.get(User, uid) if uid else None


def _call_gemini(model, payload, key, timeout=45):
    """Single Gemini call. Returns (reply, error)."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={key}"
    )
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code == 503:
            return None, "503"
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None, "empty"
        parts = candidates[0].get("content", {}).get("parts", [])
        reply = "".join(p.get("text", "") for p in parts).strip()
        return (reply or None), None
    except requests.RequestException as e:
        print(f"[{model}] request failed:", str(e))
        if getattr(e, "response", None) is not None:
            print("Response body:", e.response.text[:300])
        return None, str(e)


@ai_bp.route("/assistant")
def assistant():
    if "user" not in session:
        return redirect(url_for("auth.login"))
    user = get_user()
    return render_template("ai.html", username=user.username)


@ai_bp.post("/api/chat")
def chat():
    if "user" not in session:
        return jsonify(error="Please log in"), 401

    user = get_user()
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify(error="Message is required"), 400

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return jsonify(error="GEMINI_API_KEY is not configured"), 500

    # History — last 6 turns
    history = []
    for item in (data.get("history") or [])[-6:]:
        if (
            isinstance(item, dict)
            and item.get("role") in ("user", "assistant")
            and isinstance(item.get("content"), str)
            and item["content"].strip()
        ):
            history.append(item)

    system_prompt = (
        f"You are LAKSHYA, a friendly study assistant for college students. "
        f"The student you are helping is named '{user.username}'. "
        f"Explain clearly in short steps. Keep answers focused on studying, "
        f"programming, DSA, interviews, and general knowledge. "
        f"If the student asks your name, say you are LAKSHYA AI. "
        f"Be warm, encouraging, and concise."
    )

    contents = []
    for turn in history:
        contents.append({
            "role": "user" if turn["role"] == "user" else "model",
            "parts": [{"text": turn["content"]}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": message[:4000]}]
    })

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }

    # Try primary with exponential backoff
    for attempt in range(3):
        reply, err = _call_gemini(PRIMARY_MODEL, payload, key)
        if reply:
            return jsonify(reply=reply)
        if err == "503":
            wait = 2 ** attempt
            print(f"[{PRIMARY_MODEL}] 503 (attempt {attempt+1}/3), waiting {wait}s...")
            time.sleep(wait)
        else:
            break

    # Fallback model
    print(f"Primary failed → trying fallback: {FALLBACK_MODEL}")
    reply, err = _call_gemini(FALLBACK_MODEL, payload, key)
    if reply:
        return jsonify(reply=reply)

    return jsonify(error="AI is temporarily busy. Please try again in a moment."), 503


# ------------------------------------------------------------------
# CONVERSATIONS
# ------------------------------------------------------------------
@ai_bp.get("/api/conversations")
def list_conversations():
    if "user" not in session:
        return jsonify(error="Please log in"), 401
    user = get_user()
    convs = (
        Conversation.query
        .filter_by(user_id=user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
        .all()
    )
    return jsonify(conversations=[
        {"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()}
        for c in convs
    ])


@ai_bp.get("/api/conversations/<int:cid>")
def get_conversation(cid):
    if "user" not in session:
        return jsonify(error="Please log in"), 401
    user = get_user()
    conv = Conversation.query.filter_by(id=cid, user_id=user.id).first()
    if not conv:
        return jsonify(error="Not found"), 404
    return jsonify(messages=[
        {"role": m.role, "content": m.content} for m in conv.messages
    ])


@ai_bp.delete("/api/conversations/<int:cid>")
def delete_conversation(cid):
    if "user" not in session:
        return jsonify(error="Please log in"), 401
    user = get_user()
    conv = Conversation.query.filter_by(id=cid, user_id=user.id).first()
    if not conv:
        return jsonify(error="Not found"), 404
    db.session.delete(conv)
    db.session.commit()
    return jsonify(ok=True)


@ai_bp.post("/api/conversations")
def create_conversation():
    if "user" not in session:
        return jsonify(error="Please log in"), 401
    user = get_user()
    conv = Conversation(user_id=user.id, title="New chat")
    db.session.add(conv)
    db.session.commit()
    return jsonify(id=conv.id, title=conv.title)


@ai_bp.post("/api/conversations/<int:cid>/messages")
def save_message(cid):
    if "user" not in session:
        return jsonify(error="Please log in"), 401
    user = get_user()
    conv = Conversation.query.filter_by(id=cid, user_id=user.id).first()
    if not conv:
        return jsonify(error="Not found"), 404

    data = request.get_json(silent=True) or {}
    role = data.get("role")
    content = (data.get("content") or "").strip()

    if role not in ("user", "assistant") or not content:
        return jsonify(error="Invalid message"), 400

    msg = ChatMessage(conversation_id=cid, role=role, content=content)
    db.session.add(msg)

    if role == "user" and conv.title == "New chat":
        conv.title = content[:60]

    conv.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(ok=True, message_id=msg.id)