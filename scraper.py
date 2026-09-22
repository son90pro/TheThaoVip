import asyncio
import json
import re
from playwright.async_api import async_playwright

TARGET_URL = "https://cakhiazag.tv/"
DEFAULT_LOGO = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

async def run():
    matches_data = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            print("1. Đang truy cập Cà Khịa TV...")
            try:
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3500)
            except Exception as e:
                print(f"Cảnh báo truy cập trang chủ: {e}")

            # 1. Bóc tách JSON __NEXT_DATA__
            next_data_el = await page.query_selector("script#__NEXT_DATA__")
            if next_data_el:
                try:
                    content = await next_data_el.inner_text()
                    data = json.loads(content)
                    page_props = data.get("props", {}).get("pageProps", {})
                    raw_matches = page_props.get("matches", []) or page_props.get("dataMatches", [])

                    for m in raw_matches:
                        home = m.get("home_name") or m.get("homeTeam", {}).get("name", "")
                        away = m.get("away_name") or m.get("awayTeam", {}).get("name", "")
                        time_str = m.get("time") or m.get("match_time", "")
                        date_str = m.get("date") or m.get("match_date", "")
                        commentator = m.get("commentator") or m.get("blv", "")
                        logo = m.get("home_flag") or m.get("thumbnail") or DEFAULT_LOGO
                        slug = m.get("slug") or m.get("id")

                        if home and away:
                            time_part = f"{time_str} {date_str}".strip()
                            blv_part = f" ({commentator.upper()})" if commentator else ""
                            formatted_title = f"{time_part} ⚽ {home} vs {away}{blv_part}".strip()
                            
                            match_url = f"https://cakhiazag.tv/truc-tiep/{slug}" if slug else TARGET_URL
                            matches_data.append({
                                "title": formatted_title,
                                "url": match_url,
                                "logo": logo
                            })
                except Exception as err:
                    print(f"Lỗi đọc JSON: {err}")

            # 2. Quét HTML thẻ A nếu không tìm thấy dữ liệu JSON
            if not matches_data:
                links = await page.query_selector_all("a[href*='/truc-tiep/']")
                seen = set()
                for link in links:
                    href = await link.get_attribute("href")
                    if href and href not in seen:
                        seen.add(href)
                        full_url = f"https://cakhiazag.tv{href if href.startswith('/') else '/' + href}"
                        text = await link.inner_text()
                        clean_text = " ".join([l.strip() for l in text.split("\n") if l.strip()])
                        if not clean_text or len(clean_text) < 4:
                            slug = href.split("/")[-1].replace("-", " ").title()
                            clean_text = f"⚽ {slug}"
                        matches_data.append({
                            "title": clean_text,
                            "url": full_url,
                            "logo": DEFAULT_LOGO
                        })

            print(f"2. Tìm thấy {len(matches_data)} trận. Đang bắt luồng .m3u8...")

            final_playlist = []
            for item in matches_data[:10]:
                m3u8_url = None

                def handle_request(req):
                    nonlocal m3u8_url
                    if ".m3u8" in req.url and "blob:" not in req.url:
                        m3u8_url = req.url

                page.on("request", handle_request)
                try:
                    await page.goto(item["url"], wait_until="commit", timeout=12000)
                    await page.wait_for_timeout(3000)
                except Exception:
                    pass
                page.remove_listener("request", handle_request)

                if m3u8_url:
                    final_playlist.append({
                        "title": item["title"],
                        "logo": item["logo"],
                        "stream": m3u8_url
                    })

            await browser.close()

    except Exception as global_err:
        print(f"Lỗi hệ thống: {global_err}")
        final_playlist = []

    # Tạo nội dung file playlist.m3u
    m3u_content = "#EXTM3U\n\n"
    if 'final_playlist' in locals() and final_playlist:
        for item in final_playlist:
            m3u_content += f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="Cà Khịa TV" , 🟢 {item["title"]} [FHD]\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://cakhiazag.tv/\n'
            m3u_content += f'{item["stream"]}\n\n'
    else:
        m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Cà Khịa TV" , 🟢 Cà Khịa TV Trang Chính [FHD]\n'
        m3u_content += f'#EXTVLCOPT:http-referrer=https://cakhiazag.tv/\n'
        m3u_content += f'{TARGET_URL}\n\n'

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print("✅ Đã hoàn tất ghi file playlist.m3u.")

if __name__ == "__main__":
    asyncio.run(run())
    
