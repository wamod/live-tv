import cloudscraper
import requests
import json
import os

# رابط قاعدة بيانات Firebase الخاصة بك
FIREBASE_URL = "https://samer-tv-d2f00-default-rtdb.firebaseio.com/movies.json"

# الدومين الجديد والدقيق الذي تم اكتشافه عبر تتبع الطلبات
BASE_URL = "https://api.ossccaarr111.online/"
api_url = f"{BASE_URL}api/movies/?page=1&limit=50"

scraper = cloudscraper.create_scraper()

print("جاري الاتصال بسيرفر OscarTV الجديد وتجاوز الحماية...")
try:
    response = scraper.get(api_url, timeout=15)
    print(f"كود الاستجابة من السيرفر: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        movies_list = data.get("data", data.get("movies", data.get("results", [])))
        
        print(f"✨ تم بنجاح جلب {len(movies_list)} فيلم من الدومين الجديد!")
        
        synced_count = 0
        for movie in movies_list:
            title = movie.get("title_ar", movie.get("title", "بدون عنوان"))
            story = movie.get("story", movie.get("description", ""))
            year = str(movie.get("release_year", 0))
            rating = str(movie.get("rating", 0.0))
            poster = movie.get("poster", "none")
            tmdb_id = str(movie.get("tmdb_id", 0))
            
            # استخراج الروابط بمرونة عالية
            url_low, url_sd, url_hd = "", "", ""
            watch_links = movie.get("watch_links", movie.get("servers", movie.get("sources", [])))
            
            if isinstance(watch_links, list):
                for link in watch_links:
                    quality = str(link.get("quality", link.get("name", ""))).lower()
                    link_url = link.get("url", link.get("link", link.get("file", "")))
                    
                    if "hd" in quality or "1080" in quality or "720" in quality:
                        url_hd = link_url
                    elif "sd" in quality or "480" in quality:
                        url_sd = link_url
                    else:
                        if not url_low: url_low = link_url
                        elif not url_sd: url_sd = link_url
                        elif not url_hd: url_hd = link_url
            
            default_url = url_hd if url_hd else (url_sd if url_sd else url_low)
            
            movie_data = {
                "title": title,
                "description": story,
                "year": "" if year == "0" else year,
                "rating": rating,
                "poster": poster,
                "url_low": url_low,
                "url_sd": url_sd,
                "url_hd": url_hd,
                "url": default_url,
                "tmdb_id": tmdb_id,
                "status": "true",
                "skip_active": "false",
                "skip_from": "0",
                "skip_to": "0",
                "cast": [],
                "crew": []
            }
            
            # رفع البيانات إلى Firebase
            res = requests.post(FIREBASE_URL, json=movie_data)
            if res.status_code == 200:
                synced_count += 1
                print(f"تم رفعه لـ Firebase: {title}")
                
        print(f"\n🎉 تمت المزامنة بنجاح! الإجمالي: {synced_count}")
    else:
        print(f"السيرفر استابح الاتصال لكن كود الخطأ هو: {response.status_code}")
        print(response.text[:300])
except Exception as e:
    print(f"حدث خطأ أثناء الاتصال: {e}")
