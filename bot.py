import requests
from bs4 import BeautifulSoup
import re

url = "https://phalang.live/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://phalang.live/"
}

m3u_content = "#EXTM3U\n\n"

try:
    session = requests.Session()
    response = session.get(url, headers=headers, timeout=15)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Tìm tất cả các link iframe hoặc đường dẫn luồng phát từ trang chính
        stream_links = []
        
        # Bóc tách trực tiếp các chuỗi .m3u8 hoặc link Embed Player
        raw_matches = re.findall(r'https?://[^\s\'"]+(?:\.m3u8|/embed/[^\s\'"]+|/live/[^\s\'"]+)', response.text)
        for link in raw_matches:
            if link not in stream_links:
                stream_links.append(link)
                
        # 2. Tạo danh sách phát M3U
        if stream_links:
            for idx, stream in enumerate(stream_links, 1):
                m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Trận đấu {idx}\n'
                m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
                m3u_content += f'{stream}\n\n'
        else:
            # Nếu chưa đến giờ bóng lăn (chưa có luồng phát live)
            m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Chưa có trận đấu nào đang phát sóng\n'
            m3u_content += 'https://phalang.live/\n\n'

except Exception as e:
    print(f"Lỗi cào dữ liệu Phá Làng TV: {e}")
    m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Lỗi kết nối máy chủ\n'
    m3u_content += 'https://phalang.live/\n\n'

# Ghi ra file playlist.m3u
with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("Đã cập nhật dữ liệu Phá Làng TV thành công!")

