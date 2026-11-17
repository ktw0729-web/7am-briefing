"""YouTube Data API 업로드 (refresh token 방식)."""
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def upload(path, title, description, privacy="private", publish_at=None):
    """publish_at(ISO 시각)를 주면 비공개로 올려두었다가 그 시각에 자동 공개된다."""
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": title[:100], "description": description, "categoryId": "25",
                        "defaultLanguage": "ko"},
            "status": {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False}}
    if publish_at:
        body["status"]["publishAt"] = publish_at
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]
