import json
import re
import requests

TARGET_URL = "https://cakhiazag.tv/"
DEFAULT_LOGO = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148"
        " Safari/604.1"
    ),
    "Referer": "https://cakhiazag.tv/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

print("1. Đang kết nối tới Cà Khịa TV (cakhiazag.tv)...")
matches_list = []

try:
  res = requests.get(TARGET_URL, headers=headers, timeout=15)
  if res.status_code == 200:
    html = res.text

    # 1. Tìm dữ liệu trận đấu nhúng trong thẻ script __NEXT_DATA__ của Cà Khịa
    next_data = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html
    )
    if next_data:
      try:
        json_data = json.loads(next_data.group(1))
        # Bóc tách danh sách trận đấu từ state của Next.js
        page_props = json_data.get("props", {}).get("pageProps", {})
        matches = page_props.get("matches", []) or page_props.get(
            "dataMatches", []
        )

        for match in matches:
          home = match.get("home_name") or match.get("homeTeam", {}).get("name")
          away = match.get("away_name") or match.get("awayTeam", {}).get("name")
          time_str = match.get("time") or match.get("match_time", "")
          slug = match.get("slug") or match.get("id")

          if home and away:
            title = f"{time_str} ⚽ {home} vs {away}"
            # Lấy link hls/m3u8 nếu có hoặc tạo link chi tiết trận
            stream_url = match.get("stream_url") or match.get("hls")
            if not stream_url and slug:
              stream_url = f"https://cakhiazag.tv/truc-tiep/{slug}"

            if stream_url:
              matches_list.append((title, stream_url))
      except Exception as err:
        print(f"Lỗi đọc JSON Next.js: {err}")

    # 2. Nếu không bóc tách được từ __NEXT_DATA__, dùng Regex quét đường dẫn trận đấu
    if not matches_list:
      raw_matches = list(
          set(re.findall(r'href=["\'](/truc-tiep/[^"\']+)["\']', html))
      )
      for idx, path in enumerate(raw_matches, 1):
        clean_slug = path.split("/")[-1].replace("-", " ").title()
        matches_list.append(
            (f"Cà Khịa Live: {clean_slug}", f"https://cakhiazag.tv{path}")
        )

    # 3. Trường hợp trực tiếp tìm thấy luồng .m3u8
    m3u8_links = list(
        set(re.findall(r"https?://[^\s'\"\\]+\.m3u8[^\s'\"\\]*", html))
    )
    if m3u8_links and not matches_list:
      for idx, link in enumerate(m3u8_links, 1):
        matches_list.append((f"Cà Khịa Stream {idx}", link))

except Exception as e:
  print(f"Lỗi kết nối: {e}")

# Tạo nội dung Playlist M3U chuẩn format Chuối Chiên TV
m3u_content = "#EXTM3U\n\n"

if matches_list:
  for title, stream_url in matches_list:
    m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Cà Khịa TV" , 🟢 {title} [FHD] [hls]\n'
    m3u_content += f"#EXTVLCOPT:http-referrer=https://cakhiazag.tv/\n"
    m3u_content += f"{stream_url}\n\n"
  print(f"2. Tìm thấy {len(matches_list)} trận đấu từ Cà Khịa TV!")
else:
  m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Cà Khịa TV" , 🟢 Cà Khịa TV Trang Chính [FHD] [hls]\n'
  m3u_content += f"#EXTVLCOPT:http-referrer=https://cakhiazag.tv/\n"
  m3u_content += f"{TARGET_URL}\n\n"
  print("2. Xuất link trang chính dự phòng.")

with open("playlist.m3u", "w", encoding="utf-8") as f:
  f.write(m3u_content)

print("✅ Đã tạo xong file 'playlist.m3u' cho Cà Khịa TV!")

