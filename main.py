
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Tapmad M3U Playlist")

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "sm-monirulislam/Tapmad_Auto_Update_Playlist/"
    "refs/heads/main/tapmad_sm.m3u"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

@app.get("/")
def home():
    return {
        "status": "online",
        "name": "Tapmad M3U Playlist",
        "playlist": "/playlist.m3u"
    }

@app.get("/playlist.m3u")
def playlist():
    try:
        response = requests.get(
            SOURCE_URL,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()

        content = response.text

        if not content.lstrip().startswith("#EXTM3U"):
            raise ValueError("Invalid M3U playlist")

        return PlainTextResponse(
            content,
            media_type="audio/x-mpegurl",
            headers={
                "Content-Disposition":
                    'inline; filename="tapmad.m3u"',
                "Cache-Control": "no-cache"
            }
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Playlist loading failed: {error}"
        )
