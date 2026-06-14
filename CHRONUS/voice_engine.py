"""CHRONUS Voice Engine — XTTS-v2 local synthesis."""

import torch


def check_gpu() -> str:
    """Diagnose GPU availability and return best device string."""
    print(f"[GPU] torch.cuda.is_available(): {torch.cuda.is_available()}")
    print(f"[GPU] torch.cuda.device_count(): {torch.cuda.device_count()}")
    print(f"[GPU] torch.version.cuda: {torch.version.cuda}")
    print(f"[GPU] torch.__version__: {torch.__version__}")

    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        mem = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"[GPU] cuda device 0: {name}")
        print(f"[GPU] compute capability: {cap[0]}.{cap[1]}")
        print(f"[GPU] VRAM: {mem:.1f} GB")
        return "cuda"

    print("[GPU] No CUDA device found, using CPU")
    return "cpu"


class VoiceSynthesizer:
    """Local voice synthesis using Coqui TTS XTTS-v2."""

    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        self.device = check_gpu()
        self.gpu = self.device == "cuda"

        device_label = f"CUDA ({torch.cuda.get_device_name(0)})" if self.gpu else "CPU (slow)"
        print(f"[VOICE] XTTS-v2 loading on: {device_label}")

        from TTS.api import TTS
        self.tts = TTS(model_name).to(self.device)
        print(f"[VOICE] Voice engine ready on {self.device}")

    def synthesize(self, text: str, speaker_wav: str, output_path: str = "temp_output.wav", language: str = "en") -> str:
        """Synthesize speech from text using a reference speaker wav.

        Args:
            text: The text to speak.
            speaker_wav: Path to a 30-60s WAV of the target voice.
            output_path: Where to save the output WAV.
            language: Language code (default "en").

        Returns:
            The output_path on success.

        Raises:
            FileNotFoundError: If speaker_wav doesn't exist.
            RuntimeError: If synthesis fails.
        """
        import os
        if not os.path.isfile(speaker_wav):
            raise FileNotFoundError(f"Speaker WAV not found: {speaker_wav}")

        self.tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=output_path,
        )
        return output_path


_voice_instance = None


def get_voice_engine() -> VoiceSynthesizer:
    """Lazy singleton — only loads model on first call."""
    global _voice_instance
    if _voice_instance is None:
        _voice_instance = VoiceSynthesizer()
    return _voice_instance
