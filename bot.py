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
            await page.wait_for_timeout(3000)

            # Cuộn trang xuống để load toàn bộ danh sách trận đấu
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(1000)

            # Lấy danh sách tất cả các thẻ trận đấu
            cards = await page.query_selector_all("a")
            seen_urls = set()
            match_urls = []
            
            for card in cards:
                href = await card.get_attribute("href")
                if href and ("phalang.live" in href or href.startswith("/")) and href != "/" and "phalang.live/" not in href:
                    full_url = href if href.startswith("http") else f"https://phalang.live{href}"
                    
                    # Lọc trùng URL
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        text_content = await card.inner_text()
                        
                        # Làm sạch chuỗi hiển thị
                        clean_text = " ".join(text_content.split())
                        clean_text = re.sub(r'^[0-9\s]+', '', clean_text)
                        
                        if clean_text and len(clean_text) > 3:
                            match_urls.append((full_url, clean_text))

            print(f"2. Tìm thấy tổng cộng {len(match_urls)} trận đấu riêng biệt. Đang cào link stream...")

            # Truy cập LẦN LƯỢT TẤT CẢ các trận (không giới hạn số lượng)
            for url, title in match_urls:
                captured_stream = None

                def handle_request(request):
                    nonlocal captured_stream
                    req_url = request.url
                    if ".m3u8" in req_url and "blob:" not in req_url:
                        captured_stream = req_url

                page.on("request", handle_request)

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    await page.wait_for_timeout(2500)
                except Exception:
                    pass

                if captured_stream:
                    matches_data.append({
                        "title": title,
                        "stream": captured_stream
                    })
                
                # Gỡ bỏ listener để tránh chồng chéo sự kiện
                page.remove_listener("request", handle_request)

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            await browser.close()

    # Xuất file M3U đầy đủ
    m3u_content = "#EXTM3U\n\n"
    default_logo = "https://i.imgur.com/v8R2PzA.png"

    if matches_data:
        for item in matches_data:
            title = item['title']
            
            logo = default_logo
            if "Việt Nam" in title or "Vietnam" in title:
                logo = "https://flagcdn.com/w320/vn.png"
            elif "Hàn Quốc" in title or "Korea" in title:
                logo = "https://flagcdn.com/w320/kr.png"
            elif "Thái Lan" in title or "Thailand" in title:
                logo = "https://flagcdn.com/w320/th.png"
            elif "Anh" in title or "England" in title:
                logo = "https://flagcdn.com/w320/gb-eng.png"

            m3u_content += f'#EXTINF:-1 tvg-logo="{logo}" group-title="Phá Làng TV", ⚽ {title}\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
            m3u_content += f'{item["stream"]}\n\n'
    else:
        m3u_content += f'#EXTINF:-1 tvg-logo="{default_logo}" group-title="Phá Làng TV", 🟢 Đang cập nhật danh sách trận đấu...\n'
        m3u_content += f'#EXTVLCOPT:http-referrer=https://phalang.live/\n'
        m3u_content += 'https://phalang.live/\n\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Hoàn tất! Đã xuất thành công {len(matches_data)} trận đấu vào playlist.m3u")

asyncio.run(run())
