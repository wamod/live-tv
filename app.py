
import os
from urllib.parse import urlparse
from threading import Lock

from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

ALLOWED_HOST = "mobile.farfeshplus.mosalsalatpro.online"

_playwright = None
_browser = None
_browser_lock = Lock()


def get_browser():
    global _playwright, _browser

    with _browser_lock:
        if _browser is None or not _browser.is_connected():
            if _playwright is None:
                _playwright = sync_playwright().start()

            _browser = _playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

        return _browser


def valid_page_url(url):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == ALLOWED_HOST
            and parsed.username is None
            and parsed.password is None
        )
    except Exception:
        return False


def inspect_page(target_url):
    browser = get_browser()
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 720}
    )

    candidates = []
    page = context.new_page()

    def handle_response(response):
        url = response.url
        content_type = response.headers.get(
            "content-type", ""
        ).lower()

        if (
            ".m3u8" in url.lower()
            and response.status == 200
            and (
                "mpegurl" in content_type
                or ".m3u8" in url.lower()
            )
        ):
            if url not in candidates:
                candidates.append(url)

    page.on("response", handle_response)

    try:
        page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=20000
        )

        page.wait_for_timeout(8000)

        title = page.title()

        return {
            "title": title,
            "candidates": candidates
        }

    finally:
        context.close()


@app.get("/")
def home():
    return jsonify({
        "status": "online",
        "message": "Stream API is running"
    })


@app.get("/api/get-stream")
def get_stream():
    target_url = request.args.get("url", "").strip()

    if not target_url:
        return jsonify({
            "status": "error",
            "message": "يرجى إرسال رابط الصفحة ضمن url"
        }), 400

    if not valid_page_url(target_url):
        return jsonify({
            "status": "error",
            "message": "رابط الصفحة غير مسموح"
        }), 400

    try:
        result = inspect_page(target_url)

        if result["candidates"]:
            return jsonify({
                "status": "success",
                "title": result["title"],
                "target_url": target_url,
                "direct_stream": result["candidates"][0],
                "candidates": result["candidates"]
            })

        return jsonify({
            "status": "not_found",
            "title": result["title"],
            "target_url": target_url,
            "message": (
                "لم يتم العثور على رابط M3U8 "
                "في طلبات الشبكة المرصودة"
            )
        }), 404

    except Exception as exc:
        app.logger.exception("Stream inspection failed")

        return jsonify({
            "status": "error",
            "message": "تعذر فحص صفحة الحلقة",
            "details": str(exc)
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
