"""
Audio recording & Speech-to-Text module.
"""
import os
import queue
import threading
import tempfile
import datetime
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

from config import PROJECT_DIR


class AudioRecorder:
    """Ghi âm từ mic/loopback, transcribe bằng Google STT."""

    def __init__(self):
        self.is_recording = False
        self.audio_queue: queue.Queue = queue.Queue()
        self.stream = None
        self.writer = None
        self.wav_path: Optional[str] = None
        self.channels = 1
        self._writer_thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return sd is not None and sf is not None

    def start(self) -> str:
        """Bắt đầu ghi âm. Trả về path file WAV."""
        if not self.available:
            raise RuntimeError("Thiếu sounddevice/soundfile. Cài: pip install sounddevice soundfile")
        if self.is_recording:
            return self.wav_path or ""

        self.is_recording = True
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.wav_path = os.path.join(PROJECT_DIR, f"record_{timestamp}.wav")

        # Thử WASAPI loopback (ghi âm thanh hệ thống), fallback micro
        try:
            extra = None
            if hasattr(sd, "WasapiSettings"):
                extra = sd.WasapiSettings(loopback=True)
            self.channels = 2
            self.stream = sd.InputStream(
                samplerate=44100,
                channels=self.channels,
                callback=self._audio_callback,
                extra_settings=extra,
            )
        except Exception:
            self.channels = 1
            self.stream = sd.InputStream(
                samplerate=44100,
                channels=self.channels,
                callback=self._audio_callback,
            )

        self.writer = sf.SoundFile(
            self.wav_path, mode="w", samplerate=44100,
            channels=self.channels, subtype="PCM_16",
        )
        self.stream.start()

        self._writer_thread = threading.Thread(target=self._write_loop, daemon=True)
        self._writer_thread.start()
        return self.wav_path

    def stop(self) -> Optional[str]:
        """Dừng ghi âm. Trả về path file WAV."""
        self.is_recording = False
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
            if self.writer:
                self.writer.flush()
                self.writer.close()
        except Exception:
            pass
        self.stream = None
        self.writer = None
        return self.wav_path

    def transcribe(self, language: str = "vi-VN") -> str:
        """Chuyển đổi file WAV thành text (Google STT)."""
        if sr is None:
            return "[LỖI] Thiếu SpeechRecognition. Cài: pip install SpeechRecognition"
        if not self.wav_path or not os.path.exists(self.wav_path):
            return "[LỖI] Chưa có bản ghi."

        try:
            recognizer = sr.Recognizer()
            mono_path = self._ensure_mono_16k(self.wav_path)
            with sr.AudioFile(mono_path) as source:
                audio = recognizer.record(source)
            return recognizer.recognize_google(audio, language=language)
        except Exception as e:
            return f"[Nhận dạng lỗi] {e}"

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_queue.put(indata.copy())

    def _write_loop(self):
        while self.is_recording:
            try:
                data = self.audio_queue.get(timeout=0.5)
                if self.channels == 1 and data.ndim > 1:
                    data = data.mean(axis=1, keepdims=True)
                if self.writer:
                    self.writer.write(data)
            except Exception:
                pass

    def _ensure_mono_16k(self, src_path: str) -> str:
        """Convert sang mono 16kHz cho Google STT."""
        try:
            data, sr_hz = sf.read(src_path, always_2d=True)
            mono = data.mean(axis=1)
            target = 16000
            if sr_hz != target:
                x = np.arange(len(mono))
                xp = np.linspace(0, len(mono) - 1, int(len(mono) * target / sr_hz))
                mono = np.interp(xp, x, mono).astype(np.float32)
            out = tempfile.mktemp(prefix="record_mono_", suffix=".wav")
            sf.write(out, mono, samplerate=target, subtype="PCM_16")
            return out
        except Exception:
            return src_path
