import asyncio
from playwright.async_api import async_playwright
import re

async def run():
    m3u8_links = set()

    async with async_playwright() as p:
        # Khởi tạo trình duyệt Chromium giả lập thiết bị thật
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Lắng nghe toàn bộ traffic mạng để nhặt link .m3u8
        def handle_request(request):
            url = request.url
            if ".m3u8" in url and "blob:" not in url:
                m3u8_links.add(url)

        page.on("request", handle_request)

        try:
            print("Đang truy cập Phá Làng TV...")
            await page.goto("https://phalang.live/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)  # Đợi 5s cho JS tải xong luồng video
        except Exception as e:
            print(f"Lỗi tải trang: {e}")
        finally:
            await browser.close()

    # Tạo nội dung M3U
    m3u_content = "#EXTM3U\n\n"
    if m3u8_links:
        for idx, link in enumerate(m3u8_links, 1):
            m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Trận đấu {idx}\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
            m3u_content += f'{link}\n\n'
    else:
        m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Không tìm thấy luồng .m3u8 đang phát\n'
        m3u_content += 'https://phalang.live/\n\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Hoàn tất! Tìm thấy {len(m3u8_links)} link stream.")

asyncio.run(run())

