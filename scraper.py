import json
import re
from bs4 import BeautifulSoup
import requests

TARGET_URL = "https://cakhiazag.tv/"
DEFAULT_LOGO = (
    "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"
)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148"
        " Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://cakhiazag.tv/",
}


def clean_text(text):
  if not text:
    return ""
  return re.sub(r"\s+", " ", text).strip()


def scrape_cakhia():
  matches = []
  print("1. Đang kết nối tới Cà Khịa TV...")

  try:
    session = requests.Session()
    res = session.get(TARGET_URL, headers=headers, timeout=15)

    if res.status_code == 200:
      html = res.text
      soup = BeautifulSoup(html, "html.parser")

      # CÁCH 1: Trích xuất trực tiếp từ dữ liệu JSON __NEXT_DATA__
      next_data = soup.find("script", id="__NEXT_DATA__")
      if next_data and next_data.string:
        try:
          data = json.loads(next_data.string)
          page_props = data.get("props", {}).get("pageProps", {})
          raw_list = (
              page_props.get("matches", [])
              or page_props.get("dataMatches", [])
              or page_props.get("listMatches", [])
          )

          for item in raw_list:
            home = item.get("home_name") or item.get("homeTeam", {}).get("name")
            away = item.get("away_name") or item.get("awayTeam", {}).get("name")
            time_str = item.get("time") or item.get("match_time", "")
            date_str = item.get("date") or item.get("match_date", "")
            blv = item.get("commentator") or item.get("blv", "")
            logo = (
                item.get("home_flag")
                or item.get("thumbnail")
                or item.get("homeTeam", {}).get("logo")
                or DEFAULT_LOGO
            )
            slug = item.get("slug") or item.get("id")

            # Đường dẫn luồng stream m3u8 nếu có trong JSON
            stream_url = item.get("stream_url") or item.get("hls")
            if not stream_url and slug:
              stream_url = f"https://cakhiazag.tv/truc-tiep/{slug}"

            if home and away:
              time_part = f"{time_str} {date_str}".strip()
              blv_part = f" ({blv.upper()})" if blv else ""
              title = f"{time_part} ⚽ {home} vs {away}{blv_part}".strip()
              matches.append(
                  {"title": title, "logo": logo, "url": stream_url}
              )
        except Exception as e:
          print(f"Lỗi đọc JSON Next.js: {e}")

      # CÁCH 2: Quét thẻ HTML trận đấu nếu JSON rỗng
      if not matches:
        cards = soup.find_all("a", href=re.compile(r"/truc-tiep/"))
        seen_urls = set()

        for card in cards:
          href = card.get("href", "")
          if href in seen_urls:
            continue
          seen_urls.add(href)

          full_url = (
              f"https://cakhiazag.tv{href}" if href.startswith("/") else href
          )
          raw_text = card.get_text(separator=" ")
          clean_name = clean_text(raw_text)

          img = card.find("img")
          logo_url = (
              img.get("src") if img and img.get("src") else DEFAULT_LOGO
          )

          if clean_name and len(clean_name) > 3:
            matches.append(
                {"title": clean_name, "logo": logo_url, "url": full_url}
            )

  except Exception as e:
    print(f"Lỗi truy cập mạng: {e}")

  return matches


def build_m3u(matches):
  m3u = "#EXTM3U\n\n"
  if matches:
    for item in matches:
      m3u += f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="Cà Khịa TV" , 🟢 {item["title"]} [FHD]\n'
      m3u += f"#EXTVLCOPT:http-referrer=https://cakhiazag.tv/\n"
      m3u += f'{item["url"]}\n\n'
  else:
    m3u += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Cà Khịa TV" , 🟢 Cà Khịa TV Trang Chính [FHD]\n'
    m3u += f"#EXTVLCOPT:http-referrer=https://cakhiazag.tv/\n"
    m3u += f"{TARGET_URL}\n\n"
  return m3u


if __name__ == "__main__":
  match_list = scrape_cakhia()
  print(f"2. Bóc tách thành công {len(match_list)} trận đấu!")
  m3u_text = build_m3u(match_list)

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_text)

  print("✅ Đã tạo file 'playlist.m3u' thành công!")
    
