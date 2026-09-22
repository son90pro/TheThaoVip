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
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://cakhiazag.tv/",
}


def find_matches_in_json(data):
  """Tự động truy vết mảng danh sách trận đấu ở bất kỳ cấp độ nào trong JSON."""
  if isinstance(data, dict):
    for key in ["matches", "dataMatches", "listMatches", "data", "list"]:
      if key in data and isinstance(data[key], list) and len(data[key]) > 0:
        first = data[key][0]
        if isinstance(first, dict) and any(
            k in first
            for k in [
                "home_name",
                "homeTeam",
                "home",
                "slug",
                "match_time",
                "title",
            ]
        ):
          return data[key]
    for v in data.values():
      res = find_matches_in_json(v)
      if res:
        return res
  elif isinstance(data, list):
    for item in data:
      res = find_matches_in_json(item)
      if res:
        return res
  return []


def scrape_cakhia():
  matches_list = []
  print("1. Đang tải trang Cà Khịa TV...")

  try:
    res = requests.get(TARGET_URL, headers=headers, timeout=15)
    if res.status_code == 200:
      html = res.text

      # 1. Bóc tách dữ liệu chuẩn từ Next.js JSON state
      next_data_match = re.search(
          r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
      )
      if next_data_match:
        try:
          json_data = json.loads(next_data_match.group(1))
          raw_matches = find_matches_in_json(json_data)

          for item in raw_matches:
            if not isinstance(item, dict):
              continue

            home = (
                item.get("home_name")
                or item.get("home_team_name")
                or (
                    item.get("homeTeam", {}).get("name")
                    if isinstance(item.get("homeTeam"), dict)
                    else ""
                )
                or item.get("home")
            )
            away = (
                item.get("away_name")
                or item.get("away_team_name")
                or (
                    item.get("awayTeam", {}).get("name")
                    if isinstance(item.get("awayTeam"), dict)
                    else ""
                )
                or item.get("away")
            )

            time_str = item.get("time") or item.get("match_time") or ""
            date_str = item.get("date") or item.get("match_date") or ""
            blv = (
                item.get("commentator")
                or item.get("blv")
                or item.get("commentator_name")
                or ""
            )

            logo = (
                item.get("home_flag")
                or item.get("home_logo")
                or item.get("thumbnail")
                or (
                    item.get("homeTeam", {}).get("logo")
                    if isinstance(item.get("homeTeam"), dict)
                    else ""
                )
                or DEFAULT_LOGO
            )

            slug = item.get("slug") or item.get("id") or item.get("match_id")
            stream_url = (
                item.get("stream_url") or item.get("hls") or item.get("link")
            )

            if not stream_url and slug:
              stream_url = f"https://cakhiazag.tv/truc-tiep/{slug}"

            if home and away:
              time_part = f"{time_str} {date_str}".strip()
              if not time_part:
                time_part = "LIVE"
              blv_part = f" ({blv.upper()})" if blv else ""
              title = f"{time_part} ⚽ {home} vs {away}{blv_part}".strip()
              matches_list.append(
                  {"title": title, "logo": logo, "url": stream_url}
              )
        except Exception as e:
          print(f"Lỗi đọc JSON: {e}")

      # 2. Phương án dự phòng phân tích HTML thẻ link
      if not matches_list:
        soup = BeautifulSoup(html, "html.parser")
        seen_urls = set()

        for card in soup.find_all("a", href=re.compile(r"/truc-tiep/")):
          href = card.get("href", "")
          if href in seen_urls:
            continue

          full_url = (
              f"https://cakhiazag.tv{href}" if href.startswith("/") else href
          )
          slug_raw = href.split("/")[-1].replace("-", " ").title()

          # Bỏ qua đường dẫn quá ngắn hoặc không phải trận đấu
          if not slug_raw or len(slug_raw) < 4:
            continue

          img = card.find("img")
          logo_url = (
              img.get("src")
              if (img and img.get("src") and img.get("src").startswith("http"))
              else DEFAULT_LOGO
          )

          title_str = f"⚽ {slug_raw}"
          seen_urls.add(href)
          matches_list.append(
              {"title": title_str, "logo": logo_url, "url": full_url}
          )

  except Exception as e:
    print(f"Lỗi kết nối: {e}")

  return matches_list


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

  print("✅ Đã ghi file playlist.m3u thành công!")
    
