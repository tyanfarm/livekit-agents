import asyncio
from collections import defaultdict
import logging
import uuid

from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    MetricsCollectedEvent,
    RoomOutputOptions,
    StopResponse,
    WorkerOptions,
    cli,
    llm,
    metrics,
)
from livekit.plugins import openai, silero, deepgram
from google.cloud import translate_v2 as translate

load_dotenv()

logger = logging.getLogger("transcriber")

translator = translate.Client()

# This example demonstrates how to transcribe audio from a remote participant.
# It creates agent session with only STT enabled and publishes transcripts to the room.

async def translate_agent(text: str, target_language: str) -> str:
    # Here you would implement the translation logic, possibly calling an external API
    # For demonstration purposes, let's just return the text with a "translated" suffix
    # return f"<translated> {text} </translated>"
    translation = translator.translate(text, target_language=target_language, model="nmt")
    transcript = translation['translatedText']

    return transcript

class Transcriber(Agent):
    def __init__(self):
        super().__init__(
            instructions="not-needed",
            # stt=openai.STT(),
            # stt = openai.STT(
            #     model="gpt-4o-transcribe",
            #     language="en"
            # ),
            stt=deepgram.STT(
                model="nova-2-general",
                language="en",
            ),
            # stt=deepgram.STT(model="nova-3", language="en"),
        )

    async def on_user_turn_completed(self, chat_ctx: llm.ChatContext, new_message: llm.ChatMessage):
        user_transcript = new_message.text_content
        logger.info(f" -> {user_transcript}")

        raise StopResponse()


async def entrypoint(ctx: JobContext):
    logger.info(
        f"starting transcriber (speech to text) example, room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession(
        # vad is needed for non-streaming STT implementations
        vad=silero.VAD.load(
            min_silence_duration=0.3
        ),
    )

    user_audio_sid: str | None = None
    user_identity: str | None = None
    seg_locks: dict[str, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    current_seg_id : dict[str, str | None] = defaultdict(lambda: None)

    @ctx.room.on("track_subscribed")
    # TrackPublication - metadata of track
    # RemoteParticipant - owner of track
    def on_track_subscribed(track: rtc.Track, pub: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        nonlocal user_audio_sid, user_identity
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            user_audio_sid = pub.sid
            user_identity = participant.identity

    async def _handle_user_input_transcribed(ev, ctx, track_sid, participant_identity):
        if not ev.transcript.strip():
            return

        # Save id of current segment
        ## speaker_id will exist in diarization
        seg_key = track_sid or getattr(ev, "speaker_id", None) or "default"

        async with seg_locks[seg_key]:
            # Create ID one time until is_final=True
            seg_id = current_seg_id[seg_key] or str(uuid.uuid4())
            current_seg_id[seg_key] = seg_id

            # Translate transcript
            translated_text = await translate_agent(ev.transcript, "vi")
            print(f"=== Segment ID: {seg_id} ===")

            # Publish 
            seg = rtc.TranscriptionSegment(
                id=seg_id,
                text=translated_text,
                start_time=0,
                end_time=0,
                language="vi",
                final=bool(ev.is_final)
            )

            tr = rtc.Transcription(
                participant_identity=participant_identity,
                track_sid=track_sid or "",
                segments=[seg],
            )

            await ctx.room.local_participant.publish_transcription(tr)

            # is_final == True --> reset id
            if ev.is_final:
                current_seg_id[seg_key] = None

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        asyncio.create_task(_handle_user_input_transcribed(
            ev, ctx, user_audio_sid, user_identity
        ))

    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)

    await session.start(
        agent=Transcriber(),
        room=ctx.room,
        room_output_options=RoomOutputOptions(
            transcription_enabled=False,
            # disable audio output if it's not needed
            audio_enabled=False,
        ),
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
