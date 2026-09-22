import json
import re
import requests

FLARESOLVERR_URL = "http://localhost:8191/v1"
TARGET_URL = "https://phalang.live/"
DEFAULT_LOGO = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"


def fetch_via_flaresolverr(url):
  payload = {
      "cmd": "request.get",
      "url": url,
      "maxTimeout": 60000,
  }
  headers = {"Content-Type": "application/json"}
  try:
    response = requests.post(
        FLARESOLVERR_URL, json=payload, headers=headers, timeout=70
    )
    if response.status_code == 200:
      res_json = response.json()
      if res_json.get("status") == "ok":
        return res_json.get("solution", {})
  except Exception as e:
    print(f"Lỗi FlareSolverr: {e}")
  return None


print("Đang gửi yêu cầu giải mã Cloudflare qua FlareSolverr...")
solution = fetch_via_flaresolverr(TARGET_URL)

m3u_content = "#EXTM3U\n\n"
matches_found = []

if solution:
  html_content = solution.get("response", "")
  cookies = solution.get("cookies", [])
  user_agent = solution.get("userAgent", "")

  # Lấy danh sách link m3u8 hoặc luồng phát trực tiếp
  hls_links = list(
      set(re.findall(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', html_content))
  )

  # Nếu không thấy m3u8 trực tiếp, tìm các iframe/embed
  embed_links = list(
      set(re.findall(r'https?://[^\s\'"]+/embed/[^\s\'"]*', html_content))
  )

  if hls_links:
    for idx, link in enumerate(hls_links, 1):
      matches_found.append((f"Trận Phá Làng Live {idx}", link))
  elif embed_links:
    for idx, link in enumerate(embed_links, 1):
      matches_found.append((f"Luồng Phá Làng {idx}", link))

if matches_found:
  for title, stream in matches_found:
    m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Phá Làng TV", ⚽ {title}\n'
    m3u_content += f"#EXTVLCOPT:http-referrer=https://phalang.live/\n"
    m3u_content += f"{stream}\n\n"
else:
  # Dự phòng nếu Cloudflare thắt chặt thêm lớp captcha cứng
  m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Phá Làng TV", ⚽ Phá Làng TV Live (Kênh Chính)\n'
  m3u_content += f"#EXTVLCOPT:http-referrer=https://phalang.live/\n"
  m3u_content += "https://phalang.live/\n\n"

with open("playlist.m3u", "w", encoding="utf-8") as f:
  f.write(m3u_content)

print("Đã hoàn tất cập nhật file playlist.m3u")
