"""
Hey Arthur Voice Assistant
--------------------------

Usage:
1. Install dependencies: `pip install -e .` (from this directory) or `pip install .`.
2. Download the Vosk English small model (e.g. vosk-model-small-en-us-0.15) and place it under `./models/vosk-small-en`,
   or set the `VOSK_MODEL_PATH` environment variable to the unpacked model directory.
3. List available microphones: `python hey_arthur.py list-devices`.
4. Start the assistant: `python hey_arthur.py run`.
   Optional: `python hey_arthur.py run --wav sample.wav --print-partials`.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import queue
import signal
import threading
import time
import unicodedata
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import typer
import webrtcvad
from metaphone import doublemetaphone
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

import config
from server.serverDatabase import Queue, drinkDatabase

try:
    import sounddevice as sd
except Exception as exc:  # pragma: no cover - dependency import guard
    raise RuntimeError(
        "The sounddevice package is required. Install dependencies via `pip install -e .`."
    ) from exc

try:
    from vosk import KaldiRecognizer, Model  # type: ignore
except Exception as exc:  # pragma: no cover - dependency import guard
    raise RuntimeError(
        "The Vosk package is required. Install dependencies via `pip install -e .`."
    ) from exc


app = typer.Typer(add_completion=False)


# ---------------------------------------------------------------------------
# Utility data structures
# ---------------------------------------------------------------------------


@dataclass
class AudioFrame:
    """Audio frame emitted after VAD gating."""

    data: bytes
    timestamp: float
    is_speech: bool


@dataclass
class DeviceSelection:
    index: int
    name: str
    samplerate: float


@dataclass
class TranscriptionResult:
    text: str
    is_final: bool


# ---------------------------------------------------------------------------
# Device discovery and selection
# ---------------------------------------------------------------------------


def list_input_devices(prefer_substring: str = config.USB_MATCH_SUBSTRING) -> None:
    """Print all input-capable devices."""
    devices = sd.query_devices()
    default_in, _ = sd.default.device
    prefer_upper = prefer_substring.upper()

    typer.echo("Input devices:")
    for idx, dev in enumerate(devices):
        max_in = int(dev.get("max_input_channels", 0))
        if max_in <= 0:
            continue
        rate = int(dev.get("default_samplerate", 0))
        name = dev.get("name", "Unknown")
        tags: List[str] = []
        if default_in is not None and idx == default_in:
            tags.append("default")
        if prefer_upper and prefer_upper in name.upper():
            tags.append("USB-preferred")
        tag_str = f" [{' | '.join(tags)}]" if tags else ""
        typer.echo(f"  {idx:>2}: {name} (in={max_in}, rate={rate}){tag_str}")


def select_input_device(
    prefer_substring: str = config.USB_MATCH_SUBSTRING,
) -> DeviceSelection:
    """Select an input device, preferring USB devices."""
    devices = sd.query_devices()
    default_in, _ = sd.default.device
    candidates: List[Tuple[int, dict]] = [
        (idx, dev) for idx, dev in enumerate(devices) if dev.get("max_input_channels", 0) > 0
    ]
    if not candidates:
        raise RuntimeError("No input-capable audio devices found.")

    preferred_terms: List[str] = []
    if prefer_substring:
        preferred_terms.append(prefer_substring.upper())
    for extra in getattr(config, "ADDITIONAL_PREFERRED_DEVICE_SUBSTRINGS", []):
        term = extra.upper()
        if term and term not in preferred_terms:
            preferred_terms.append(term)

    chosen_pair: Optional[Tuple[int, dict]] = None
    for term in preferred_terms:
        matches = [
            (idx, dev)
            for idx, dev in candidates
            if term and term in dev.get("name", "").upper()
        ]
        if matches:
            chosen_pair = matches[0]
            break

    if chosen_pair is None and default_in is not None:
        chosen_pair = next((pair for pair in candidates if pair[0] == default_in), None)
    if not chosen_pair:
        chosen_pair = candidates[0]
    chosen_idx, chosen_dev = chosen_pair
    samplerate = float(chosen_dev.get("default_samplerate") or config.SAMPLE_RATE)
    name = chosen_dev.get("name", f"Device {chosen_idx}")
    return DeviceSelection(index=chosen_idx, name=name, samplerate=samplerate)


# ---------------------------------------------------------------------------
# Audio streaming with VAD gating
# ---------------------------------------------------------------------------


class BaseAudioStream:
    """Common interface for audio sources."""

    frame_duration: float

    def start(self) -> None:  # pragma: no cover - runtime
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - runtime
        raise NotImplementedError

    def get_frame(self, timeout: float = 0.1) -> Optional[AudioFrame]:  # pragma: no cover - runtime
        raise NotImplementedError

    def time_since_voice(self) -> float:  # pragma: no cover - runtime
        raise NotImplementedError


class AudioStream(BaseAudioStream):
    """
    Microphone audio stream that uses WebRTC VAD to gate frames.

    The stream runs a PortAudio callback to collect raw audio, processes it on a background
    thread, and produces VAD-approved frames (with pre-roll and hangover) ready for ASR.
    If the underlying stream fails, it will attempt to re-open using the current device
    selection policy.
    """

    PRE_SPEECH_MS = 200
    HANGOVER_MS = 200

    def __init__(
        self,
        device_selector: Callable[[], DeviceSelection],
        sample_rate: int,
        frame_ms: int,
        vad_aggressiveness: int,
        *,
        debug: bool = False,
    ) -> None:
        self._device_selector = device_selector
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self.frame_bytes = self.frame_samples * 2  # 16-bit mono
        self.frame_duration = frame_ms / 1000.0
        self._stop_event = threading.Event()
        self._raw_queue = queue.Queue(maxsize=100)
        self._deliver_queue = queue.Queue(maxsize=200)
        self._stream: Optional[sd.InputStream] = None
        self._processor_thread: Optional[threading.Thread] = None
        self._vad = webrtcvad.Vad(vad_aggressiveness)
        self._prebuffer_len = max(1, int(self.PRE_SPEECH_MS / frame_ms))
        self._hangover_frames = max(1, int(self.HANGOVER_MS / frame_ms))
        self._triggered = False
        self._last_voiced_at = time.monotonic()
        self._last_frame_at = time.monotonic()
        self._current_device: Optional[DeviceSelection] = None
        self._debug = debug
        self._lock = threading.Lock()
        self._restart_lock = threading.Lock()
        self._last_restart_attempt = 0.0

    def start(self) -> None:
        self._stop_event.clear()
        self._open_stream()
        self._processor_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._processor_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=1.0)
        if self._stream:
            with contextlib.suppress(Exception):
                self._stream.stop()
            with contextlib.suppress(Exception):
                self._stream.close()

    def time_since_voice(self) -> float:
        return time.monotonic() - self._last_voiced_at

    def time_since_frame(self) -> float:
        return time.monotonic() - self._last_frame_at

    def get_frame(self, timeout: float = 0.1) -> Optional[AudioFrame]:
        if self._stop_event.is_set():
            return None
        self._ensure_stream_alive()
        try:
            return self._deliver_queue.get(timeout=timeout)
        except queue.Empty:
            if self.time_since_frame() > 1.0:
                self._restart_stream("no audio frames observed")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_stream_alive(self) -> None:
        stream = self._stream
        if stream is None:
            self._restart_stream("stream unavailable")
            return
        try:
            active = stream.active
        except Exception:
            active = True
        if not active:
            self._restart_stream("stream inactive")

    def _restart_stream(self, reason: str) -> None:
        if self._stop_event.is_set():
            return
        now = time.monotonic()
        if now - self._last_restart_attempt < 1.0:
            return
        self._last_restart_attempt = now
        logging.warning("Restarting audio stream (%s)", reason)
        with self._restart_lock:
            try:
                self._open_stream()
            except Exception as exc:
                logging.error("Audio stream restart failed: %s", exc)
                time.sleep(1.0)

    def _put_deliver_queue(self, frame: AudioFrame) -> None:
        try:
            self._deliver_queue.put_nowait(frame)
        except queue.Full:
            logging.warning("Deliver queue full; dropping frame")

    @staticmethod
    def _clear_queue(q: queue.Queue) -> None:
        with contextlib.suppress(queue.Empty):
            while True:
                q.get_nowait()

    def _open_stream(self) -> None:
        """Open (or reopen) the PortAudio stream."""
        if self._stream:
            with contextlib.suppress(Exception):
                self._stream.close()
        self._clear_queue(self._raw_queue)
        self._clear_queue(self._deliver_queue)
        self._current_device = self._device_selector()
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_samples,
                dtype="int16",
                channels=1,
                device=self._current_device.index,
                callback=self._callback,
            )
            self._stream.start()
            logging.debug(
                "Audio stream using device '%s' (idx=%d, %.0f Hz)",
                self._current_device.name,
                self._current_device.index,
                self.sample_rate,
            )
            self._last_frame_at = time.monotonic()
        except Exception as exc:
            logging.error("Failed to open audio stream: %s", exc)
            raise

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            logging.warning("Audio callback status: %s", status)
        try:
            timestamp = time.monotonic()
            self._raw_queue.put_nowait((indata.copy(), timestamp))
            self._last_frame_at = timestamp
        except queue.Full:
            logging.warning("Audio raw queue full; dropping frame")

    def _process_loop(self) -> None:
        """Process raw frames -> VAD -> deliver queue."""
        # Maintain a short pre-roll buffer so we can prepend audio when speech starts.
        prebuffer: deque = deque(maxlen=self._prebuffer_len)
        triggered = False
        remaining_hang = 0
        while not self._stop_event.is_set():
            try:
                chunk, timestamp = self._raw_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            frame_bytes = chunk.tobytes()
            is_speech = False
            try:
                is_speech = self._vad.is_speech(frame_bytes, self.sample_rate)
            except Exception as exc:
                logging.error("VAD failure: %s", exc)

            if is_speech:
                self._last_voiced_at = timestamp

            if is_speech:
                if not triggered:
                    triggered = True
                    remaining_hang = self._hangover_frames
                    for buffered_bytes, buffered_ts in prebuffer:
                        if self._debug:
                            logging.debug("Emitting prebuffer frame at %.3f", buffered_ts)
                        self._put_deliver_queue(AudioFrame(buffered_bytes, buffered_ts, is_speech=False))
                    prebuffer.clear()
                self._put_deliver_queue(AudioFrame(frame_bytes, timestamp, is_speech=True))
                remaining_hang = self._hangover_frames
            else:
                if triggered:
                    if remaining_hang > 0:
                        self._put_deliver_queue(AudioFrame(frame_bytes, timestamp, is_speech=False))
                        remaining_hang -= 1
                    else:
                        triggered = False
                if not triggered:
                    # Collect silence so the next speech segment can include a lead-in.
                    prebuffer.append((frame_bytes, timestamp))

        # Flush queues on stop
        while not self._deliver_queue.empty():
            try:
                self._deliver_queue.get_nowait()
            except queue.Empty:
                break


class WavAudioStream(BaseAudioStream):
    """Audio stream sourced from a WAV file (for offline testing)."""

    PRE_SPEECH_MS = 200
    HANGOVER_MS = 200

    def __init__(self, path: Path, frame_ms: int, vad_aggressiveness: int) -> None:
        self._path = path
        self._wav = wave.open(str(path), "rb")
        self.sample_rate = self._wav.getframerate()
        self.frame_ms = frame_ms
        self.frame_samples = int(self.sample_rate * frame_ms / 1000)
        self.frame_duration = frame_ms / 1000.0
        self._vad = webrtcvad.Vad(vad_aggressiveness)
        self._stop = False
        self._last_voiced_at = time.monotonic()
        self._prebuffer: deque = deque(maxlen=max(1, int(self.PRE_SPEECH_MS / frame_ms)))
        self._hangover_frames = max(1, int(self.HANGOVER_MS / frame_ms))
        self._remaining_hangover = 0
        self._triggered = False
        self._pending_frames: deque = deque()

        if self._wav.getnchannels() != 1 or self._wav.getsampwidth() != 2:
            raise ValueError("WAV input must be 16-bit mono PCM.")
        if self.sample_rate != config.SAMPLE_RATE:
            raise ValueError(f"WAV sample rate must be {config.SAMPLE_RATE}, found {self.sample_rate}.")

    def start(self) -> None:
        self._stop = False
        self._wav.rewind()
        self._prebuffer.clear()
        self._pending_frames.clear()
        self._triggered = False
        self._remaining_hangover = 0
        self._last_voiced_at = time.monotonic()

    def stop(self) -> None:
        self._stop = True
        with contextlib.suppress(Exception):
            self._wav.close()

    def time_since_voice(self) -> float:
        return time.monotonic() - self._last_voiced_at

    def get_frame(self, timeout: float = 0.1) -> Optional[AudioFrame]:
        if self._stop:
            return None
        if self._pending_frames:
            return self._pending_frames.popleft()
        data = self._wav.readframes(self.frame_samples)
        if not data:
            self._stop = True
            return None
        timestamp = time.monotonic()
        try:
            is_speech = self._vad.is_speech(data, self.sample_rate)
        except Exception as exc:
            logging.error("VAD failure on WAV: %s", exc)
            is_speech = False
        if is_speech:
            self._last_voiced_at = timestamp
            if not self._triggered:
                self._triggered = True
                while self._prebuffer:
                    buffered_bytes, buffered_ts = self._prebuffer.popleft()
                    self._pending_frames.append(AudioFrame(buffered_bytes, buffered_ts, is_speech=False))
            self._remaining_hangover = self._hangover_frames
            self._pending_frames.append(AudioFrame(data, timestamp, is_speech=True))
            return self._pending_frames.popleft()
        if self._triggered and self._remaining_hangover > 0:
            self._remaining_hangover -= 1
            self._pending_frames.append(AudioFrame(data, timestamp, is_speech=False))
            return self._pending_frames.popleft()
        self._triggered = False
        self._prebuffer.append((data, timestamp))
        if self._pending_frames:
            return self._pending_frames.popleft()
        return None


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


class Transcriber:
    """Wrapper around Vosk to provide streaming transcription events."""

    def __init__(self, model_path: Path, sample_rate: int, *, print_partials: bool = False) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"Vosk model not found at {model_path}. Download the small English model and place it there "
                f"or set {config.VOSK_MODEL_ENV_VAR}."
            )
        self._model = Model(str(model_path))
        self.sample_rate = sample_rate
        self._print_partials = print_partials

    def start_session(self) -> "TranscriberSession":
        recognizer = KaldiRecognizer(self._model, self.sample_rate)
        recognizer.SetWords(True)
        return TranscriberSession(recognizer, print_partials=self._print_partials)


class TranscriberSession:
    """Manages a single streaming transcription session."""

    def __init__(self, recognizer: KaldiRecognizer, *, print_partials: bool = False) -> None:
        self._recognizer = recognizer
        self._print_partials = print_partials

    def accept_frame(self, frame: AudioFrame) -> Iterable[TranscriptionResult]:
        """Feed audio frame bytes and yield transcription results."""
        results: List[TranscriptionResult] = []
        if self._recognizer.AcceptWaveform(frame.data):
            final = json.loads(self._recognizer.Result())
            text = final.get("text", "").strip()
            if text:
                results.append(TranscriptionResult(text=text, is_final=True))
        else:
            partial = json.loads(self._recognizer.PartialResult()).get("partial", "").strip()
            if partial:
                if self._print_partials:
                    logging.info("[partial] %s", partial)
                results.append(TranscriptionResult(text=partial, is_final=False))
        return results

    def flush(self) -> Iterable[TranscriptionResult]:
        final = json.loads(self._recognizer.FinalResult())
        text = final.get("text", "").strip()
        if text:
            return [TranscriptionResult(text=text, is_final=True)]
        return []


# ---------------------------------------------------------------------------
# Text processing helpers
# ---------------------------------------------------------------------------


FILLER_WORDS = {"uh", "um", "erm"}

TARGET_WAKE_PHRASE = "hey arthur"
TARGET_WAKE_METAPHONE = [code for code in doublemetaphone(TARGET_WAKE_PHRASE) if code]


def normalize_text(text: str) -> str:
    """Normalize text to ASCII alphanumerics."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    cleaned = []
    for token in text.split():
        token = "".join(ch for ch in token if ch.isalnum())
        if not token:
            continue
        if token in FILLER_WORDS:
            continue
        cleaned.append(token)
    return " ".join(cleaned)


def metaphone_distance(candidate: str) -> Tuple[bool, Optional[int]]:
    """Check metaphone similarity; returns (match, min_distance)."""
    codes = [code for code in doublemetaphone(candidate) if code]
    if not codes or not TARGET_WAKE_METAPHONE:
        return False, None
    min_distance: Optional[int] = None
    for cand in codes:
        for target in TARGET_WAKE_METAPHONE:
            distance = Levenshtein.distance(cand, target)
            if min_distance is None or distance < min_distance:
                min_distance = distance
            if distance <= 1:
                return True, distance
    return False, min_distance


def is_wake_phrase(text: str, wake_threshold: int) -> Tuple[bool, dict]:
    """Check if text matches the wake phrase using fuzzy + phonetic similarity."""
    normalized = normalize_text(text)
    if not normalized:
        return False, {"candidate": "", "fuzzy": 0, "token": 0, "metaphone": False, "meta_distance": None}
    fuzzy_score = fuzz.partial_ratio(normalized, TARGET_WAKE_PHRASE)
    token_score = fuzz.token_set_ratio(normalized, TARGET_WAKE_PHRASE)
    # Accept either strong fuzzy match or a near-identical Double Metaphone code.
    metaphone_match, meta_distance = metaphone_distance(normalized)
    accepted = fuzzy_score >= wake_threshold or token_score >= wake_threshold or metaphone_match
    if metaphone_match:
        accepted = True
    else:
        accepted = fuzzy_score >= wake_threshold or token_score >= wake_threshold
    meta = {
        "candidate": normalized,
        "fuzzy": fuzzy_score,
        "token": token_score,
        "metaphone": metaphone_match,
        "meta_distance": meta_distance,
    }
    return accepted, meta


def match_drink(text: str, drinks: Sequence[str], drink_threshold: int) -> Optional[str]:
    """Return canonical drink if detected in text."""
    normalized = normalize_text(text)
    if not normalized:
        return None
    tokens = normalized.split()
    search_space = tokens + [" ".join(tokens)]
    for token in list(tokens):
        if token.endswith("s"):
            search_space.append(token[:-1])
    # Scan both individual tokens and the full utterance for fuzzy matches.
    for candidate in search_space:
        if not candidate:
            continue
        match = process.extractOne(candidate, drinks, scorer=fuzz.WRatio, score_cutoff=drink_threshold)
        if match:
            return match[0]
    return None


# ---------------------------------------------------------------------------
# Core state machine
# ---------------------------------------------------------------------------


class HeyArthurController:
    """State machine orchestrating passive and active listening."""

    ACTIVE_SILENCE_TIMEOUT = 1.5  # seconds without voice to end active mode

    def __init__(
        self,
        audio_stream: BaseAudioStream,
        transcriber: Transcriber,
        drinks: Sequence[str],
        *,
        wake_threshold: int,
        drink_threshold: int,
        active_max_speech: float,
        post_wake_silence: float,
        delay_before_making: float,
    ) -> None:
        self.audio_stream = audio_stream
        self.transcriber = transcriber
        self.drinks = list(drinks)
        self.wake_threshold = wake_threshold
        self.drink_threshold = drink_threshold
        self.active_max_speech = active_max_speech
        self.post_wake_silence = post_wake_silence
        self.delay_before_making = delay_before_making
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self.audio_stream.start()
        try:
            self._passive_loop()
        finally:
            self.audio_stream.stop()

    # ------------------------------------------------------------------

    def _passive_loop(self) -> None:
        logging.info("[passive] listening...")
        session = self.transcriber.start_session()
        while not self._stop_event.is_set():
            frame = self.audio_stream.get_frame(timeout=0.2)
            if frame is None:
                time.sleep(0.01)
                continue
            for result in session.accept_frame(frame):
                is_wake, meta = is_wake_phrase(result.text, self.wake_threshold)
                if not is_wake:
                    continue
                logging.info(
                    "[wake] candidate='%s', fuzzy=%d, token=%d, metaphone=%s",
                    meta["candidate"],
                    meta["fuzzy"],
                    meta["token"],
                    meta["metaphone"],
                )
                self._await_post_wake_silence()
                logging.info("[active] listening for drink...")
                drink = self._active_loop()
                if drink:
                    logging.info("[result] Making %s", drink)
                    # Add drink to queue
                    drink_data = drinkDatabase.retrieveDrink(drink)
                    if drink_data:
                        Queue.addToQueueClient(drink_data)
                        logging.info("[queue] Added %s to queue", drink_data.get("drink_name", drink))
                    else:
                        logging.warning("Drink '%s' not found in database; nothing queued", drink)
                else:
                    logging.info("[timeout] returning to passive")
                session = self.transcriber.start_session()
                logging.info("[passive] listening...")
                break

    def _await_post_wake_silence(self) -> None:
        """Debounce wake detection by enforcing post-wake silence."""
        target = self.post_wake_silence
        logging.debug("Waiting for %.1fs silence post wake", target)
        now = time.monotonic()
        silence_deadline = now + target
        max_deadline = now + target + 0.2

        while not self._stop_event.is_set():
            frame = self.audio_stream.get_frame(timeout=0.05)
            now = time.monotonic()
            if frame is not None and frame.is_speech:
                silence_deadline = now + target
                continue
            if now >= silence_deadline:
                return
            if now >= max_deadline:
                logging.debug("Silence wait exceeded %.1fs, proceeding", max_deadline - (silence_deadline - target))
                return

    def _active_loop(self) -> Optional[str]:
        session = self.transcriber.start_session()
        speech_time = 0.0
        last_result_text = ""
        active_start = time.monotonic()
        while not self._stop_event.is_set():
            frame = self.audio_stream.get_frame(timeout=0.2)
            if frame is None:
                if speech_time >= self.active_max_speech:
                    break
                if time.monotonic() - active_start > self.active_max_speech + 4:
                    break
                if self.audio_stream.time_since_voice() > self.ACTIVE_SILENCE_TIMEOUT and speech_time > 0:
                    break
                time.sleep(0.01)
                continue

            if frame.is_speech:
                speech_time += self.audio_stream.frame_duration

            for result in session.accept_frame(frame):
                if result.is_final and result.text:
                    logging.info("[active] transcript='%s'", result.text)
                last_result_text = result.text
                drink = match_drink(result.text, self.drinks, self.drink_threshold)
                if drink:
                    return drink
            if speech_time >= self.active_max_speech:
                break
            if self.audio_stream.time_since_voice() > self.ACTIVE_SILENCE_TIMEOUT and speech_time > 0:
                break
        # Flush any remaining text to allow final detection.
        for result in session.flush():
            if result.text:
                logging.info("[active] transcript='%s'", result.text)
            drink = match_drink(result.text, self.drinks, self.drink_threshold)
            if drink:
                return drink
        if last_result_text:
            logging.debug("[active] final transcript='%s'", last_result_text)
        return None

    def _sleep_with_stop(self, duration: float) -> None:
        deadline = time.monotonic() + duration
        while not self._stop_event.is_set() and time.monotonic() < deadline:
            # Drain pending frames so the capture queue does not overflow during standby.
            while True:
                frame = self.audio_stream.get_frame(timeout=0)
                if frame is None:
                    break
            remaining = deadline - time.monotonic()
            time.sleep(min(0.1, remaining))


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def resolve_model_path(model_override: Optional[Path]) -> Path:
    if model_override:
        return model_override
    env_path = os.getenv(config.VOSK_MODEL_ENV_VAR)
    if env_path:
        return Path(env_path)
    return Path(config.DEFAULT_VOSK_MODEL_DIR)


def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_drinks(drink_override: Optional[str]) -> Sequence[str]:
    if not drink_override:
        return config.DRINKS
    return [token.strip().lower() for token in drink_override.split(",") if token.strip()]


# ---------------------------------------------------------------------------
# Typer commands
# ---------------------------------------------------------------------------


@app.command()
def list_devices() -> None:
    """List available audio input devices."""
    setup_logging(debug=False)
    list_input_devices()


@app.command()
def run(
    wake_threshold: int = typer.Option(config.WAKE_MIN_FUZZ, help="Wake phrase fuzzy score threshold."),
    drink_threshold: int = typer.Option(config.DRINK_MIN_FUZZ, help="Drink detection fuzzy score threshold."),
    active_max_speech: float = typer.Option(
        config.ACTIVE_MAX_SPEECH_S, help="Maximum speech duration (seconds) in active mode."
    ),
    post_wake_silence: float = typer.Option(
        config.SILENCE_POST_WAKE_S, help="Silence required after wake phrase before entering active mode."
    ),
    delay_before_making: float = typer.Option(
        config.DELAY_BEFORE_MAKING_S, help="Delay (seconds) before announcing drink preparation."
    ),
    drinks: Optional[str] = typer.Option(None, help="Override drink list (comma-separated)."),
    prefer_substring: str = typer.Option(config.USB_MATCH_SUBSTRING, help="Preferred substring for USB mics."),
    model_path: Optional[Path] = typer.Option(None, exists=False, help="Override path to Vosk model directory."),
    wav: Optional[Path] = typer.Option(None, exists=True, help="Read audio from WAV file instead of microphone."),
    debug: bool = typer.Option(False, help="Enable debug logging."),
    print_partials: bool = typer.Option(False, help="Print partial ASR hypotheses."),
) -> None:
    """Run the Hey Arthur assistant."""
    setup_logging(debug=debug)
    drink_list = parse_drinks(drinks)
    model_dir = resolve_model_path(model_path)

    sample_rate = config.SAMPLE_RATE
    if wav:
        try:
            audio_stream: BaseAudioStream = WavAudioStream(
                wav, frame_ms=config.FRAME_MS, vad_aggressiveness=config.VAD_AGGRESSIVENESS
            )
        except Exception as exc:
            logging.error("Failed to initialise WAV input: %s", exc)
            raise typer.Exit(code=1)
        sample_rate = audio_stream.sample_rate
        logging.info("Using WAV input: %s", wav)
    else:
        # Re-run device selection whenever we (re)open the stream so USB unplug events fall back gracefully.
        def selector_with_retry() -> DeviceSelection:
            while True:
                try:
                    selection = select_input_device(prefer_substring=prefer_substring)
                    logging.info(
                        "[passive] listening on device '%s' (idx=%s, %.0f Hz)",
                        selection.name,
                        selection.index,
                        sample_rate,
                    )
                    return selection
                except Exception as exc:
                    logging.error("Device enumeration failed: %s", exc)
                    time.sleep(1.0)

        audio_stream = AudioStream(
            selector_with_retry,
            sample_rate=sample_rate,
            frame_ms=config.FRAME_MS,
            vad_aggressiveness=config.VAD_AGGRESSIVENESS,
            debug=debug,
        )

    try:
        transcriber = Transcriber(model_dir, sample_rate=sample_rate, print_partials=print_partials)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        raise typer.Exit(code=1)

    controller = HeyArthurController(
        audio_stream,
        transcriber,
        drink_list,
        wake_threshold=wake_threshold,
        drink_threshold=drink_threshold,
        active_max_speech=active_max_speech,
        post_wake_silence=post_wake_silence,
        delay_before_making=delay_before_making,
    )

    stop_event = threading.Event()

    def _handle_sigint(signum, frame):  # pragma: no cover - signal handler
        logging.info("Received interrupt, shutting down...")
        stop_event.set()
        controller.stop()

    signal.signal(signal.SIGINT, _handle_sigint)

    def run_controller():
        try:
            controller.run()
        except Exception as exc:
            logging.error("Controller crashed: %s", exc)
            stop_event.set()

    worker = threading.Thread(target=run_controller, daemon=True)
    worker.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    finally:
        controller.stop()
        audio_stream.stop()
        worker.join(timeout=2.0)
        logging.info("Shutdown complete.")


if __name__ == "__main__":
    app()
