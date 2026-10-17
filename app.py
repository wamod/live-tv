import os
import re
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
        
        first_result = soup.select_one("article.poster a") or soup.select_one(".poster a")
            
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
        movie_html = movie_response.text
        movie_soup = BeautifulSoup(movie_html, "html.parser")
        
        stream_url = ""

        # 1. البحث في عناصر iframe بالصفحة
        for iframe in movie_soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src") or iframe.get("data-lazy-src")
            if src and not src.startswith("about:blank") and "facebook" not in src and "twitter" not in src:
                stream_url = src
                break

        # 2. البحث داخل روابط التشغيل (Watch/Embed)
        if not stream_url:
            for a in movie_soup.select("a[href*='embed'], a[href*='player'], a[href*='vidsrc'], a[data-url]"):
                href = a.get("href") or a.get("data-url")
                if href and href != "#":
                    stream_url = href
                    break

        # 3. البحث باستخدام الـ Regex عن أطُر المشغلات أو روابط m3u8/mp4 داخل كود السكربتات
        if not stream_url:
            found_urls = re.findall(r'https?://[^\s\'"]+\.(?:m3u8|mp4)', movie_html)
            if found_urls:
                stream_url = found_urls[0]
            else:
                found_embeds = re.findall(r'https?://[^\s\'"]+(?:embed|player|vidsrc)[^\s\'"]*', movie_html)
                if found_embeds:
                    stream_url = found_embeds[0]

        # تصحيح الرابط المستخرج النهائي
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
