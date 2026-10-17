import os
import re
import urllib.parse
import cloudscraper
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

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

    # 1. استخراج روابط iframe مع استبعاد يوتيوب وفيسبوك
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

        # استبعاد روابط يوتيوب ومواقع التواصل الاجتماعي لعدم جلب الإعلانات
        if "youtube" in host or "youtu.be" in host or host.endswith("facebook.com") or host.endswith("twitter.com"):
            continue

        links.append({
            "type": "embed",
            "url": full_url
        })

    # 2. استخراج روابط التشغيل الموجودة في أزرار أو خصائص خوادم العرض (Servers/Watch options)
    for a in soup.select("a[href*='embed'], a[href*='player'], a[href*='watch'], a[data-url]"):
        href = a.get("href") or a.get("data-url")
        if href and href != "#":
            full_url = urljoin(page_url, href)
            host = urlparse(full_url).hostname or ""
            if "youtube" not in host and "facebook" not in host:
                links.append({
                    "type": "embed",
                    "url": full_url
                })

    # 3. استخراج روابط الفيديو المباشرة (مثل m3u8 أو mp4)
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src") or tag.get("data-src")
        if src:
            links.append({
                "type": "video",
                "url": urljoin(page_url, src)
            })

    for tag in soup.find_all(True):
        for attr in ("data-url", "data-video", "data-src"):
            value = tag.get(attr)
            if value and isinstance(value, str):
                if re.search(r"\.(m3u8|mp4|mpd)(?:$|[?#])", value, re.IGNORECASE):
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
        "message": "Fushaar Scraper API is running successfully!"
    })


@app.route("/api/fushaar", methods=["GET"])
def get_fushaar_movie():
    title = request.args.get("title", "").strip()

    if not title:
        return jsonify({
            "status": "error",
            "message": "المرجو إدخال اسم الفيلم عبر ?title="
        }), 400

    try:
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://www.fushaar.com/?s={encoded_title}"
        
        response = get_page(search_url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        first_result = soup.select_one("article.poster a, .poster a, div.post a, h3 a")
            
        if not first_result or not first_result.get("href"):
            return jsonify({
                "status": "not_found",
                "message": "لم يتم العثور على النتائج في موقع فشار"
            }), 404

        movie_page_url = urljoin(search_url, first_result["href"])

        movie_response = get_page(movie_page_url)
        links = extract_player_links(movie_response.url, movie_response.text)

        # احتياطي: إذا لم يتم العثور على روابط بسبب حماية المشغل، نرجع رابط الصفحة المصدر ليتعامل معها التطبيق
        if not links:
            links.append({
                "type": "page",
                "url": movie_page_url
            })

        return jsonify({
            "status": "success",
            "title": title,
            "source_page": movie_page_url,
            "count": len(links),
            "links": links
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "تعذر الاتصال بموقع فشار",
            "details": str(error)
        }), 502


@app.route("/api/extract", methods=["GET"])
def extract():
    page_url = request.args.get("url", "").strip()
    if not page_url:
        return jsonify({"status": "error", "message": "أرسل الرابط عبر ?url="}), 400

    try:
        response = get_page(page_url)
        links = extract_player_links(response.url, response.text)
        return jsonify({
            "status": "success",
            "source_page": response.url,
            "count": len(links),
            "links": links
        })
    except Exception as error:
        return jsonify({"status": "error", "message": str(error)}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
