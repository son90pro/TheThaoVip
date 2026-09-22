import asyncio
from playwright.async_api import async_playwright
import re

async def scrape_match(context, match_info):
    url, title = match_info
    page = await context.new_page()
    captured_stream = None

    def handle_request(request):
        nonlocal captured_stream
        req_url = request.url
        if ".m3u8" in req_url and "blob:" not in req_url:
            captured_stream = req_url

    page.on("request", handle_request)

    try:
        # Giảm timeout xuống 8s để chạy thật nhanh
        await page.goto(url, wait_until="commit", timeout=8000)
        await page.wait_for_timeout(3000)
    except Exception:
        pass
    finally:
        await page.close()

    if captured_stream:
        return {"title": title, "stream": captured_stream}
    return None

async def run():
    matches_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print("1. Đang truy cập trang chủ Phá Làng TV...")
            await page.goto("https://phalang.live/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)

            # Lấy tất cả các đường link trên trang
            elements = await page.query_selector_all("a, div[href]")
            match_list = []
            seen_urls = set()

            for el in elements:
                href = await el.get_attribute("href")
                if not href:
                    href = await el.get_attribute("data-href")

                if href and href != "/" and not href.startswith("#") and "javascript" not in href:
                    full_url = href if href.startswith("http") else f"https://phalang.live{href}"
                    
                    if full_url not in seen_urls and "phalang.live" in full_url:
                        seen_urls.add(full_url)
                        text_content = await el.inner_text()
                        clean_text = " ".join(text_content.split())
                        clean_text = re.sub(r'^[0-9\s]+', '', clean_text)
                        
                        # Loại bỏ các link trang chủ, điều khoản...
                        if len(clean_text) > 4 and not any(x in clean_text.lower() for x in ["trang chủ", "lịch thi đấu", "bảng xếp hạng", "tin tức"]):
                            match_list.append((full_url, clean_text))

            print(f"2. Bóc tách được {len(match_list)} trận đấu. Đang tiến hành quét luồng stream song song...")

            # Chạy quét tối đa 5 trận cùng lúc để tránh bị nghẽn
            semaphore = asyncio.Semaphore(5)
            
            async def worker(match_info):
                async with semaphore:
                    return await scrape_match(context, match_info)

            tasks = [worker(m) for m in match_list]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res:
                    matches_data.append(res)

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        finally:
            await browser.close()

    # Định dạng M3U xuất ra
    m3u_content = "#EXTM3U\n\n"
    # Link logo quả bóng đá chuẩn (không bị lỗi như link cũ)
    default_logo = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

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

    print(f"Hoàn thành! Xuất thành công {len(matches_data)} trận vào file playlist.m3u")

asyncio.run(run())
