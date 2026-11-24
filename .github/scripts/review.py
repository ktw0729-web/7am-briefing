import os, sys, json, subprocess, requests
diff = subprocess.run(["git", "diff", f"origin/{os.environ['BASE']}...HEAD", "--", ".", ":!history", ":!*.lock"], capture_output=True, text=True).stdout[:90000]
rules = open(".github/REVIEW_CHECKLIST.md", encoding="utf-8").read()
r = requests.post("https://api.openai.com/v1/chat/completions",
    headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"].strip()},
    json={"model": os.getenv("OPENAI_MODEL", "gpt-4.1"),
          "messages": [{"role": "system", "content": "당신은 엄격한 코드 검수자다. 한국어로 답한다.\n" + rules},
                       {"role": "user", "content": "다음 변경(diff)을 검수하라.\n\n" + diff}]}, timeout=180)
r.raise_for_status()
body = "## 🔎 ChatGPT 검수\n\n" + r.json()["choices"][0]["message"]["content"]
requests.post(f"https://api.github.com/repos/{os.environ['REPO']}/issues/{os.environ['PR']}/comments",
    headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"},
    json={"body": body}, timeout=30).raise_for_status()
