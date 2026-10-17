import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

app = Flask(__name__)

# رأس الطلب لتجاوز متصفحات المتصفح العادية
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}


@app.route("/", methods=["GET"])
def home():
    return jsonify(
        {
            "status": "online",
            "message": "Movie Scraper API is running successfully!",
        }
    )


@app.route("/api/fushaar", methods=["GET"])
def get_fushaar_movie():
    # استقبال اسم الفيلم من رابط الطلب (e.g. /api/fushaar?title=Avatar)
    movie_title = request.args.get("title")

    if not movie_title:
        return jsonify(
            {"status": "error", "message": "Please provide a movie title (?title=...)"}
        ), 400

    try:
        # 1. ترميز اسم الفيلم للبحث في URL
        encoded_title = urllib.parse.quote(movie_title)
        search_url = f"https://www.fushaar.com/?s={encoded_title}"

        # 2. إرسال طلب البحث إلى فشار
        response = requests.get(search_url, headers=HEADERS, timeout=10)

        if response.status_code != 200:
            return jsonify(
                {"status": "error", "message": "Failed to reach search source"}
            ), 500

        soup = BeautifulSoup(response.text, "html.parser")

        # 3. استخراج أول نتيجة بحث (رابط صفحة الفيلم)
        first_result = soup.select_one("article.poster a")
        if not first_result:
            # محاولة البحث عبر محدد آخر إذا تطلب الأمر
            first_result = soup.select_one(".poster a")

        if not first_result or not first_result.get("href"):
            return jsonify(
                {"status": "not_found", "message": "Movie not found on Fushaar"}
            ), 404

        movie_page_url = first_result["href"]

        # 4. فتح صفحة الفيلم لاستخراج رابط الفيديو أو المشغل
        movie_response = requests.get(movie_page_url, headers=HEADERS, timeout=10)
        movie_soup = BeautifulSoup(movie_response.text, "html.parser")

        # البحث عن وسوم الفيديو أو Iframe التضمين
        embed_iframe = movie_soup.select_one("iframe")
        video_source = movie_soup.select_one("video source")

        stream_url = ""
        if embed_iframe and embed_iframe.get("src"):
            stream_url = embed_iframe["src"]
        elif video_source and video_source.get("src"):
            stream_url = video_source["src"]

        if not stream_url:
            # إذا لم يُعثر على مشغل مباشر، يتم إرجاع رابط الصفحة الرسمية للفيلم
            stream_url = movie_page_url

        # 5. إرجاع النتيجة بتنسيق JSON إلى تطبيق الأندرويد
        return jsonify(
            {
                "status": "success",
                "title": movie_title,
                "embed_url": stream_url,
                "source_page": movie_page_url,
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # الحصول على المنفذ المخصص من بيئة التشغيل على Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
