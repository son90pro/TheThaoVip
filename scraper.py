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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://cakhiazag.tv/",
}


def clean_slug_to_title(slug):
  """Chuyển đổi đường dẫn slug (vd: man-utd-vs-arsenal-123) thành tên trận đấu sạch."""
  # Bỏ chuỗi id số ở cuối slug
  slug_clean = re.sub(r"-\d+$", "", slug)
  parts = slug_clean.split("-")
  words = [p.capitalize() for p in parts if p]
  title = " ".join(words)
  # Chuẩn hóa chữ 'Vs' thành 'vs'
  return re.sub(r"\bVs\b", "vs", title)


def scrape_cakhia():
  matches = []
  print("1. Đang tải trang Cà Khịa TV...")

  try:
    res = requests.get(TARGET_URL, headers=headers, timeout=15)
    if res.status_code == 200:
      html = res.text
      soup = BeautifulSoup(html, "html.parser")

      # 1. Thử trích xuất dữ liệu JSON chuẩn từ __NEXT_DATA__
      next_data = soup.find("script", id="__NEXT_DATA__")
      if next_data and next_data.string:
        try:
          data = json.loads(next_data.string)
          page_props = data.get("props", {}).get("pageProps", {})
          raw_list = (
              page_props.get("matches", [])
              or page_props.get("dataMatches", [])
              or []
          )

          for item in raw_list:
            if not isinstance(item, dict):
              continue
            home = item.get("home_name") or item.get("homeTeam", {}).get("name")
            away = item.get("away_name") or item.get("awayTeam", {}).get("name")
            if home and away:
              time_str = item.get("time") or item.get("match_time") or ""
              blv = item.get("commentator") or item.get("blv") or ""
              slug = item.get("slug") or item.get("id") or ""

              blv_part = f" ({blv.upper()})" if blv else ""
              time_part = f"{time_str} " if time_str else ""
              title = f"{time_part}⚽ {home} vs {away}{blv_part}".strip()
              url = (
                  f"https://cakhiazag.tv/truc-tiep/{slug}"
                  if slug
                  else TARGET_URL
              )
              matches.append(
                  {"title": title, "logo": DEFAULT_LOGO, "url": url}
              )
        except Exception as e:
          print(f"Lỗi JSON: {e}")

      # 2. Bóc tách từ HTML với bộ lọc chống nhiễu BLV
      if not matches:
        seen_slugs = set()
        for a_tag in soup.find_all("a", href=re.compile(r"/truc-tiep/")):
          href = a_tag.get("href", "")
          slug = href.split("/")[-1].strip()

          # LỌC NGHIÊM NGẶT: Bắt buộc phải chứa "-vs-" trong link mới là TRẬN ĐẤU.
          # Loại bỏ tất cả link BLV lẻ như /truc-tiep/fabio
          if not slug or "-vs-" not in slug.lower() or slug in seen_slugs:
            continue

          seen_slugs.add(slug)
          clean_title = clean_slug_to_title(slug)
          full_url = (
              f"https://cakhiazag.tv{href}" if href.startswith("/") else href
          )

          img = a_tag.find("img")
          logo_url = (
              img.get("src")
              if (img and img.get("src") and img.get("src").startswith("http"))
              else DEFAULT_LOGO
          )

          matches.append({
              "title": f"⚽ {clean_title}",
              "logo": logo_url,
              "url": full_url,
          })

  except Exception as e:
    print(f"Lỗi kết nối: {e}")

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
  matches = scrape_cakhia()
  print(f"2. Bóc tách thành công {len(matches)} trận đấu!")
  m3u_text = build_m3u(matches)

  with open("playlist.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_text)

  print("✅ Đã tạo file playlist.m3u thành công!")
    
