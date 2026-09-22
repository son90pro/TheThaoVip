import requests
import re

url = "https://phalang.live/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    html_text = response.text
    
    m3u_content = "#EXTM3U\n"
    pattern = r'href=["\']([^"\']*\.m3u8[^"\']*)["\']'
    matches = re.findall(pattern, html_text)
    
    for idx, stream_url in enumerate(matches, 1):
        m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp", Trận đấu {idx}\n'
        m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
        m3u_content += f'{stream_url}\n\n'
        
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
        
    print("Thành công!")
except Exception as e:
    print(f"Lỗi: {e}")
  
