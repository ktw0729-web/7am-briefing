"""텍스트 → 음성(mp3). edge-tts(무료) 사용. 필요시 다른 TTS로 교체."""
import asyncio, os, subprocess, edge_tts

VOICE = "ko-KR-SunHiNeural"   # 남성: ko-KR-InJoonNeural

async def _run(text, path, rate):
    await edge_tts.Communicate(text, VOICE, rate=rate).save(path)

def speak(text: str, path: str, rate: str = "+5%"):
    if os.getenv("FAKE_TTS"):  # 네트워크 없이 파이프라인만 테스트: 글자수 비례 무음 생성
        sec = max(2, len(text) / 5)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", str(sec), "-q:a", "9", path], check=True)
        return
    asyncio.run(_run(text, path, rate))
