import requests
import re

m3u_content = "#EXTM3U\n\n"

# Danh sách nguồn IPTV / cào link bóng đá trực tiếp
sources = [
    "https://raw.githubusercontent.com/yem2021/free-iptv/main/sports.m3u",
    "https://iptv-org.github.io/iptv/categories/sports.m3u"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 1. Thử cào link trực tiếp từ trang web nguồn
try:
    res = requests.get("https://phalang.live/", headers=headers, timeout=10)
    matches = re.findall(r'(https?://[^\s\'"]+\.m3u8[^\s\'"]*)', res.text)
    if matches:
        for idx, url in enumerate(set(matches), 1):
            m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp Phalang", Trận đấu {idx}\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n{url}\n\n'
except Exception as e:
    print(f"Lỗi cào phalang: {e}")

# 2. Tổng hợp các kênh thể thao/bóng đá chất lượng cao sẵn có
for src in sources:
    try:
        r = requests.get(src, headers=headers, timeout=10)
        if r.status_code == 200:
            lines = r.text.splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF"):
                    # Gợi ý nhóm kênh vào mục Trực Tiếp Thể Thao
                    line_info = lines[i]
                    if 'group-title="' not in line_info:
                        line_info = line_info.replace('#EXTINF:-1', '#EXTINF:-1 group-title="⚽ Thể Thao Quốc Tế"')
                    
                    if i + 1 < len(lines) and lines[i+1].startswith("http"):
                        m3u_content += f"{line_info}\n{lines[i+1]}\n\n"
    except Exception as e:
        print(f"Lỗi lấy nguồn {src}: {e}")

# Lưu file playlist
with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("Đã cập nhật playlist thành công!")


