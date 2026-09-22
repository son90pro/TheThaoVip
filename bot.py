import json
import re
import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://gavang33.live/"
DEFAULT_LOGO = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://gavang33.live/",
    "Origin": "https://gavang33.live",
}

print(f"Đang kết nối tới {TARGET_URL}...")

matches = []

try:
  response = requests.get(TARGET_URL, headers=headers, timeout=15)
  if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")

    # 1. Tìm các thẻ trận đấu trên giao diện Web (WordPress)
    match_items = soup.find_all(
        ["div", "li", "a"],
        class_=re.compile(r"match|item|event|live", re.IGNORECASE),
    )

    for item in match_items:
      text = item.get_text(separator=" ", strip=True)
      # Lọc các khối chứa từ khóa "VS" hoặc thời gian
      if " vs " in text.lower() or " - " in text:
        href = item.get("href") or ""
        if href and not href.startswith("http"):
          href = f"https://gavang33.live{href}"

        matches.append({"title": text[:80], "url": href})

    # 2. Tìm trực tiếp các luồng stream .m3u8 hoặc embed API xuất hiện trong HTML
    m3u8_links = list(
        set(re.findall(r"https?://[^\s'\"\\]+\.m3u8[^\s'\"\\]*", response.text))
    )
    embed_links = list(
        set(
            re.findall(
                r"https?://[^\s'\"\\]*(?:gvapi|gavang|embed)[^\s'\"\\]*",
                response.text,
            )
        )
    )

    print(f"-> Tìm thấy {len(matches)} khung trận đấu trên trang chủ.")
    print(f"-> Phân tích thấy {len(m3u8_links)} link .m3u8 trực tiếp.")
    print(f"-> Tìm thấy {len(embed_links)} link embed API phát sóng.")

    # Xuất dữ liệu ra file M3U thử nghiệm
    m3u_content = "#EXTM3U\n\n"

    if m3u8_links:
      for idx, link in enumerate(m3u8_links, 1):
        m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV", ⚽ Gà Vàng Live Stream {idx}\n'
        m3u_content += f"#EXTVLCOPT:http-referrer=https://gavang33.live/\n"
        m3u_content += f"{link}\n\n"
    elif matches:
      for idx, match in enumerate(matches, 1):
        m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV", ⚽ {match["title"]}\n'
        m3u_content += f"#EXTVLCOPT:http-referrer=https://gavang33.live/\n"
        m3u_content += f'{match["url"] or TARGET_URL}\n\n'
    else:
      m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV", ⚽ Gà Vàng TV Trang Chính\n'
      m3u_content += f"#EXTVLCOPT:http-referrer=https://gavang33.live/\n"
      m3u_content += f"{TARGET_URL}\n\n"

    with open("gavang_playlist.m3u", "w", encoding="utf-8") as f:
      f.write(m3u_content)

    print("✅ Đã xuất kết quả ra file 'gavang_playlist.m3u'!")

  else:
    print(
        f"Lỗi truy cập {TARGET_URL} - Mã phản hồi (Status Code):"
        f" {response.status_code}"
    )

except Exception as e:
  print(f"Lỗi khi cào dữ liệu: {e}")
  
