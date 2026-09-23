import time
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

def run_scraper():
    final_playlist = []

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

            # Lấy thông tin trận đấu bằng JS
            raw_matches = page.evaluate('''() => {
                const matches = [];
                const links = Array.from(document.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"]'));
                
                links.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href) return;
                    
                    let container = link.closest('.match-item, .item-match, .card-match, .match-card, .item, .card');
                    if (!container) {
                        container = link.parentElement ? (link.parentElement.parentElement ? link.parentElement.parentElement.parentElement : link.parentElement) : link;
                    }
                    if (!container) return;
                    
                    const fullText = container.innerText || '';
                    let logo = '';
                    const img = container.querySelector('img');
                    if (img) {
                        logo = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    }
                    
                    matches.push({
                        url: href.startsWith('http') ? href : window.location.origin + href,
                        fullText: fullText,
                        logo: logo.startsWith('http') ? logo : (logo ? window.location.origin + logo : '')
                    });
                });
                
                return matches;
            }''')

            parsed_items = []
            for item in raw_matches:
                text = item['fullText']
                if not text:
                    continue

                # 1. Trích xuất Thời gian (Giờ & Ngày)
                time_match = re.search(r'(\d{1,2}:\d{2})', text)
                date_match = re.search(r'(\d{1,2}/\d{1,2})', text)
                m_time = time_match.group(1) if time_match else "LIVE"
                m_date = date_match.group(1) if date_match else ""
                time_str = f"{m_time} {m_date}".strip()

                # 2. Trích xuất ĐẦY ĐỦ tên BLV (không bị cắt chữ)
                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    # Cắt bỏ phần dư thừa phía sau tên BLV
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2})', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                # 3. Lọc bỏ toàn bộ các dòng chứa Thời gian, Ngày tháng, BLV để lấy Tên 2 Đội
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                clean_lines = []
                for l in lines:
                    l_lower = l.lower()
                    # Loại bỏ các dòng chứa số giờ/ngày
                    if re.search(r'\d{1,2}:\d{2}', l) or re.search(r'\d{1,2}/\d{1,2}', l):
                        continue
                    # Loại bỏ từ khóa trạng thái
                    if any(k in l_lower for k in ["live", "trực tiếp", "hls", "flv", "xem ngay", "sắp diễn ra"]):
                        continue
                    # Loại bỏ dòng tên BLV
                    if blv_name and l_lower in blv_name.lower():
                        continue
                    if re.search(r'^(gà|blv)\s+', l_lower):
                        continue
                    
                    clean_lines.append(l)

                teams_str = ""
                if len(clean_lines) >= 2:
                    if clean_lines[0].lower() != clean_lines[1].lower():
                        teams_str = f"{clean_lines[0]} vs {clean_lines[1]}"
                    else:
                        teams_str = clean_lines[0]
                elif len(clean_lines) == 1:
                    teams_str = clean_lines[0]

                if not teams_str:
                    continue

                blv_suffix = f" ({blv_name})" if blv_name else ""

                # Tiêu đề hoàn chỉnh đầy đủ thông tin
                full_title = f"{time_str} ⚽ {teams_str}{blv_suffix} [hls]"

                parsed_items.append({
                    "title": full_title,
                    "logo": item['logo'],
                    "url": item['url']
                })

            # Lọc trùng lặp
            unique_dict = {}
            for p_item in parsed_items:
                key = f"{p_item['url']}_{p_item['title']}"
                if key not in unique_dict:
                    unique_dict[key] = p_item

            final_matches = list(unique_dict.values())
            print(f"[*] Bóc tách thành công {len(final_matches)} luồng trận đấu chuẩn.")

            # Trích xuất link m3u8
            captured_m3u8 = []
            def handle_request(request):
                if ".m3u8" in request.url and "blob:" not in request.url:
                    captured_m3u8.append(request.url)

            page.on("request", handle_request)

            for item in final_matches:
                captured_m3u8.clear()
                try:
                    page.goto(item['url'], timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    item['stream'] = captured_m3u8[0] if captured_m3u8 else item['url']
                except:
                    item['stream'] = item['url']

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        finally:
            browser.close()

    # Ghi file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        if not final_matches:
            f.write(f'#EXTINF:-1 tvg-logo="{BASE_URL}/favicon.ico" group-title="{GROUP_NAME}",Chưa có trận đấu nào\n')
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
    
