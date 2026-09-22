import re
from playwright.sync_api import sync_playwright

TARGET_URL = "https://gavang33.me/"  # Thay URL nguồn anh muốn cào
OUTPUT_FILE = "playlist.m3u"

def run_scraper():
    found_links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Giả lập User-Agent của máy tính
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Bắt các gói tin gửi đi chứa đuôi .m3u8
        def handle_request(request):
            if ".m3u8" in request.url:
                print(f"[+] Tìm thấy m3u8: {request.url}")
                found_links.append(request.url)

        page.on("request", handle_request)

        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(5000) # Chờ 5s cho trang load xong
        except Exception as e:
            print(f"Lỗi truy cập trang: {e}")
        finally:
            browser.close()

    # Lọc các link trùng lặp
    unique_links = list(set(found_links))

    # Ghi file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#EXT-X-SESSION-DATA:DATA-ID=\"com.xbmc.m3u\"\n\n")

        if not unique_links:
            print("Không tìm thấy luồng m3u8 nào.")
            return

        for idx, link in enumerate(unique_links, start=1):
            f.write(f"#EXTINF:-1 group-title=\"Gà Vàng TV\", Kenh Trực Tiếp {idx}\n")
            # Kèm Header Referer & User-Agent để IPTV Player không bị chặn
            f.write(f"#EXTVLCOPT:http-referrer={TARGET_URL}\n")
            f.write(f"#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n")
            f.write(f"{link}|Referer={TARGET_URL}&User-Agent=Mozilla/5.0\n\n")

    print(f"Đã cập nhật thành công {len(unique_links)} link vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
