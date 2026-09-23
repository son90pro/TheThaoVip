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

            # Dùng JavaScript tìm chính xác Khung Trận Đấu cha (tránh quét nhầm nút lẻ)
            raw_matches = page.evaluate('''() => {
                const matches = [];
                const links = Array.from(document.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"]'));
                
                links.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href) return;
                    
                    // Truy ngược tìm khung chứa toàn bộ trận đấu
                    let container = link.closest('.match-item, .item-match, .card-match, .match-card, .item, .card');
                    if (!container) {
                        container = link.parentElement ? (link.parentElement.parentElement ? link.parentElement.parentElement.parentElement : link.parentElement) : link;
                    }
                    if (!container) return;
                    
                    const fullText = container.innerText || '';
                    
                    // Lấy logo
                    let logo = '';
                    const img = container.querySelector('img');
                    if (img) {
                        logo = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    }
                    
                    // Lấy tên BLV từ link hoặc thẻ
                    let blv = link.innerText || link.getAttribute('title') || '';
                    
                    matches.push({
                        url: href.startsWith('http') ? href : window.location.origin + href,
                        fullText: fullText,
                        linkText: blv,
                        logo: logo.startsWith('http') ? logo : (logo ? window.location.origin + logo : '')
                    });
                });
                
                return matches;
            }''')

            # Xử lý bóc tách dữ liệu chuẩn
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

                # 2. Trích xuất Tên 2 đội bóng (BẮT BỘC ĐỦ ĐỘI NHÀ VS ĐỘI KHÁCH)
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                clean_lines = []
                for l in lines:
                    l_lower = l.lower()
                    if re.match(r'^\d{1,2}:\d{2}$', l) or re.match(r'^\d{1,2}/\d{1,2}$', l):
                        continue
                    if l_lower in ["live", "trực tiếp", "hls", "flv", "xem ngay", "sắp diễn ra"]:
                        continue
                    if re.search(r'^(gà|blv)\s+', l_lower):
                        continue
                    clean_lines.append(l)

                teams_str = ""
                vs_match = re.search(r'(.+?)\s+(?:vs|-)\s+(.+)', text, re.IGNORECASE)
                if vs_match:
                    t1 = vs_match.group(1).split('\n')[-1].strip()
                    t2 = vs_match.group(2).split('\n')[0].strip()
                    if t1.lower() != t2.lower():
                        teams_str = f"{t1} vs {t2}"
                    else:
                        teams_str = t1
                elif len(clean_lines) >= 2:
                    if clean_lines[0].lower() != clean_lines[1].lower():
                        teams_str = f"{clean_lines[0]} vs {clean_lines[1]}"
                    else:
                        teams_str = clean_lines[0]

                # Nếu vẫn không lấy đủ tên trận bóng thì bỏ qua (lọc rác)
                if not teams_str or len(teams_str) < 3:
                    continue

                # 3. Trích xuất tên BLV
                blv_name = ""
                blv_match = re.search(r'(Gà\s+[A-Za-zÀ-ỹ0-9]+|BLV\s+[A-Za-zÀ-ỹ0-9]+)', item['linkText'] + " " + text, re.IGNORECASE)
                if blv_match:
                    blv_name = blv_match.group(1).strip()

                blv_suffix = f" ({blv_name})" if blv_name else ""

                # Tiêu đề ĐẦY ĐỦ THÔNG TIN để ngắt thành 3 dòng đẹp mắt trên IPTV
                full_title = f"{time_str} ⚽ {teams_str}{blv_suffix} [hls]"

                parsed_items.append({
                    "title": full_title,
                    "logo": item['logo'],
                    "url": item['url']
                })

            # Lọc trùng lặp kênh
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
    
