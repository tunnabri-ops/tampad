import os
import re
import time
import requests

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from fastapi.requests import Request

app = FastAPI(
    title="Tapmad M3U API with 403 Bypass Proxy",
    description="M3U Playlist API and Advanced Proxy Stream for Tapmad",
    version="3.2.0"
)

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "sm-monirulislam/Tapmad_Auto_Update_Playlist/"
    "refs/heads/main/tapmad_sm.m3u"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.tapmad.com/",
    "Origin": "https://www.tapmad.com",
    "Accept": "*/*"
}

TIMEOUT = 25

# ১ মিনিটের স্মার্ট ক্যাশ মেমোরি
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


def parse_playlist(content, base_url=""):
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
            original_url = line
            if base_url:
                proxied_url = f"{base_url}/proxy?url={requests.utils.quote(original_url, safe='')}"
                current["url"] = proxied_url
            else:
                current["url"] = original_url

            channels.append(current)
            current = None

    return channels


@app.get("/")
def home(request: Request):
    return {
        "success": True,
        "status": "online",
        "service": "Tapmad M3U API with 403 Bypass",
        "version": "3.2.0",
        "endpoints": {
            "playlist": "/playlist.m3u",
            "channels": "/api/channels",
            "proxy": "/proxy?url=STREAM_URL",
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
    base_url = str(request.base_url).rstrip("/")
    content = fetch_playlist()
    
    lines = content.splitlines()
    new_lines = []
    
    for line in lines:
        line_str = line.strip()
        if line_str and not line_str.startswith("#"):
            proxied_url = f"{base_url}/proxy?url={requests.utils.quote(line_str, safe='')}"
            new_lines.append(proxied_url)
        else:
            new_lines.append(line_str)
            
    modified_content = "\n".join(new_lines)

    return PlainTextResponse(
        modified_content,
        media_type="audio/x-mpegurl",
        headers={
            "Content-Disposition": 'inline; filename="tapmad_sm.m3u"',
            "Cache-Control": "no-store"
        }
    )


@app.get("/proxy")
def proxy_stream(url: str):
    """
    403 Forbidden বাইপাস করার জন্য আপডেট করা স্ট্রিমিং প্রক্সি রাউট
    """
    try:
        proxy_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://www.tapmad.com/",
            "Origin": "https://www.tapmad.com",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        req = requests.get(url, headers=proxy_headers, stream=True, timeout=TIMEOUT, allow_redirects=True)
        
        def generate():
            for chunk in req.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        content_type = req.headers.get("content-type", "video/mp2t")
        
        return StreamingResponse(
            generate(),
            status_code=req.status_code,
            media_type=content_type if content_type else "video/mp2t"
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Proxy failed: {e}")


@app.get("/api/channels")
def get_channels(request: Request):
    base_url = str(request.base_url).rstrip("/")
    content = fetch_playlist()
    channels = parse_playlist(content, base_url)

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
        "message": "Tapmad playlist cache forcefully refreshed",
        "total": len(channels)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SERVER_PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
