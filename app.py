import os
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Direct Stream API"})

@app.route("/api/stream", methods=["GET"])
def get_stream():
    tmdb_id = request.args.get("tmdb_id", "").strip()
    
    if not tmdb_id:
        return jsonify({"status": "error", "message": "أدخل tmdb_id"}), 400

    # سيرفرات مشغلات مباشرة بدون إعلانات مزعجة
    servers = [
        f"https://vidsrc.to/embed/movie/{tmdb_id}",
        f"https://autoembed.to/movie/tmdb/{tmdb_id}",
        f"https://2embed.org/embed/movie?tmdb={tmdb_id}"
    ]

    return jsonify({
        "status": "success",
        "tmdb_id": tmdb_id,
        "embed_url": servers[0],
        "all_servers": servers
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
