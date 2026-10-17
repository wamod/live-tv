import os
import re
import base64
from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "On-Demand Stream Scraper API is running!"})

def get_direct_stream(iframe_url):
    if not iframe_url:
        return ""
    
    # تصحيح الرابط إذا كان يبدأ بـ //
    full_iframe_url = f"https:{iframe_url}" if iframe_url.startswith("//") else iframe_url

    try:
        headers = { 
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://d.syrlive.com/',
            'Origin': 'https://d.syrlive.com',
            'Accept': '*/*'
        }
        response = requests.get(full_iframe_url, headers=headers, timeout=10)
        data = response.text

        # 1. البحث عن روابط m3u8 الصريحة
        m3u8_regex = r'https?://[\w\.-]+/.+?\.m3u8[^\s"\']*'
        matches = re.findall(m3u8_regex, data)
        if matches:
            return matches[0].replace('\\', '')

        # 2. البحث عن الروابط داخل سمة "source" في المشغل
        source_match = re.search(r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', data, re.IGNORECASE)
        if source_match:
            return source_match.group(1)

        # 3. البحث عن روابط Base64 (إذا كان المشغل يشفر الرابط)
        base64_regex = r'["\']([A-Za-z0-9+/]{50,})={0,2}["\']'
        b64_matches = re.findall(base64_regex, data)
        for b64 in b64_matches:
            try:
                decoded = base64.b64decode(b64).decode('utf-8')
                if '.m3u8' in decoded:
                    url_match = re.search(r'https?://[\w\.-]+/.+?\.m3u8[^\s"\']*', decoded, re.IGNORECASE)
                    if url_match:
                        return url_match.group(0)
            except Exception:
                pass

        return ""
    except Exception as e:
        print(f"⚠️ فشل الوصول للمشغل: {e}")
        return ""

@app.route("/api/get-stream", methods=["GET"])
def get_stream():
    # استقبال رابط صفحة العرض أو التفاصيل من تطبيق الأندرويد
    target_url = request.args.get("url", "").strip()
    
    if not target_url:
        return jsonify({"status": "error", "message": "الرجاء إرسال رابط الصفحة (url)"}), 400

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # البحث عن الـ iframe الخاص بالمشغل
        iframe = soup.find('iframe')
        iframe_src = ""
        if iframe:
            iframe_src = iframe.get('src', '') or iframe.get('data-src', '')
            if iframe_src.startswith('//'):
                iframe_src = 'https:' + iframe_src

        direct_m3u8 = ""
        if iframe_src:
            direct_m3u8 = get_direct_stream(iframe_src)

        return jsonify({
            "status": "success",
            "target_url": target_url,
            "iframe_url": iframe_src,
            "direct_stream": direct_m3u8
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
