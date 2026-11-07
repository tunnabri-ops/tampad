import os
import re
import requests

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI(
    title="Universal M3U API",
    description="M3U Playlist API for your own player",
    version="2.0.0"
)

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "sm-monirulislam/Tapmad_Auto_Update_Playlist/"
    "refs/heads/main/tapmad_sm.m3u"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*"
}

TIMEOUT = 25


def fetch_playlist():
    try:
        response = requests.get(
            SOURCE_URL,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        content = response.text.strip()

        if not content.startswith("#EXTM3U"):
            raise ValueError("Invalid M3U response")

        return content

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"Source request failed: {error}"
        )

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        )


def parse_playlist(content):
    channels = []
    current = None

    for line in content.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("#EXTINF"):
            name_match = re.search(r",([^,]*)$", line)

            logo_match = re.search(
                r'tvg-logo="([^"]*)"', line
            )

            group_match = re.search(
                r'group-title="([^"]*)"', line
            )

            current = {
                "name": (
                    name_match.group(1).strip()
                    if name_match else "Unknown"
                ),
                "logo": (
                    logo_match.group(1)
                    if logo_match else ""
                ),
                "group": (
                    group_match.group(1)
                    if group_match else "Other"
                )
            }

        elif current and not line.startswith("#"):
            current["url"] = line

            channels.append(current)
            current = None

    return channels


@app.get("/")
def home():
    return {
        "success": True,
        "status": "online",
        "service": "Universal M3U API",
        "version": "2.0.0",
        "endpoints": {
            "playlist": "/playlist.m3u",
            "channels": "/api/channels",
            "health": "/api/health",
            "refresh": "/api/refresh",
            "docs": "/docs"
        }
    }


@app.get("/api/health")
def health():
    return {
        "success": True,
        "status": "healthy"
    }


@app.get("/playlist.m3u")
def get_playlist():
    content = fetch_playlist()

    return PlainTextResponse(
        content,
        media_type="audio/x-mpegurl",
        headers={
            "Content-Disposition":
                'inline; filename="playlist.m3u"',
            "Cache-Control": "no-store"
        }
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


@app.get("/api/refresh")
def refresh_playlist():
    content = fetch_playlist()
    channels = parse_playlist(content)

    return {
        "success": True,
        "message": "Playlist fetched successfully",
        "total": len(channels)
    }


@app.get("/api/info")
def playlist_info():
    content = fetch_playlist()
    channels = parse_playlist(content)

    return {
        "name": "Tapmad Playlist",
        "format": "M3U",
        "total_channels": len(channels),
        "source": "GitHub"
    }


if __name__ == "__main__":
    import uvicorn
    # প্যানেল থেকে বরাদ্দকৃত পোর্ট স্বয়ংক্রিয়ভাবে নেওয়ার ব্যবস্থা করা হয়েছে
    port = int(os.environ.get("SERVER_PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
