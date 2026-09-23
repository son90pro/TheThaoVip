import time
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

def parse_match_info(card_elem):
    """Hàm bóc tách chi tiết: Thời gian, Đội bóng, BLV và Logo từ thẻ trận đấu"""
    try:
        # 1. Lấy Logo
        img_elem = card_elem.query_selector("img")
        logo_url = ""
        blv_from_img = ""
        if img_elem:
            src = img_elem.get_attribute("src") or img_elem.get_attribute("data-src") or ""
            if src:
                logo_url = src if src.startswith("http") else f"{BASE_URL}{src}"
            
            # Lấy tên BLV từ alt/title của ảnh logo (nếu có)
            alt = img_elem.get_attribute("alt") or img_elem.get_attribute("title") or ""
            if any(k in alt.lower() for k in ["gà", "blv"]):
                blv_from_img = alt.strip()

        # 2. Lấy toàn bộ văn bản trong thẻ
        text = card_elem.inner_text().strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 3. Trích xuất Giờ & Ngày
        time_match = re.search(r'(\d{1,2}:\d{2})', text)
        date_match = re.search(r'(\d{1,2}/\d{1,2})', text)
        
        m_time = time_match.group(1) if time_match else ""
        m_date = date_match.group(1) if date_match else ""
        time_str = f"{m_time} {m_date}".strip() if (m_time or m_date) else "LIVE"

        # 4. Trích xuất tên BLV
        blv_name = blv_from_img
        if not blv_name:
            blv_match = re.search(r'(Gà\s+[A-Za-zÀ-ỹ0-9\s]+|BLV\s+[A-Za-zÀ-ỹ0-9\s]+)', text, re.IGNORECASE)
            if blv_match:
                blv_name = blv_match.group(1).strip()

        # 5. Trích xuất tên 2 Đội bóng
        teams_str = ""
        
        # Trường hợp 1: Có chứa từ "vs" hoặc "-"
        vs_match = re.search(r'(.+?)\s+(?:vs|-)\s+(.+)', text, re.IGNORECASE)
        if vs_match:
            t1 = vs_match.group(1).split('\n')[-1].strip()
            t2 = vs_match.group(2).split('\n')[0].strip()
            teams_str = f"{t1} vs {t2}"
        else:
            # Trường hợp 2: Lọc bỏ các dòng chứa thời gian, trạng thái, tên BLV để tìm 2 đội
            clean_lines = []
            for l in lines:
                l_lower = l.lower()
                if re.match(r'^\d{1,2}:\d{2}$', l) or re.match(r'^\d{1,2}/\d{1,2}$', l):
                    continue
                if l_lower in ["trực tiếp", "live", "hls", "flv", "sắp diễn ra"]:
                    continue
                if blv_name and l_lower in blv_name.lower():
                    continue
                clean_lines.append(l)

            if len(clean_lines) >= 2:
                teams_str = f"{clean_lines[0]} vs {clean_lines[1]}"
            elif len(clean_lines) == 1:
                teams_str = clean_lines[0]

        if not teams_str:
            teams_str = "Trận đấu Trực Tiếp"

        # Ghép thành tên hiển thị chuẩn
        blv_suffix = f" ({blv_name})" if blv_name else ""
        full_title = f"{time_str} ⚽ {teams_str}{blv_suffix} [hls]"

        return {
            "title": full_title,
            "logo": logo_url
        }
    except Exception:
        return None

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
            print(f"[*] Đang cào dữ liệu từ: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # Quét tất cả khung chứa thông tin trận đấu
            cards = page.query_selector_all("a[href*='/truc-tiep/'], a[href*='/match/'], a[href*='/live/'], .match-item, .card")
            
            for card in cards:
                href = card.get_attribute("href")
                if not href:
                    continue
                
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                info = parse_match_info(card)
                
                if info:
                    info["url"] = full_url
                    match_items.append(info)

            # Lọc trùng lặp URL
            unique_matches = {m['url']: m for m in match_items}.values()
            print(f"[*] Đã bóc tách thành công {len(unique_matches)} trận đấu có đầy đủ thông tin.")

            # Bắt link stream m3u8 thực tế
            final_playlist = []
            captured_m3u8 = []

            def handle_request(request):
                if ".m3u8" in request.url and "blob:" not in request.url:
                    captured_m3u8.append(request.url)

            page.on("request", handle_request)

            for idx, match in enumerate(unique_matches, start=1):
                captured_m3u8.clear()
                try:
                    page.goto(match['url'], timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    
                    stream_link = captured_m3u8[0] if captured_m3u8 else match['url']
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
            print(f"Lỗi hệ thống: {e}")
        finally:
            browser.close()

    # Ghi ra file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        if not final_playlist:
            f.write(f'#EXTINF:-1 tvg-logo="{BASE_URL}/favicon.ico" group-title="{GROUP_NAME}",Chưa có trận đấu nào đang phát\n')
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
    
