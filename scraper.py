import time
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"

# Danh sách từ khóa nhận diện LINK QUẢNG CÁO cần BỎ QUA
AD_KEYWORDS = ["ad", "ads", "promo", "intro", "banner", "teaser", "trailer", "default", "logo"]

def is_ad_link(url):
    url_lower = url.lower()
    return any(kw in url_lower for kw in AD_KEYWORDS)

def run_scraper():
    match_streams = [] # Lưu danh sách dict: {"title": ..., "url": ...}

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

        # Biến tạm lưu link m3u8 bắt được trong mỗi trang trận đấu
        current_captured_urls = []

        def handle_request(request):
            url = request.url
            if ".m3u8" in url and "blob:" not in url:
                if not is_ad_link(url):
                    print(f"[+] Bắt được luồng chuẩn: {url}")
                    current_captured_urls.append(url)
                else:
                    print(f"[-] Đã bỏ qua link quảng cáo: {url}")

        page.on("request", handle_request)

        try:
            print(f"[*] Đang quét trang chủ: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Lấy danh sách các trận đấu đang diễn ra trên trang chủ
            matches = []
            links = page.query_selector_all("a")
            
            for link in links:
                try:
                    href = link.get_attribute("href")
                    title = link.inner_text().strip()
                    
                    if href and any(k in href for k in ["/truc-tiep/", "/match/", "/xem-bong-da/", "/live/"]):
                        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                        clean_title = re.sub(r'\s+', ' ', title).replace("\n", " - ")
                        if len(clean_title) < 3:
                            clean_title = "Trận đấu Trực Tiếp"
                        
                        matches.append({"title": clean_title, "url": full_url})
                except:
                    pass

            # Lọc các trận đấu trùng lặp URL
            unique_matches = {m['url']: m for m in matches}.values()
            print(f"[*] Tìm thấy {len(unique_matches)} trận đấu trong danh sách.")

            # Duyệt qua từng trận đấu để trích xuất link m3u8 chuẩn
            for idx, match in enumerate(unique_matches, start=1):
                current_captured_urls.clear()
                print(f"[*] [{idx}/{len(unique_matches)}] Đang lấy luồng trận: {match['title']}")
                
                try:
                    page.goto(match['url'], timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)

                    # Tự động click vào trình phát video
                    players = page.query_selector_all("iframe, .player, button")
                    for p_elem in players[:2]:
                        try:
                            p_elem.click(timeout=1500)
                        except:
                            pass
                    
                    page.wait_for_timeout(3000)

                    # Lưu lại các link thu được cho trận này
                    for stream_url in set(current_captured_urls):
                        match_streams.append({
                            "title": match['title'],
                            "url": stream_url
                        })
                except Exception as e:
                    print(f"Lỗi khi cào trận {match['title']}: {e}")

        except Exception as e:
            print(f"Lỗi truy cập hệ thống: {e}")
        finally:
            browser.close()

    # Ghi danh sách ra file playlist.m3u
    print(f"\n[=>] Tổng cộng thu được {len(match_streams)} luồng trận đấu chất lượng.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-SESSION-DATA:DATA-ID=\"com.xbmc.m3u\"\n\n")

        if not match_streams:
            f.write("#EXTINF:-1 group-title=\"Gà Vàng TV\", Chưa có trận đấu nào đang phát\n")
            f.write("http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4\n")
        else:
            for idx, item in enumerate(match_streams, start=1):
                f.write(f"#EXTINF:-1 group-title=\"Gà Vàng TV\", {item['title']} (Server {idx})\n")
                f.write(f"#EXTVLCOPT:http-referrer={BASE_URL}/\n")
                f.write(f"#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n")
                f.write(f"{item['url']}|Referer={BASE_URL}/&User-Agent=Mozilla/5.0\n\n")

if __name__ == "__main__":
    run_scraper()
    
