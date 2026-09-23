import time
import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# ⚠️ BẮT BUỘC: Thay domain Cloudflare Worker của anh Sơn vào đây (Không kèm https://)
WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

FILTER_KEYWORDS = [
    "cup", "cúp", "league", "championship", "asian games", "emperor's cup", 
    "v-league", "premier", "champions", "euro", "copa", "afc", "oca", "fifa", 
    "uefa", "serie", "liga", "bundesliga", "k-league", "j-league", "lfp", "giải",
    "live", "trực tiếp", "hls", "flv", "xem ngay", "sắp diễn ra", "phút"
]

def get_m3u8_for_match(context, match_url):
    page = context.new_page()
    # Tối ưu tốc độ: Chặn tải hình ảnh, CSS để bắt link nhanh nhất
    page.route("**/*.{png,jpg,jpeg,svg,css,woff,woff2}", lambda route: route.abort())
    
    m3u8_found = []

    def handle_request(request):
        url = request.url
        if ".m3u8" in url and "blob:" not in url:
            m3u8_found.append(url)

    page.on("request", handle_request)

    try:
        page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
        # Đợi tối đa 4 giây để Player JS kích hoạt & tạo request m3u8
        for _ in range(8):
            if m3u8_found:
                break
            time.sleep(0.5)
    except Exception as e:
        print(f"Lỗi tải trang {match_url}: {e}")
    finally:
        page.close()

    return m3u8_found[0] if m3u8_found else None

def run_scraper():
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

        final_matches = []
        try:
            print(f"[*] Đang tải trang chủ: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Bóc tách danh sách trận đấu
            raw_matches = page.evaluate('''() => {
                const matches = [];
                const cards = Array.from(document.querySelectorAll('.match-item, .item-match, .card-match, .match-card, div[class*="match"]'));
                const targets = cards.length > 0 ? cards : Array.from(document.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"]')).map(a => a.closest('.card, .item, div') || a);

                targets.forEach(card => {
                    const links = Array.from(card.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"]'));
                    const primaryLink = links[0] || (card.tagName === 'A' ? card : null);
                    if (!primaryLink) return;
                    
                    const href = primaryLink.getAttribute('href');
                    if (!href) return;

                    let logo = '';
                    const teamImgs = Array.from(card.querySelectorAll('[class*="team"] img, [class*="club"] img, .logo img'));
                    if (teamImgs.length > 0) {
                        let src = teamImgs[0].getAttribute('src') || teamImgs[0].getAttribute('data-src') || '';
                        if (src) logo = src.startsWith('http') ? src : window.location.origin + src;
                    }
                    if (!logo) {
                        const allImgs = Array.from(card.querySelectorAll('img'));
                        for (let img of allImgs) {
                            let src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                            if (src && !src.includes('avatar') && !src.includes('favicon')) {
                                logo = src.startsWith('http') ? src : window.location.origin + src;
                                break;
                            }
                        }
                    }

                    matches.push({
                        url: href.startsWith('http') ? href : window.location.origin + href,
                        fullText: card.innerText || '',
                        logo: logo
                    });
                });

                return matches;
            }''')

            parsed_items = []
            for item in raw_matches:
                text = item['fullText']
                if not text:
                    continue

                time_match = re.search(r'(\d{1,2}:\d{2})', text)
                date_match = re.search(r'(\d{1,2}/\d{1,2})', text)
                m_time = time_match.group(1) if time_match else "LIVE"
                m_date = date_match.group(1) if date_match else ""
                time_str = f"{m_time} {m_date}".strip()

                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2})', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                clean_text_no_time = re.sub(r'\d{1,2}:\d{2}', '', text)
                clean_text_no_time = re.sub(r'\d{1,2}/\d{1,2}', '', clean_text_no_time)

                lines = [l.strip() for l in clean_text_no_time.split('\n') if l.strip()]
                valid_lines = []
                for line in lines:
                    l_lower = line.lower()
                    if any(kw in l_lower for kw in FILTER_KEYWORDS):
                        continue
                    if blv_name and l_lower in blv_name.lower():
                        continue
                    if re.search(r'^(gà|blv)\s+', l_lower):
                        continue
                    if len(line) >= 2 and re.search(r'[A-Za-zÀ-ỹ]', line):
                        valid_lines.append(line)

                teams_str = ""
                vs_match = re.search(r'([A-Za-zÀ-ỹ0-9\s\.\-]+)\s+(?:vs|-)\s+([A-Za-zÀ-ỹ0-9\s\.\-]+)', clean_text_no_time, re.IGNORECASE)
                if vs_match:
                    t1 = vs_match.group(1).split('\n')[-1].strip()
                    t2 = vs_match.group(2).split('\n')[0].strip()
                    if len(t1) >= 2 and len(t2) >= 2 and not t1.isdigit() and not t2.isdigit():
                        teams_str = f"{t1} vs {t2}"

                if not teams_str:
                    if len(valid_lines) >= 2:
                        if valid_lines[0].lower() != valid_lines[1].lower():
                            teams_str = f"{valid_lines[0]} vs {valid_lines[1]}"
                        else:
                            teams_str = valid_lines[0]
                    elif len(valid_lines) == 1:
                        teams_str = valid_lines[0]

                if not teams_str:
                    continue

                blv_suffix = f" ({blv_name})" if blv_name else ""
                full_title = f"{time_str} ⚽ {teams_str}{blv_suffix}"

                parsed_items.append({
                    "title": full_title,
                    "logo": item['logo'],
                    "url": item['url']
                })

            unique_dict = {}
            for p_item in parsed_items:
                key = f"{p_item['url']}_{p_item['title']}"
                if key not in unique_dict:
                    unique_dict[key] = p_item

            final_matches = list(unique_dict.values())
            print(f"[*] Tìm thấy {len(final_matches)} trận. Đang tiến hành lấy luồng m3u8...")

            page.close()

            # BẮT BẮT BUỘC LINK .M3U8 THẬT BẰNG PLAYWRIGHT
            for idx, match in enumerate(final_matches):
                print(f"[{idx+1}/{len(final_matches)}] Bóc tách: {match['title']}")
                m3u8_url = get_m3u8_for_match(context, match['url'])
                match['m3u8_url'] = m3u8_url
                if m3u8_url:
                    print(f"    => Đã tìm thấy M3U8: {m3u8_url[:50]}...")
                else:
                    print(f"    => Trận đấu chưa phát sóng.")

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        finally:
            browser.close()

    # Tạo file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        valid_count = 0
        for item in final_matches:
            if not item.get('m3u8_url'):
                continue
            
            logo_attr = f'tvg-logo="{item["logo"]}"' if item["logo"] else ''
            
            # Gửi link .m3u8 THẬT đã lấy được sang cho Cloudflare Worker Proxy
            proxy_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(item['m3u8_url'], safe='')}"
            
            f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
            f.write(f'{proxy_url}\n\n')
            valid_count += 1

        if valid_count == 0:
            f.write(f'#EXTINF:-1 tvg-logo="{BASE_URL}/favicon.ico" group-title="{GROUP_NAME}",Chưa có trận nào đang phát\n')
            f.write("http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4\n")

    print(f"[*] Đã xuất thành công {valid_count} trận đấu vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
