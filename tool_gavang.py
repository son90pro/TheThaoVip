import asyncio
import re
import base64
import requests
from playwright.async_api import async_playwright

# --- CẤU HÌNH GITHUB CỦA ANH SƠN ---
GITHUB_TOKEN = "ĐIỀN_TOKEN_GITHUB_CỦA_ANH_VÀO_ĐÂY"
USER_NAME = "son90pro"  # Thay bằng Username GitHub của anh
REPO_NAME = "iptv-bongda"

TARGET_URL = "https://gavang33.me/"
DEFAULT_LOGO = "https://raw.githubusercontent.com/stv-logo/logo/main/sports.png"

async def run():
    matches_data = []

    async with async_playwright() as p:
        # Mở Chrome thật để vượt qua cơ chế chống bot
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("1. Đang mở Gà Vàng TV trên máy tính...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        # Lấy danh sách thẻ trận đấu
        cards = await page.query_selector_all("div")
        match_targets = []

        for card in cards:
            text = await card.inner_text()
            if "VS" in text and ("/" in text or ":" in text):
                if len(text) < 300 and "\n" in text:
                    anchor = await card.query_selector("a")
                    href = await anchor.get_attribute("href") if anchor else None
                    if not href:
                        href = await card.get_attribute("data-href") or await card.get_attribute("onclick")
                    
                    if href:
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        clean_title = " ".join(lines)
                        if "http" not in href:
                            match_url = re.search(r"'/([^']+)'", href)
                            href = f"https://gavang33.me/{match_url.group(1)}" if match_url else f"https://gavang33.me{href if href.startswith('/') else '/' + href}"
                        match_targets.append((href, clean_title))

        print(f"2. Bắt được {len(match_targets)} trận đấu. Đang tiến hành bóc tách luồng .m3u8...")

        # Mở từng trận để bắt link .m3u8 thực tế
        for url, title in match_targets[:10]:
            captured_stream = None

            def handle_request(request):
                nonlocal captured_stream
                if ".m3u8" in request.url and "blob:" not in request.url:
                    captured_stream = request.url

            page.on("request", handle_request)
            try:
                await page.goto(url, wait_until="commit", timeout=12000)
                await page.wait_for_timeout(3000)
            except Exception:
                pass

            if captured_stream:
                matches_data.append({"title": title, "stream": captured_stream})
            page.remove_listener("request", handle_request)

        await browser.close()

    # --- TẠO NỘI DUNG M3U ĐÚNG CẤU TRÚC MẪU ANH CẦN ---
    m3u_content = "#EXTM3U\n\n"
    if matches_data:
        for item in matches_data:
            m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV" , 🟢 {item["title"]} [FHD] [hls]\n'
            m3u_content += f'#EXTVLCOPT:http-referrer=https://gavang33.me/\n'
            m3u_content += f'{item["stream"]}\n\n'
    else:
        m3u_content += f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}" group-title="Gà Vàng TV" , 🟢 Gà Vàng TV Trang Chính\n'
        m3u_content += f'#EXTVLCOPT:http-referrer=https://gavang33.me/\n'
        m3u_content += f'https://gavang33.me/\n\n'

    # Ghi file ở máy nhà
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    # --- TỰ ĐỘNG ĐẨY LÊN GITHUB CỦA ANH SƠN ---
    if GITHUB_TOKEN != "ĐIỀN_TOKEN_GITHUB_CỦA_ANH_VÀO_ĐÂY":
        api_url = f"https://api.github.com/repos/{USER_NAME}/{REPO_NAME}/contents/playlist.m3u"
        headers_gh = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        sha = None
        res = requests.get(api_url, headers=headers_gh)
        if res.status_code == 200:
            sha = res.json()['sha']

        content_b64 = base64.b64encode(m3u_content.encode('utf-8')).decode('utf-8')
        payload = {"message": "Auto update playlist", "content": content_b64}
        if sha:
            payload["sha"] = sha

        push_res = requests.put(api_url, json=payload, headers=headers_gh)
        if push_res.status_code in [200, 201]:
            print("\n✅ ĐÃ ĐẨY FILE LÊN GITHUB THÀNH CÔNG!")
            print(f"👉 Link nạp vào Tivi: https://raw.githubusercontent.com/{USER_NAME}/{REPO_NAME}/main/playlist.m3u")

asyncio.run(run())

