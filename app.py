import os
import re
import urllib.parse
import cloudscraper
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

# إنشاء كاشط ذكي يتجاوز حماية Cloudflare
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

    # استخراج روابط iframe (مشغلات العرض)
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

    # استخراج روابط الفيديو المباشرة
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src") or tag.get("data-src")

        if src:
            links.append({
                "type": "video",
                "url": urljoin(page_url, src)
            })

    # البحث عن روابط التشغيل في خصائص HTML (مثل m3u8 أو mp4)
    for tag in soup.find_all(True):
        for attr in ("data-url", "data-video", "data-src", "href"):
            value = tag.get(attr)

            if not value or not isinstance(value, str):
                continue

            if re.search(r"\.(m3u8|mp4|mpd)(?:$|[?#])", value, re.IGNORECASE):
                links.append({
                    "type": "video",
                    "url": urljoin(page_url, value)
                })

    # إزالة الروابط المكررة
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
        "message": "Cima4U & General Scraper API is running!"
    })


@app.route("/api/cima4u", methods=["GET"])
def get_cima4u_movie():
    title = request.args.get("title", "").strip()

    if not title:
        return jsonify({
            "status": "error",
            "message": "المرجو إدخال اسم الفيلم أو المسلسل عبر ?title="
        }), 400

    try:
        encoded_title = urllib.parse.quote(title)
        # نطاق Cima4U (يمكن تحديث النطاق إذا تغير رابط الموقع الرئيسي)
        search_url = f"https://www.cima4u.cc/search?q={encoded_title}"
        
        response = get_page(search_url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # البحث عن أول نتيجة مطابقة في هيكلة موقع Cima4U
        first_result = soup.select_one("div.GridItem a, div.Thumb a, .MovieItem a, article a, h3 a")
            
        if not first_result or not first_result.get("href"):
            return jsonify({
                "status": "not_found",
                "message": "لم يتم العثور على النتائج في Cima4U"
            }), 404

        movie_page_url = urljoin(search_url, first_result["href"])

        # الدخول لصفحة الفيلم وجلب روابط التشغيل تلقائياً
        movie_response = get_page(movie_page_url)
        links = extract_player_links(movie_response.url, movie_response.text)

        return jsonify({
            "status": "success",
            "title": title,
            "source_page": movie_response.url,
            "count": len(links),
            "links": links
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": "تعذر الاتصال بموقع Cima4U أو جلب البيانات",
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
        return jsonify({
            "status": "error",
            "message": "تعذر جلب الصفحة",
            "details": str(error)
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
