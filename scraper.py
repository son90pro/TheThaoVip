import os
import re
import json
import requests

TARGET_URL = "https://gavang33.me/"
DEFAULT_LOGO = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148"
        " Safari/604.1"
    ),
    "Referer": "https://gavang33.me/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

print("1. Đang kết nối tới gavang33.me...")

matches_list = []

try:
  res = requests.get(TARGET_URL, headers=headers, timeout=15)
  if res.status_code == 200:
    html = res.text

    # Tìm các đoạn JSON hoặc link m3u8 trong mã nguồn
    m3u8_links = list(
        set(re.findall(r"https?://[^\s'\"\\]+\.m3u8[^\s'\"\\]*", html))
    )

    # Tìm danh sách trận đấu qua regex pattern
    raw_cards = re.findall(
        r'<div[^>]*class="[^"]*match[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL
    )

    if m3u8_links:
      for idx, link in enumerate(m3u8_links, 1):
        matches_list.append(
            (f"Gà Vàng Live Stream {idx}", link)
        )

    # Nếu không bắt được m3u8 trực tiếp, bóc tách link các trang trận đấu
    if not matches_list:
      match_paths = list(set(re.findall(r'/match/[a-zA-Z0-9-]+', html)))
      for idx, path in enumerate(match_paths, 1):
        full_match_url = f"https://gavang33.me{path}"
        matches_list.append((f"Trận đấu Gà Vàng {idx}", full_match_url))

except Exception as e:
  print(f"Lỗi truy cập: {e}")

# Tạo nội dung M3U đúng định dạng chuẩn như anh yêu cầu
m3u_content = "#EXTM3U\n\n"

if matches_list:
  for title, stream_url in matches_list:
    m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV" , 🟢 {title} [FHD] [hls]\n'
    m3u_content += f"#EXTVLCOPT:http-referrer=https://gavang33.me/\n"
    m3u_content += f"{stream_url}\n\n"
else:
  m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV" , 🟢 Gà Vàng TV Trang Chính [FHD] [hls]\n'
  m3u_content += f"#EXTVLCOPT:http-referrer=https://gavang33.me/\n"
  m3u_content += f"{TARGET_URL}\n\n"

# Ghi ra file playlist.m3u
with open("playlist.m3u", "w", encoding="utf-8") as f:
  f.write(m3u_content)

print(
    f"✅ Đã tạo thành công file playlist.m3u chứa {len(matches_list)} mục!"
)
