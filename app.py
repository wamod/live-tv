import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "message": "Movie Scraper API is running successfully!"
    })

@app.route("/api/fushaar", methods=["GET"])
def get_fushaar_movie():
    movie_title = request.args.get("title")
    
    if not movie_title:
        return jsonify({"status": "error", "message": "Please provide a movie title (?title=...)"}), 400

    try:
        encoded_title = urllib.parse.quote(movie_title)
        search_url = f"https://www.fushaar.com/?s={encoded_title}"
        
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to reach search source"}), 500

        soup = BeautifulSoup(response.text, "html.parser")
        
        first_result = soup.select_one("article.poster a")
        if not first_result:
            first_result = soup.select_one(".poster a")
            
        if not first_result or not first_result.get("href"):
            return jsonify({"status": "not_found", "message": "Movie not found on Fushaar"}), 404

        raw_href = first_result["href"]
        
        # تصحيح مسار رابط الفيلم
        if raw_href.startswith("http"):
            movie_page_url = raw_href
        elif raw_href.startswith("//"):
            movie_page_url = "https:" + raw_href
        else:
            if not raw_href.startswith("/"):
                raw_href = "/" + raw_href
            movie_page_url = "https://www.fushaar.com" + raw_href

        # فتح صفحة الفيلم
        movie_response = requests.get(movie_page_url, headers=HEADERS, timeout=10)
        movie_soup = BeautifulSoup(movie_response.text, "html.parser")
        
        stream_url = ""

        # 1. البحث عن إطار العرض (iframe)
        iframes = movie_soup.find_all("iframe")
        for iframe in iframes:
            src = iframe.get("src") or iframe.get("data-src")
            if src and ("player" in src or "embed" in src or "fushaar" in src or "vidsrc" in src or "autoembed" in src):
                stream_url = src
                break
            elif src and not stream_url:
                stream_url = src

        # 2. إذا لم يجد iframe، يبحث عن فيديو مباشر (source)
        if not stream_url:
            video_source = movie_soup.select_one("video source") or movie_soup.select_one("video")
            if video_source:
                stream_url = video_source.get("src") or video_source.get("data-src", "")

        # 3. البحث في الروابط المضمنة بداخل خيارات المشغلات (Watch Options/Server Select)
        if not stream_url:
            watch_links = movie_soup.select("a[href*='embed'], a[href*='player'], a[href*='watch']")
            if watch_links:
                stream_url = watch_links[0].get("href", "")

        # تصحيح رابط السيرفر المجلوب
        if stream_url:
            if stream_url.startswith("//"):
                stream_url = "https:" + stream_url
            elif stream_url.startswith("/"):
                stream_url = "https://www.fushaar.com" + stream_url
        else:
            stream_url = movie_page_url

        return jsonify({
            "status": "success",
            "title": movie_title,
            "embed_url": stream_url,
            "source_page": movie_page_url
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
