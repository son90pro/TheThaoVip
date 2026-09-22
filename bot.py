import requests
import json
import re

m3u_content = "#EXTM3U\n\n"
default_logo = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://phalang.live/",
    "Origin": "https://phalang.live"
}

matches_found = []

# Danh sách các API ẩn thường lấy dữ liệu của hệ thống Phá Làng
api_endpoints = [
    "https://phalang.live/api/v1/matches/live",
    "https://phalang.live/api/matches",
    "https://phalang.live/json/matches.json"
]

for api_url in api_endpoints:
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(items, list) and len(items) > 0:
                for item in items:
                    title = item.get("name") or item.get("title") or f"{item.get('home_name')} vs {item.get('away_name')}"
                    stream = item.get("stream_url") or item.get("hls") or item.get("m3u8")
                    if title and stream:
                        matches_found.append((title, stream))
                if matches_found:
                    break
    except Exception:
        pass

# Nếu gọi API kín không được, dùng regex cào thẳng luồng embed công khai
if not matches_found:
    try:
        res = requests.get("https://phalang.live/", headers=headers, timeout=10)
        # Bắt các chuỗi định dạng trận đấu và link hls
        raw_streams = re.findall(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', res.text)
        for idx, stream in enumerate(set(raw_streams), 1):
            matches_found.append((f"Trận Phá Làng Live {idx}", stream))
    except Exception:
        pass

# Ghi file M3U
if matches_found:
    for title, stream in matches_found:
        logo = default_logo
        if "Việt Nam" in title or "Vietnam" in title:
            logo = "https://flagcdn.com/w320/vn.png"
        elif "Hàn Quốc" in title or "Korea" in title:
            logo = "https://flagcdn.com/w320/kr.png"

        m3u_content += f'#EXTINF:-1 tvg-logo="{logo}" group-title="Phá Làng TV", ⚽ {title}\n'
        m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
        m3u_content += f'{stream}\n\n'
else:
    # Nếu bị Cloudflare chặn triệt để IP GitHub, dùng nguồn luồng dự phòng
    m3u_content += f'#EXTINF:-1 tvg-logo="{default_logo}" group-title="Phá Làng TV", ⚽ Kênh Trực Tiếp Phá Làng (Đang phát)\n'
    m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
    m3u_content += 'https://phalang.live/\n\n'

with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("Đã hoàn tất cập nhật!")
