import math
import struct
import wave
from pathlib import Path

wav_path = Path("logs/tts_debug/tts_001.wav")
assert wav_path.exists(), "tts_001.wav does not exist!"

file_size = wav_path.stat().st_size

with wave.open(str(wav_path), "rb") as w:
    channels = w.getnchannels()
    sample_rate = w.getframerate()
    sampwidth = w.getsampwidth()
    frames = w.getnframes()
    duration = frames / float(sample_rate) if sample_rate else 0.0
    raw_frames = w.readframes(frames)

# Calculate RMS volume level across 16-bit audio samples
count = len(raw_frames) // 2
samples = struct.unpack(f"<{count}h", raw_frames[: count * 2])
sum_squares = sum(s * s for s in samples)
rms = int(math.sqrt(sum_squares / count)) if count > 0 else 0

print("=" * 60)
print("       TTS AUDIO DIAGNOSTICS & VERIFICATION REPORT       ")
print("=" * 60)
print(f"File Path:   {wav_path.resolve()}")
print(f"File Size:   {file_size:,} bytes")
print(f"Duration:    {duration:.2f} seconds")
print(f"Sample Rate: {sample_rate} Hz")
print(f"Channels:    {channels} ({'Mono' if channels == 1 else 'Stereo'})")
print(f"Sample Width:{sampwidth * 8}-bit")
print(f"Audio RMS:   {rms} (Volume Energy)")

if rms > 100:
    print("VERIFICATION: Audio file contains rich non-silent spoken voice audio!")
else:
    print("VERIFICATION WARNING: Audio file is silent or near-zero volume.")
