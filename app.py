import os
import re
import urllib.parse
import cloudscraper
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

# إنشاء كاشط ذكي يتجاوز حماية Cloudflare وربوتات الحماية
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'android',
        'desktop': False
    }
)

TIMEOUT = 20


def get_page(url):
    response = scraper.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def extract_player_links(page_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    # روابط iframe
    for iframe in soup.find_all("iframe"):
        src = (
            iframe.get("src")
            or iframe.get("data-src")
            or iframe.get("data-lazy-src")
        )

        if not src or src == "about:blank":
            continue

        full_url = urljoin(page_url, src)
        host = urlparse(full_url).hostname or ""

        if host.endswith("facebook.com"):
            continue

        links.append({
            "type": "embed",
            "url": full_url
        })

    # روابط الفيديو المباشرة
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src") or tag.get("data-src")

        if src:
            links.append({
                "type": "video",
                "url": urljoin(page_url, src)
            })

    # روابط التشغيل الموجودة في خصائص HTML
    for tag in soup.find_all(True):
        for attr in (
            "data-url",
            "data-video",
            "data-src",
            "href"
        ):
            value = tag.get(attr)

            if not value or not isinstance(value, str):
                continue

            if re.search(
                r"\.(m3u8|mp4|mpd)(?:$|[?#])",
                value,
                re.IGNORECASE
            ):
                links.append({
                    "type": "video",
                    "url": urljoin(page_url, value)
                })

    # إزالة التكرار
    unique = []
    seen = set()

    for item in links:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "message": "Movie and Series Search API (Cloudflare Bypassed) is running!"
    })


@app.route("/api/search", methods=["GET"])
def search():
    title = request.args.get("title", "").strip()
    kind = request.args.get("type", "all").strip().lower()

    if not title:
        return jsonify({
            "status": "error",
            "message": "اكتب اسم الفيلم أو المسلسل"
        }), 400

    if kind not in ("all", "movie", "series"):
        return jsonify({
            "status": "error",
            "message": "type must be all, movie or series"
        }), 400

    try:
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://a.qfilm.tv/?s={encoded_title}"
        
        response = get_page(search_url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        first_result = soup.select_one("div.result-item a, article a, .item a, .poster a, h3.title a")
            
        if not first_result or not first_result.get("href"):
            return jsonify({
                "status": "not_found",
                "message": "لم يتم العثور على نتائج مطابقة لهذا العنوان"
            }), 404

        movie_page_url = urljoin(search_url, first_result["href"])

        movie_response = get_page(movie_page_url)
        links = extract_player_links(movie_response.url, movie_response.text)

        return jsonify({
            "status": "success",
            "title": title,
            "type": kind,
            "source_page": movie_response.url,
            "count": len(links),
            "links": links
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "تعذر الاتصال بمصدر البحث أو تجاوز الحماية",
            "details": str(error)
        }, 502)


@app.route("/api/extract", methods=["GET"])
def extract():
    page_url = request.args.get("url", "").strip()

    if not page_url:
        return jsonify({
            "status": "error",
            "message": "أرسل رابط صفحة المحتوى عبر ?url="
        }), 400

    parsed = urlparse(page_url)

    if parsed.scheme != "https" or not parsed.hostname:
        return jsonify({
            "status": "error",
            "message": "يجب إدخال رابط HTTPS صالح"
        }), 400

    try:
        response = get_page(page_url)
        links = extract_player_links(
            response.url,
            response.text
        )

        return jsonify({
            "status": "success",
            "source_page": response.url,
            "count": len(links),
            "links": links
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "تعذر جلب الصفحة",
            "details": str(error)
        }, 502)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
