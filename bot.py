import asyncio
from playwright.async_api import async_playwright
import re

async def run():
    matches_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print("1. Mở trang Phá Làng TV...")
            await page.goto("https://phalang.live/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            # Lấy danh sách tất cả các thẻ trận đấu trên giao diện
            cards = await page.query_selector_all("a")
            match_urls = []
            
            for card in cards:
                href = await card.get_attribute("href")
                if href and ("phalang.live" in href or href.startswith("/")) and href != "/" and "phalang.live/" not in href:
                    full_url = href if href.startswith("http") else f"https://phalang.live{href}"
                    # Lấy text thông tin trận đấu (giờ, tên đội, BLV)
                    text_content = await card.inner_text()
                    text_content = " ".join(text_content.split())
                    if text_content and len(text_content) > 5:
                        match_urls.append((full_url, text_content))

            print(f"2. Tìm thấy {len(match_urls)} trận đấu. Bắt đầu trích xuất luồng stream...")

            # Truy cập từng trang trận đấu để lấy link stream .m3u8
            for url, title in match_urls[:8]:
                captured_stream = None

                def handle_request(request):
                    nonlocal captured_stream
                    req_url = request.url
                    if ".m3u8" in req_url and "blob:" not in req_url:
                        captured_stream = req_url

                page.on("request", handle_request)

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                    await page.wait_for_timeout(3500)
                except Exception:
                    pass

                if captured_stream:
                    matches_data.append({
                        "title": title,
                        "stream": captured_stream
                    })

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            await browser.close()

    # Tạo định dạng M3U chuẩn hiển thị đầy đủ tên trận đấu
    m3u_content = "#EXTM3U\n\n"
    if matches_data:
        for item in matches_data:
            clean_title = item['title'].replace("\n", " - ")
            m3u_content += f'#EXTINF:-1 group-title="Phá Làng TV", ⚽ {clean_title}\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
            m3u_content += f'{item["stream"]}\n\n'
    else:
        m3u_content += '#EXTINF:-1 group-title="Phá Làng TV", 🟢 Dang cap nhat danh sach tran dau...\n'
        m3u_content += '#EXTVLCOPT:http-referrer=https://phalang.live/\n'
        m3u_content += 'https://phalang.live/\n\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Hoàn tất! Đã bóc tách thành công {len(matches_data)} trận đấu đầy đủ tên.")

asyncio.run(run())
