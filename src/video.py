"""이미지+음성 → 슬라이드 클립 → 하나의 mp4."""
import subprocess

def _dur(audio):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", audio], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

def clip(image, audio, out, pad=0.6):
    d = _dur(audio) + pad
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", image, "-i", audio,
                    "-t", f"{d:.2f}", "-af", f"apad=pad_dur={pad}", "-c:v", "libx264", "-preset", "veryfast",
                    "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "aac", "-b:a", "160k",
                    "-vf", "scale=1920:1080", out], check=True)

def concat(clips, out, listfile):
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listfile,
                    "-c", "copy", out], check=True)
