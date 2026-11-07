import os
import re
import requests

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.requests import Request

app = FastAPI(
    title="Universal M3U API with Proxy",
    description="M3U Playlist API and Proxy Stream for your own player",
    version="2.1.0"
)

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "sm-monirulislam/Tapmad_Auto_Update_Playlist/"
    "refs/heads/main/tapmad_sm.m3u"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
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
            # স্ট্রিম লিংকগুলোকে আমাদের প্রক্সি রুটের মাধ্যমে রি-রাইট করা হচ্ছে
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
        "service": "Universal M3U API with Proxy",
        "version": "2.1.0",
        "endpoints": {
            "playlist": "/playlist.m3u",
            "channels": "/api/channels",
            "proxy": "/proxy?url=STREAM_URL",
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
    
    # অরিজিনাল মিউথ্রিউ লাইনের লিংকগুলোকে প্রক্সি লিংকে রূপান্তর করা
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
            "Content-Disposition": 'inline; filename="playlist.m3u"',
            "Cache-Control": "no-store"
        }
    )


@app.get("/proxy")
def proxy_stream(url: str):
    """
    ট্যাপমাড বা অন্যান্য সিডিএন লিংক বাইপাস করার জন্য প্রক্সি স্ট্রিম রাউট
    """
    try:
        req = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT)
        
        def generate():
            for chunk in req.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        # রেসপন্স হেডার ও কনটেন্ট টাইপ ঠিক রাখা
        content_type = req.headers.get("content-type", "video/mp2t")
        
        return Response(
            generate(),
            status_code=req.status_code,
            media_type=content_type
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
    content = fetch_playlist()
    channels = parse_playlist(content)

    return {
        "success": True,
        "message": "Playlist fetched successfully",
        "total": len(channels)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SERVER_PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
