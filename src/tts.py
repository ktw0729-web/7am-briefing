"""텍스트 → 음성(mp3). edge-tts(무료) 사용. 필요시 다른 TTS로 교체."""
import asyncio, os, subprocess, edge_tts

VOICE = os.getenv("TTS_VOICE", "ko-KR-HyunsuMultilingualNeural")   # 대안: ko-KR-SunHiNeural(여), ko-KR-InJoonNeural(남)
FALLBACK = "ko-KR-SunHiNeural"
RATE = os.getenv("TTS_RATE", "+10%")   # 1.1배속

async def _run(text, path, rate, voice=None):
    try:
        await edge_tts.Communicate(text, voice or VOICE, rate=rate).save(path)
    except Exception as e:
        if voice or VOICE == FALLBACK:
            raise
        print("TTS 음성 실패, 기본 음성으로 대체:", e)
        await edge_tts.Communicate(text, FALLBACK, rate=rate).save(path)

def speak(text: str, path: str, rate: str = None, voice: str = None):
    rate = rate or RATE
    if os.getenv("FAKE_TTS"):  # 네트워크 없이 파이프라인만 테스트: 글자수 비례 무음 생성
        sec = max(2, len(text) / 5)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", str(sec), "-q:a", "9", path], check=True)
        return
    asyncio.run(_run(text, path, rate, voice))
