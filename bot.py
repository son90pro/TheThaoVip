import requests
import re

# Trang web lấy nguồn stream
url = "https://phalang.live/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

m3u_content = "#EXTM3U\n\n"

try:
    response = requests.get(url, headers=headers, timeout=15)
    html_text = response.text
    
    # Tìm tất cả link .m3u8 trên trang web
    matches = re.findall(r'(https?://[^\s\'"]+\.m3u8[^\s\'"]*)', html_text)
    
    if matches:
        for idx, stream_url in enumerate(set(matches), 1):
            m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp", Trận đấu {idx}\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
            m3u_content += f'{stream_url}\n\n'
    else:
        # Nếu chưa tìm thấy link live tự động, thêm sẵn link mẫu/kênh test
        m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp", Kênh Thể Thao 1 (Demo)\n'
        m3u_content += 'https://phalang.live/\n\n'

except Exception as e:
    print(f"Lỗi: {e}")
    m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp", Dang cap nhat...\n'
    m3u_content += 'https://phalang.live/\n\n'

with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("Đã cập nhật playlist.m3u!")

