"""
Configuration constants for the Hey Arthur voice assistant.
"""

from pathlib import Path

# Drinks that can be requested. The list should contain lower-case canonical names.
DRINKS = [
    "latte",
    "cappuccino",
    "espresso",
    "mojito",
    "martini",
    "lemonade",
    "cola"
]

# Wake and drink detection thresholds (RapidFuzz scores, 0-100 scale).
WAKE_MIN_FUZZ = 85
DRINK_MIN_FUZZ = 80

# Voice activity detection (WebRTC VAD) parameters.
FRAME_MS = 30
SAMPLE_RATE = 16_000
VAD_AGGRESSIVENESS = 2

# Timeout and timing configuration.
ACTIVE_MAX_SPEECH_S = 8.0
SILENCE_POST_WAKE_S = 0.2
DELAY_BEFORE_MAKING_S = 7.0

# Device selection.
# Prefer USB microphones first, but also consider common vendor labels.
USB_MATCH_SUBSTRING = "USB"
ADDITIONAL_PREFERRED_DEVICE_SUBSTRINGS = [
    "FIFINE",
]

# Offline ASR model configuration.
VOSK_MODEL_ENV_VAR = "VOSK_MODEL_PATH"
DEFAULT_VOSK_MODEL_DIR = Path("models") / "vosk-small-en"
