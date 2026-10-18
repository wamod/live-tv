import os
import time
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# بدء Playwright ومتصفح Chromium عالميًا (لإعادة الاستخدام وتجنب بدء متصفح جديد في كل طلب)
playwright = sync_playwright().start()
browser = playwright.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]
)

def sniff_stream(target_url, timeout=30):
    """
    زيارة الصفحة المستهدفة، ومراقبة الشبكة، واستخراج رابط m3u8
    """
    stream_url = None
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720}
    )
    page = context.new_page()

    # دالة رد الاتصال الأساسية: مراقبة جميع الاستجابات
    def handle_response(response):
        nonlocal stream_url
        # تصفية الروابط التي تحتوي على m3u8 (استبعاد الإعلانات أو مقاطع الفيديو القصيرة، يمكنك إضافة المزيد من شروط التصفية حسب الحاجة)
        if ".m3u8" in response.url and stream_url is None:
            # التحقق من أن رمز الحالة طبيعي
            if response.status == 200:
                stream_url = response.url
                print(f"[+] تم التقاط رابط البث: {stream_url}")

    page.on("response", handle_response)

    try:
        # زيارة الصفحة، والانتظار حتى اكتمال domcontentloaded (لا تنتظر اكتمال جميع الموارد، لتجنب البطء الشديد)
        page.goto(target_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        
        # الانتظار الإضافي لعدة ثوانٍ، للسماح للمشغل بإرسال طلب m3u8
        # إذا كان الموقع يحتاج إلى النقر على زر التشغيل يدويًا، يمكنك إضافة page.click('selector') هنا
        page.wait_for_timeout(8000)  # انتظار 8 ثوانٍ
        
        # إذا لم يتم الالتقاط، حاول مرة أخرى الانتظار لفترة أطول قليلاً
        if not stream_url:
            page.wait_for_timeout(5000)
            
    except Exception as e:
        print(f"[!] خطأ أثناء الزيارة: {e}")
    finally:
        context.close()

    return stream_url


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Stream Sniffer API (Playwright) is running!"})


@app.route("/api/get-stream", methods=["GET"])
def get_stream():
    target_url = request.args.get("url", "").strip()
    if not target_url:
        return jsonify({"status": "error", "message": "الرجاء توفير رابط الصفحة (url)"}), 400

    stream = sniff_stream(target_url)

    if stream:
        return jsonify({
            "status": "success",
            "target_url": target_url,
            "direct_stream": stream
        })
    else:
        return jsonify({
            "status": "error",
            "message": "لم يتم التقاط رابط m3u8، قد يكون الموقع بحاجة إلى النقر على التشغيل، أو أن الرابط مشفر، أو أن المهلة قصيرة جدًا",
            "target_url": target_url
        }), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
