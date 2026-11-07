
import requests
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI(
    title="Tapmad M3U API",
    version="1.0.0"
)

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "sm-monirulislam/Tapmad_Auto_Update_Playlist/"
    "refs/heads/main/tapmad_sm.m3u"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def fetch_playlist():
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

        return content

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"Source unavailable: {error}"
        )


def parse_playlist(content):
    channels = []
    current = {}

    for line in content.splitlines():
        line = line.strip()

        if line.startswith("#EXTINF"):
            name = line.split(",")[-1].strip()

            logo = re.search(r'tvg-logo="([^"]*)"', line)
            group = re.search(r'group-title="([^"]*)"', line)

            current = {
                "name": name,
                "logo": logo.group(1) if logo else "",
                "group": group.group(1) if group else "Other"
            }

        elif line.startswith(("http://", "https://")):
            if current:
                current["url"] = line
                channels.append(current)
                current = {}

    return channels


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Tapmad M3U API",
        "version": "1.0.0",
        "endpoints": [
            "/playlist.m3u",
            "/api/channels",
            "/api/health",
            "/docs"
        ]
    }


@app.get("/playlist.m3u")
def get_m3u():
    content = fetch_playlist()

    return PlainTextResponse(
        content,
        media_type="audio/x-mpegurl",
        headers={"Cache-Control": "no-cache"}
    )


@app.get("/api/channels")
def get_channels():
    content = fetch_playlist()
    channels = parse_playlist(content)

    return JSONResponse({
        "success": True,
        "total": len(channels),
        "channels": channels
    })


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/refresh")
def refresh():
    content = fetch_playlist()
    channels = parse_playlist(content)

    return {
        "success": True,
        "message": "Playlist refreshed",
        "total": len(channels)
    }
