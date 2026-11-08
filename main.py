import os
import re
import time
import requests

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.requests import Request

app = FastAPI(
    title="SonyLIV Direct M3U API",
    description="M3U Playlist API with Direct Source Links (No Proxy)",
    version="2.0.0"
)

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "srhady/SonyLiv/refs/heads/main/sonyliv_playlist.m3u"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sonyliv.com/",
    "Origin": "https://www.sonyliv.com",
    "Accept": "*/*"
}

TIMEOUT = 25

# ১ মিনিটের স্মার্ট ক্যাশ (রিয়েল-টাইম ফ্রেশ লিংক ফেচ করার জন্য)
CACHE_DURATION = 60
cache = {
    "content": None,
    "timestamp": 0
}


def fetch_playlist(force_refresh=False):
    global cache
    current_time = time.time()

    if force_refresh or not cache["content"] or (current_time - cache["timestamp"] > CACHE_DURATION):
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

            cache["content"] = content
            cache["timestamp"] = current_time

        except requests.RequestException as error:
            if not cache["content"]:
                raise HTTPException(
                    status_code=502,
                    detail=f"Source request failed: {error}"
                )
        except ValueError as error:
            if not cache["content"]:
                raise HTTPException(
                    status_code=502,
                    detail=str(error)
                )

    return cache["content"]


def parse_playlist(content):
    channels = []
    current = None

    for line in content.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("#EXTINF"):
            name_match = re.search(r",([^,]*)$", line)
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            group_match = re.search(r'group-title="([^"]*)"', line)

            current = {
                "name": name_match.group(1).strip() if name_match else "Unknown",
                "logo": logo_match.group(1) if logo_match else "",
                "group": group_match.group(1) if group_match else "Other"
            }

        elif current and not line.startswith("#"):
            # সরাসরি অরিজিনাল সোর্স লিংক বসবে, কোনো প্রক্সি থাকবে না
            current["url"] = line
            channels.append(current)
            current = None

    return channels


@app.get("/")
def home(request: Request):
    return {
        "success": True,
        "status": "online",
        "service": "SonyLIV Direct M3U API",
        "version": "2.0.0",
        "endpoints": {
            "playlist": "/playlist.m3u",
            "channels": "/api/channels",
            "refresh": "/api/refresh",
            "health": "/api/health",
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
def get_playlist(request: Request):
    # প্রক্সি ছাড়া সরাসরি গিটহাবের রিয়েল-টাইম M3U কন্টেন্ট রিটার্ন করবে
    content = fetch_playlist()

    return PlainTextResponse(
        content,
        media_type="audio/x-mpegurl",
        headers={
            "Content-Disposition": 'inline; filename="sonyliv_playlist.m3u"',
            "Cache-Control": "no-store"
        }
    )


@app.get("/api/channels")
def get_channels(request: Request):
    content = fetch_playlist()
    channels = parse_playlist(content)

    return JSONResponse({
        "success": True,
        "total": len(channels),
        "channels": channels
    })


@app.get("/api/refresh")
def refresh_playlist():
    content = fetch_playlist(force_refresh=True)
    channels = parse_playlist(content)

    return {
        "success": True,
        "message": "Playlist cache forcefully refreshed",
        "total": len(channels)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SERVER_PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
