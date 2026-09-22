import asyncio
from playwright.async_api import async_playwright
import re

async def run():
    m3u8_links = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Hàm bắt link stream .m3u8 từ luồng mạng
        def handle_request(request):
            url = request.url
            if ".m3u8" in url and "blob:" not in url:
                m3u8_links.add(url)

        page.on("request", handle_request)

        try:
            print("1. Đang truy cập Trang chủ Phá Làng...")
            await page.goto("https://phalang.live/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Lấy tất cả các đường link trận đấu đang diễn ra trên trang chủ
            anchors = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            match_links = [link for link in set(anchors) if "phalang.live" in link and link != "https://phalang.live/"]

            print(f"2. Tìm thấy {len(match_links)} trang trận đấu. Đang tiến hành soi link stream...")

            # Mở tối đa 5 trận đầu tiên để bắt link
            for match_url in match_links[:5]:
                try:
                    print(f"-> Mở trang: {match_url}")
                    await page.goto(match_url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(4000) # Đợi player load luồng
                except Exception as err:
                    print(f"Bỏ qua trang {match_url}: {err}")

        except Exception as e:
            print(f"Lỗi tổng quan: {e}")
        finally:
            await browser.close()

    # Xuất dữ liệu ra M3U
    m3u_content = "#EXTM3U\n\n"
    if m3u8_links:
        for idx, link in enumerate(m3u8_links, 1):
            m3u_content += f'#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Trận đấu {idx}\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
            m3u_content += f'{link}\n\n'
    else:
        m3u_content += '#EXTINF:-1 group-title="⚽ Trực Tiếp Phá Làng", Server Dự Phòng (Đang nạp luồng)\n'
        m3u_content += '#EXTVLCOPT:http-referrer=https://phalang.live/\n'
        m3u_content += 'https://phalang.live/\n\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Xong! Đã trích xuất được {len(m3u8_links)} link stream.")

asyncio.run(run())
