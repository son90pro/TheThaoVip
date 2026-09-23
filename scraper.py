import time
import re
import json
from playwright.sync_api import sync_playwright

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

def clean_text(text):
    return re.sub(r'\s+', ' ', text or '').strip()

def run_scraper():
    match_list = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        try:
            print(f"[*] Đang tải trang chủ: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # Quét các khung chứa trận đấu chính (loại bỏ các nút icon BLV lẻ)
            cards = page.query_selector_all(".match-item, .item-match, .card-match, .match-card, div[class*='match']")
            if not cards:
                cards = page.query_selector_all("a[href*='/truc-tiep/'], a[href*='/match/']")

            for card in cards:
                try:
                    href = card.get_attribute("href") or ""
                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}" if href else ""

                    card_text = card.inner_text().strip()
                    if not card_text:
                        continue

                    # 1. Trích xuất thời gian (Giờ & Ngày)
                    time_match = re.search(r'(\d{1,2}:\d{2})', card_text)
                    date_match = re.search(r'(\d{1,2}/\d{1,2})', card_text)
                    m_time = time_match.group(1) if time_match else ""
                    m_date = date_match.group(1) if date_match else ""
                    time_str = f"{m_time} {m_date}".strip() if (m_time or m_date) else "LIVE"

                    # 2. Trích xuất Logo
                    imgs = card.query_selector_all("img")
                    logo_url = ""
                    for img in imgs:
                        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                        if src and "favicon" not in src and "avatar" not in src:
                            logo_url = src if src.startswith("http") else f"{BASE_URL}{src}"
                            break

                    # 3. Trích xuất Tên 2 đội bóng (BẮT BỘC)
                    home_away = ""
                    # Tìm theo cấu trúc chữ 'vs' hoặc dấu '-'
                    vs_match = re.search(r'([A-Za-zÀ-ỹ0-9\s\.\-]+)\s+(?:vs|-)\s+([A-Za-zÀ-ỹ0-9\s\.\-]+)', card_text, re.IGNORECASE)
                    if vs_match:
                        t1 = clean_text(vs_match.group(1)).split('\n')[-1]
                        t2 = clean_text(vs_match.group(2)).split('\n')[0]
                        if len(t1) > 2 and len(t2) > 2:
                            home_away = f"{t1} vs {t2}"

                    # Nếu không tìm thấy chữ 'vs', thử tìm danh sách dòng chữ tên đội
                    if not home_away:
                        team_elems = card.query_selector_all("[class*='team'], [class*='name']")
                        teams = [clean_text(e.inner_text()) for e in team_elems if clean_text(e.inner_text())]
                        teams = [t for t in teams if not re.match(r'^\d{1,2}:\d{2}$', t) and t.lower() not in ["live", "trực tiếp", "hls", "flv"]]
                        if len(teams) >= 2:
                            home_away = f"{teams[0]} vs {teams[1]}"

                    # Bỏ qua nếu không phải thẻ trận đấu thực sự (không có tên 2 đội bóng)
                    if not home_away:
                        continue

                    # 4. Trích xuất tên BLV
                    blv_match = re.search(r'(Gà\s+[A-Za-zÀ-ỹ0-9]+|BLV\s+[A-Za-zÀ-ỹ0-9]+)', card_text, re.IGNORECASE)
                    blv_str = f" ({blv_match.group(1)})" if blv_match else ""

                    full_title = f"{time_str} ⚽ {home_away}{blv_str} [hls]"

                    match_list.append({
                        "title": full_title,
                        "logo": logo_url,
                        "url": full_url
                    })

                except Exception:
                    continue

            # Lọc trùng lặp trận đấu
            unique_matches = {}
            for m in match_list:
                if m['title'] not in unique_matches:
                    unique_matches[m['title']] = m

            final_matches = list(unique_matches.values())
            print(f"[*] Lọc thành công {len(final_matches)} trận đấu chuẩn.")

            # Trích xuất link luồng m3u8
            captured_m3u8 = []
            def handle_request(request):
                if ".m3u8" in request.url and "blob:" not in request.url:
                    captured_m3u8.append(request.url)

            page.on("request", handle_request)

            for item in final_matches:
                captured_m3u8.clear()
                if item['url']:
                    try:
                        page.goto(item['url'], timeout=20000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2500)
                        item['stream'] = captured_m3u8[0] if captured_m3u8 else item['url']
                    except:
                        item['stream'] = item['url']
                else:
                    item['stream'] = BASE_URL

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        finally:
            browser.close()

    # Ghi file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        if not final_matches:
            f.write(f'#EXTINF:-1 tvg-logo="{BASE_URL}/favicon.ico" group-title="{GROUP_NAME}",Chưa có trận đấu nào đang phát\n')
            f.write("http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4\n")
        else:
            for item in final_matches:
                logo_attr = f'tvg-logo="{item["logo"]}"' if item["logo"] else ''
                f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
                f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n')
                f.write(f'{item["stream"]}|Referer={BASE_URL}/&User-Agent=Mozilla/5.0\n\n')

if __name__ == "__main__":
    run_scraper()
