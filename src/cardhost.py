"""카드 이미지를 공개 URL로 올린다 (같은 저장소의 'cards' 브랜치, 매번 1커밋으로 덮어써서 용량이 늘지 않음).
Threads는 이미지를 '공개 URL'로만 받기 때문에 필요하다. GitHub Actions의 GITHUB_TOKEN을 사용."""
import os, glob, shutil, subprocess, tempfile

def publish(card_dir, run_id):
    """card_dir의 PNG를 cards 브랜치 {run_id}/ 아래에 올리고 {파일명: URL} 반환. 실패하면 {}."""
    repo, tok = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (repo and tok):
        return {}
    pngs = sorted(glob.glob(f"{card_dir}/*.png"))
    if not pngs:
        return {}
    tmp = tempfile.mkdtemp()
    try:
        dest = os.path.join(tmp, run_id); os.makedirs(dest)
        for p in pngs:
            shutil.copy(p, dest)
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        def git(*a):
            subprocess.run(["git", *a], cwd=tmp, check=True, env=env, capture_output=True)
        git("init", "-q", "-b", "cards")
        git("config", "user.name", "github-actions[bot]")
        git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
        git("add", "-A"); git("commit", "-q", "-m", f"cards {run_id}")
        git("push", "-q", "--force", f"https://x-access-token:{tok}@github.com/{repo}.git", "cards:cards")
        return {os.path.basename(p): f"https://raw.githubusercontent.com/{repo}/cards/{run_id}/{os.path.basename(p)}" for p in pngs}
    except Exception as e:
        print("카드 이미지 업로드 실패(텍스트로만 게시):", getattr(e, "stderr", e))
        return {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
