import time
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://gavang33.me"  # Trang nguồn
OUTPUT_FILE = "playlist.m3u"

def run_scraper():
    found_streams = []

    with sync_playwright() as p:
        # Khởi tạo trình duyệt với tham số vượt chặn Bot
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.new_page()

        # Bắt gói tin gửi đi có đuôi .m3u8
        def handle_request(request):
            url = request.url
            if ".m3u8" in url and "blob:" not in url:
                print(f"[+] Tìm thấy m3u8: {url}")
                found_streams.append(url)

        page.on("request", handle_request)

        try:
            print(f"[*] Đang truy cập trang chủ: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Lấy tất cả các đường dẫn trận đấu trực tiếp từ trang chủ
            match_links = []
            hrefs = page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            for href in hrefs:
                # Lọc các liên kết dẫn đến trang trực tiếp trận đấu
                if href and any(k in href for k in ["/truc-tiep/", "/match/", "/xem-bong-da/", "/live/"]):
                    match_links.append(href)

            match_links = list(set(match_links))
            print(f"[*] Tìm thấy {len(match_links)} trận đấu đang/sắp diễn ra.")

            # Nếu không thấy link chi tiết nào, thử cào trực tiếp tại trang chủ
            if not match_links:
                match_links = [BASE_URL]

            # Giới hạn cào tối đa 5-10 trận đang phát để tránh quá tải
            for idx, match_url in enumerate(match_links[:8], start=1):
                print(f"[*] [{idx}/{len(match_links[:8])}] Đang cào: {match_url}")
                try:
                    page.goto(match_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)

                    # Tự động tìm và click vào nút Play/Màn hình video nếu có
                    play_buttons = page.query_selector_all("button, .play-btn, .player, iframe")
                    for btn in play_buttons[:3]:
                        try:
                            btn.click(timeout=2000)
                        except:
                            pass
                    
                    # Chờ luồng video tải
                    page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"Lỗi khi cào trang {match_url}: {e}")

        except Exception as e:
            print(f"Lỗi truy cập tổng: {e}")
        finally:
            browser.close()

    # Lọc trùng lặp danh sách link m3u8
    unique_streams = list(set(found_streams))
    print(f"\n[=>] Tổng cộng tìm thấy {len(unique_streams)} luồng m3u8.")

    # Ghi ra file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-SESSION-DATA:DATA-ID=\"com.xbmc.m3u\"\n\n")

        for idx, link in enumerate(unique_streams, start=1):
            f.write(f"#EXTINF:-1 group-title=\"Gà Vàng TV\", Kenh Truc Tiep {idx}\n")
            f.write(f"#EXTVLCOPT:http-referrer={BASE_URL}/\n")
            f.write(f"#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n")
            f.write(f"{link}|Referer={BASE_URL}/&User-Agent=Mozilla/5.0\n\n")

if __name__ == "__main__":
    run_scraper()
    
