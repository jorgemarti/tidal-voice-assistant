"""
Gemini command parser: sends the command audio (WAV) to Gemini and gets back a structured intent
{action, query, artist, artist_alternatives, transcript}. The local Vosk transcript is not sent in audio mode.
"""

import io
import json
import re
import os
import time
import wave
from typing import Optional

import glob
from config import GEMINI_MODEL, GEMINI_USE_AUDIO, GEMINI_MAX_PER_HOUR, GEMINI_MAX_PER_DAY, KNOWN_ARTISTS, setup_logging

logger = setup_logging(__name__)

COMMAND_WAV_DIR = "/tmp/tidal-commands"  # last utterances kept for offline debugging
COMMAND_WAV_KEEP = 10

# A play request must contain a command verb. Without one, the "title" is usually someone else's sentence
# (a meeting in English became play_song "Feelin' the Responsibility" after a false wake on 2026-11-06).
COMMAND_VERB_RE = re.compile(
    r"\b(reproduce|reprodúceme|reproducir|reproduzca|pon|ponme|pónme|poner|pones|quiero (?:oír|oir|escuchar)|escuchar|"
    r"toca|tócame|play|posa|posa'm|posam|fica|reprodueix)\b", re.IGNORECASE)


def has_command_verb(transcript) -> bool:
    return bool(COMMAND_VERB_RE.search(transcript or ""))


ACTIONS = {"play_song", "play_artist", "play_album", "play_playlist", "stop", "pause", "resume", "skip", "unknown"}

PROMPT = (
    "Eres el parser de un asistente de música en español (España). El usuario acaba de decir la frase de activación "
    "\"okey música\" y a continuación una orden, que puede estar en el audio. "
    "Devuelve SOLO un JSON con estas claves: "
    "action (uno de: play_song, play_artist, play_album, play_playlist, stop, pause, resume, skip, unknown), "
    "query (el título de la canción, nombre del artista, álbum o playlist tal como lo diría el usuario, en su idioma original, o null), "
    "artist (artista si se menciona además del título, o null), "
    "artist_alternatives (lista de hasta 2 artistas alternativos si no estás seguro de haber entendido bien el nombre, o []), "
    "transcript (transcripción literal de la orden), "
    "library_match (si la orden se refiere claramente a una entrada de la biblioteca del usuario que se adjunta, esa entrada copiada "
    "literalmente, letra por letra; si no, null. La biblioteca solo sirve para rellenar library_match: nunca cambies query, artist ni transcript por ella). "
    "Conserva títulos y nombres en el idioma en que se oyen (catalán, inglés, portugués...), nunca los traduzcas a ningún idioma: "
    "'bon dia' se devuelve como 'Bon dia' y 'mi caballo percherón' se devuelve en español tal cual. "
    "Muchos artistas son internacionales (The Strokes, Queen, Rosalía): fíate del audio. "
    "El transcript es literal: solo palabras que se oyen, sin completar ni inventar. "
    "Ejemplos: 'reproduce bohemian rhapsody de queen' -> play_song, query 'Bohemian Rhapsody', artist 'Queen'. "
    "'pon algo de rosalía' -> play_artist, query 'Rosalía'. 'pon el disco el madrileño' -> play_album, query 'El Madrileño'. "
    "'siguiente' -> skip. 'para' -> stop. 'pausa' -> pause. 'sigue' -> resume. "
    "Si solo se nombra un artista sin título ('reproduce billie eilish', 'pon queen') -> play_artist, nunca play_song. "
    "Escribe los nombres de artistas conocidos con su grafía oficial (Billie Eilish, The Strokes, La Gossa Sorda). "
    "Si solo oyes la frase de activación, o un verbo suelto sin título ('reproduce', 'pon'): unknown con transcript de lo oído."
)


class LLMCommandParser:
    def __init__(self, library=None):
        self.client = None
        self.library = library  # library.Library: labels for the prompt and the closed set for library_match
        self._requests = []  # timestamps of the requests made, for the hourly and daily caps
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            logger.warning("GEMINI_API_KEY not set, LLM parser disabled")
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=key)
            logger.info(f"LLM parser ready ({GEMINI_MODEL}, audio={GEMINI_USE_AUDIO})")
        except Exception as e:
            logger.error(f"Could not init Gemini client: {e}")

    @property
    def available(self) -> bool:
        return self.client is not None

    @staticmethod
    def _wav(audio: bytes, sample_rate: int) -> bytes:
        bio = io.BytesIO()
        with wave.open(bio, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(audio)
        return bio.getvalue()

    @staticmethod
    def _keep_wav(wav: bytes):
        try:
            os.makedirs(COMMAND_WAV_DIR, exist_ok=True)
            with open(os.path.join(COMMAND_WAV_DIR, time.strftime("%Y%m%d-%H%M%S") + ".wav"), "wb") as f:
                f.write(wav)
            for old in sorted(glob.glob(os.path.join(COMMAND_WAV_DIR, "2*.wav")))[:-COMMAND_WAV_KEEP]:  # own files only
                os.remove(old)
        except OSError:
            pass

    def _within_budget(self) -> bool:
        now = time.time()
        self._requests = [t for t in self._requests if now - t < 86400]
        hour = sum(1 for t in self._requests if now - t < 3600)
        if hour >= GEMINI_MAX_PER_HOUR or len(self._requests) >= GEMINI_MAX_PER_DAY:
            logger.warning(f"Gemini request cap reached ({hour} this hour, {len(self._requests)} today): command not sent")
            return False
        self._requests.append(now)
        logger.info(f"Gemini request {hour + 1} this hour, {len(self._requests)} today")
        return True

    @staticmethod
    def _norm(text: str) -> str:
        import unicodedata
        return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()

    def _ground_artist(self, data: dict, action: str) -> dict:
        """Drop an artist the model did not hear.

        The known-artists list makes the model attribute unrelated titles to a family favourite
        ("reproduce patufet" became play_artist El Pot Petit). If the artist's words do not appear in
        the model's own literal transcript, the artist is removed and an artist action becomes a song search.
        """
        artist, transcript = data.get("artist"), data.get("transcript") or ""
        if not artist or not transcript:
            return data
        words = [w for w in self._norm(artist).split() if len(w) > 2]
        t = self._norm(transcript)
        if words and not any(w in t for w in words):
            logger.info(f"Artist '{artist}' not heard in '{transcript}': dropping it")
            data = dict(data, artist=None)
            if action == "play_artist":
                query = data.get("query") or ""
                heard = self._norm(query)
                if not heard or not any(w in t for w in heard.split() if len(w) > 2):
                    # The query was the invented artist too: search what was actually said
                    import re
                    said = re.sub(r"^(reproduce|pon|ponme|escuchar|quiero escuchar|pon música de|reproduce música de)\s+", "", transcript.strip(), flags=re.IGNORECASE)
                    data["query"] = said
                data["action"] = "play_song"
        return data

    def parse(self, command: dict) -> Optional[dict]:
        if not self.client or not self._within_budget():
            return None
        from google.genai import types
        contents = [PROMPT]
        known = list(dict.fromkeys(list(KNOWN_ARTISTS) + (self.library.artist_names() if self.library else [])))
        if known:
            contents.append("Artistas que esta familia escucha a menudo, solo para acertar la grafía si el audio se parece mucho a uno de ellos. "
                            "Nunca añadas un artista que no se oiga ni adaptes el título a su repertorio o idioma: " + ", ".join(known))
        hint = self.library.hint_text() if self.library else ""
        if hint:
            contents.append("Biblioteca del usuario (favoritos, playlists y lo más escuchado), una entrada por elemento separadas por punto y coma:\n" + hint)
        hint = command.get("transcript") or ""
        if GEMINI_USE_AUDIO and command.get("audio"):
            # The local Vosk transcript is deliberately not sent: with foreign names it biases the
            # model towards its own mistakes ("strauss" for The Strokes). The audio alone does better.
            wav = self._wav(command["audio"], command["sample_rate"])
            self._keep_wav(wav)
            contents.append(types.Part.from_bytes(data=wav, mime_type="audio/wav"))
        elif hint:
            contents.append(f"Orden transcrita: '{hint}'")
        else:
            return None
        t0 = time.time()
        try:
            r = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_level="minimal"),
                ),
            )
            data = json.loads(r.text)
        except Exception as e:
            logger.error(f"Gemini parse failed after {time.time() - t0:.1f}s: {e}")
            return None
        logger.info(f"Gemini ({time.time() - t0:.1f}s): {data}")
        action = data.get("action") if data.get("action") in ACTIONS else "unknown"
        data = self._ground_artist(data, action)
        action = data.get("action") if data.get("action") in ACTIONS else "unknown"
        # 'unknown' is an answer (the model heard it and it is not a music command), not a failure
        alts = [a for a in (data.get("artist_alternatives") or []) if isinstance(a, str) and a]
        match = data.get("library_match") if isinstance(data.get("library_match"), str) else None
        if match and not (self.library and self.library.lookup(match)):
            logger.info(f"library_match '{match}' is not in the library: ignored")
            match = None
        return {"action": action, "query": data.get("query"), "artist": data.get("artist"), "artist_alternatives": alts[:2],
                "transcript": data.get("transcript"), "library_match": match}
