"""Voice agent capability — speech-to-text and text-to-speech for agent interactions.

Enables agents to communicate via voice. Uses OpenAI Whisper for transcription
and OpenAI TTS for speech synthesis. Falls back to text if voice unavailable.

Agents can:
- Accept voice input from users (transcribed to text)
- Respond with synthesized speech
- Handle phone-style interactions
"""
import os
import logging
import httpx
import base64

log = logging.getLogger("arch.voice")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
VOICE_AVAILABLE = bool(OPENAI_API_KEY)

if VOICE_AVAILABLE:
    log.info("Voice: AVAILABLE (OpenAI Whisper + TTS)")
else:
    log.info("Voice: NOT CONFIGURED (set OPENAI_API_KEY)")


async def transcribe_audio(audio_bytes: bytes, format: str = "webm") -> str:
    """Transcribe audio to text using OpenAI Whisper."""
    if not VOICE_AVAILABLE:
        return "[Voice not configured]"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": (f"audio.{format}", audio_bytes, f"audio/{format}")},
                data={"model": "whisper-1"},
            )
            if resp.status_code == 200:
                return resp.json().get("text", "")
            else:
                log.warning(f"Whisper error: {resp.status_code}")
                return f"[Transcription failed: {resp.status_code}]"
    except Exception as e:
        return f"[Transcription error: {e}]"


async def synthesize_speech(text: str, voice: str = "nova") -> bytes:
    """Convert text to speech using OpenAI TTS."""
    if not VOICE_AVAILABLE:
        return b""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "tts-1",
                    "input": text[:4096],
                    "voice": voice,
                    "response_format": "mp3",
                },
            )
            if resp.status_code == 200:
                return resp.content
            else:
                log.warning(f"TTS error: {resp.status_code}")
                return b""
    except Exception as e:
        log.warning(f"TTS error: {e}")
        return b""


async def voice_chat(agent_client, audio_bytes: bytes, agent_name: str = "assistant") -> dict:
    """Full voice chat: transcribe input → agent response → synthesize output."""
    # 1. Transcribe
    text = await transcribe_audio(audio_bytes)
    if text.startswith("["):
        return {"error": text, "text_input": "", "text_response": "", "audio_response": None}

    # 2. Get agent response (use the existing chat endpoint)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"http://127.0.0.1:8000/api/v1/boardroom/agents/{agent_name}/chat",
                json={"message": text},
            )
            response_text = resp.json().get("response", "I could not process that.")
    except Exception as e:
        response_text = f"Error: {e}"

    # 3. Synthesize response
    audio = await synthesize_speech(response_text[:500])

    return {
        "text_input": text,
        "text_response": response_text,
        "audio_response": base64.b64encode(audio).decode() if audio else None,
        "audio_format": "mp3",
    }
