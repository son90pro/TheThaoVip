import time
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

def run_scraper():
    match_items = []

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
            print(f"[*] Đang cào dữ liệu lịch thi đấu từ: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # Quét các thẻ/khung chứa thông tin trận đấu trên trang chủ
            cards = page.query_selector_all("a[href*='/truc-tiep/'], a[href*='/match/'], a[href*='/live/'], .match-item, .card")
            
            for card in cards:
                try:
                    href = card.get_attribute("href")
                    if not href:
                        continue
                    
                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    
                    # 1. Trích xuất Logo (nếu có)
                    img_elem = card.query_selector("img")
                    logo_url = ""
                    if img_elem:
                        src = img_elem.get_attribute("src") or img_elem.get_attribute("data-src")
                        if src:
                            logo_url = src if src.startswith("http") else f"{BASE_URL}{src}"
                    
                    # 2. Lấy toàn bộ văn bản trong khung trận đấu
                    text_content = card.inner_text().strip()
                    lines = [line.strip() for line in text_content.split("\n") if line.strip()]
                    
                    if not lines:
                        continue

                    # Mẫu tên mặc định nếu không phân tích được chi tiết
                    match_time = "LIVE"
                    match_title = " Trận đấu Trực Tiếp"
                    blv_name = ""

                    # Phân tích thời gian (ví dụ: 16:00 22/09 hoặc 16:00)
                    time_match = re.search(r'(\d{1,2}:\d{2}(\s+\d{1,2}/\d{1,2})?)', text_content)
                    if time_match:
                        match_time = time_match.group(1)

                    # Phân tích tên 2 đội (có chữ 'vs' hoặc '-')
                    for line in lines:
                        if " vs " in line.lower() or " - " in line:
                            match_title = line
                            break
                    
                    if match_title == " Trận đấu Trực Tiếp" and len(lines) >= 2:
                        match_title = f"{lines[0]} vs {lines[1]}"

                    # Phân tích tên BLV (thường nằm trong ngoặc hoặc có chữ BLV/Gà...)
                    blv_match = re.search(r'\((Gà\s+[^\)]+)\)|BLV\s+[\w\s]+', text_content, re.IGNORECASE)
                    if blv_match:
                        blv_name = f" ({blv_match.group(0).strip('()')})"

                    # Ghép định dạng hiển thị chuẩn như ảnh
                    full_display_name = f"{match_time} ⚽ {match_title}{blv_name} [hls]"

                    match_items.append({
                        "title": full_display_name,
                        "logo": logo_url,
                        "url": full_url
                    })
                except Exception as e:
                    continue

            # Lọc trùng lặp trận đấu
            unique_matches = {m['url']: m for m in match_items}.values()
            print(f"[*] Đã trích xuất thành công {len(unique_matches)} trận đấu có đầy đủ Logo & Thông tin.")

            # Bắt link m3u8 thực tế cho từng trận
            final_playlist = []
            current_captured_urls = []

            def handle_request(request):
                if ".m3u8" in request.url and "blob:" not in request.url:
                    current_captured_urls.append(request.url)

            page.on("request", handle_request)

            for idx, match in enumerate(unique_matches, start=1):
                current_captured_urls.clear()
                try:
                    page.goto(match['url'], timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    
                    # Tìm link m3u8 phát thực tế
                    stream_link = current_captured_urls[0] if current_captured_urls else match['url']
                    
                    final_playlist.append({
                        "title": match['title'],
                        "logo": match['logo'],
                        "stream": stream_link
                    })
                except:
                    final_playlist.append({
                        "title": match['title'],
                        "logo": match['logo'],
                        "stream": match['url']
                    })

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            browser.close()

    # Ghi file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        if not final_playlist:
            # File mẫu hiển thị khi chưa có danh sách trận
            f.write(f'#EXTINF:-1 tvg-logo="https://gavang33.me/favicon.ico" group-title="{GROUP_NAME}",Chưa có trận đấu nào đang phát\n')
            f.write("http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4\n")
        else:
            for item in final_playlist:
                logo_attr = f'tvg-logo="{item["logo"]}"' if item["logo"] else ''
                f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
                f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n')
                f.write(f'{item["stream"]}|Referer={BASE_URL}/&User-Agent=Mozilla/5.0\n\n')

if __name__ == "__main__":
    run_scraper()
    
