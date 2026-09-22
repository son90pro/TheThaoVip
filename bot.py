import requests
import json
import re

m3u_content = "#EXTM3U\n\n"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://phalang.live/",
    "Origin": "https://phalang.live"
}

# Danh sách các endpoint API thường dùng của các hệ thống web thể thao
api_urls = [
    "https://phalang.live/api/matches",
    "https://phalang.live/api/v1/matches",
    "https://phalang.live/json/matches.json"
]

found_matches = False

# 1. Thử gọi API ẩn của trang web
for api_url in api_urls:
    try:
        res = requests.get(api_url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            # Giả định dữ liệu mảng các trận đấu
            matches = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(matches, list) and len(matches) > 0:
                for match in matches:
                    title = match.get("name") or match.get("title") or f"{match.get('home_team')} vs {match.get('away_team')}"
                    stream_url = match.get("stream_url") or match.get("link") or match.get("m3u8")
                    if stream_url:
                        m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", {title}\n'
                        m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
                        m3u_content += f'{stream_url}\n\n'
                        found_matches = True
                if found_matches:
                    break
    except Exception:
        pass

# 2. Nếu không gọi được API, quét sâu mã HTML bằng Regex Regex quét toàn bộ iframe/hls/m3u8
if not found_matches:
    try:
        main_res = requests.get("https://phalang.live/", headers=headers, timeout=10)
        html_text = main_res.text
        
        # Lấy tất cả link player iframe hoặc luồng stream ẩn trong tập tin JS
        links = re.findall(r'https?://[^\s\'"]+(?:\.m3u8|/embed/[^\s\'"]+|/live/[^\s\'"]+|/player[^\s\'"]*)', html_text)
        
        # Loại bỏ các link trùng lặp
        unique_links = list(set(links))
        
        if unique_links:
            for idx, link in enumerate(unique_links, 1):
                m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Trận trực tiếp {idx}\n'
                m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
                m3u_content += f'{link}\n\n'
            found_matches = True
    except Exception as e:
        print(f"Lỗi quét web: {e}")

# 3. Nếu vẫn bị chặn JS hoàn toàn, ghi nhận kênh tổng hợp nguồn dự phòng
if not found_matches:
    m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Server 1 - Trang Chủ Phá Làng\n'
    m3u_content += '#EXTVLCOPT:http-referrer=https://phalang.live/\n'
    m3u_content += 'https://phalang.live/\n\n'

with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("Đã cập nhật dữ liệu hoàn tất!")
