import time
import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# Domain Cloudflare Worker proxy
WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"

BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

# Bộ lọc từ khóa giải đấu & trạng thái rác
FILTER_KEYWORDS = [
    "cup", "cúp", "league", "championship", "asian games", "emperor's cup", 
    "v-league", "premier", "champions", "euro", "copa", "afc", "oca", "fifa", 
    "uefa", "serie", "liga", "bundesliga", "k-league", "j-league", "lfp", "giải",
    "live", "trực tiếp", "hls", "flv", "xem ngay", "sắp diễn ra", "phút",
    "categoría", "primera", "hiệp 1", "hiệp 2", "hết giờ", "ht", "ft", "fulltime", "halftime"
]

def parse_teams_from_url(url: str) -> str:
    """
    Bóc tách chính xác tên 2 đội bóng từ URL slug, loại bỏ hoàn toàn nhiễu DOM.
    Ví dụ: /truc-tiep/america-de-cali-vs-deportivo-pereira-abc1234 -> America De Cali vs Deportivo Pereira
    """
    try:
        match = re.search(r'/(?:truc-tiep|match|live)/([^/?#]+)', url)
        if not match:
            return ""
        slug = match.group(1)
        
        parts = slug.split('-vs-')
        if len(parts) != 2:
            return ""
        
        team1_slug, team2_slug = parts[0], parts[1]
        team2_slug = re.sub(r'-[a-z0-9]{8,35}$', '', team2_slug, flags=re.IGNORECASE)
        
        def clean_word(w):
            w_low = w.lower()
            if w_low in ['nu', 'nữ']: return 'Nữ'
            if w_low in ['nam']: return 'Nam'
            if w_low in ['u23', 'u21', 'u20', 'u19', 'u18', 'u17', 'u16', 'u15']: return w.upper()
            if w_low in ['ir', 'uae', 'usa', 'uk']: return w.upper()
            return w.capitalize()

        t1 = " ".join([clean_word(w) for w in team1_slug.split('-')])
        t2 = " ".join([clean_word(w) for w in team2_slug.split('-')])
        
        if t1 and t2 and len(t1) > 1 and len(t2) > 1:
            return f"{t1} vs {t2}"
    except Exception:
        pass
    return ""

def get_m3u8_for_match(context, match_url):
    page = context.new_page()
    page.route("**/*.{png,jpg,jpeg,svg,css,woff,woff2}", lambda route: route.abort())
    
    m3u8_found = []

    def handle_request(request):
        url = request.url
        if ".m3u8" in url and "blob:" not in url:
            m3u8_found.append(url)

    page.on("request", handle_request)

    try:
        page.goto(match_url, timeout=12000, wait_until="domcontentloaded")
        for _ in range(6):
            if m3u8_found:
                break
            time.sleep(0.5)
    except Exception:
        pass
    finally:
        page.close()

    return m3u8_found[0] if m3u8_found else None

def run_scraper():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        # Thiết lập múi giờ Việt Nam
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )
        page = context.new_page()

        final_matches = []
        try:
            print(f"[*] Đang tải trang chủ Gà Vàng TV: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

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
                url = item['url']
                if not text:
                    continue

                # 1. Trích xuất thời gian
                time_match = re.search(r'(\d{1,2}:\d{2})', text)
                date_match = re.search(r'(\d{1,2}/\d{1,2})', text)
                m_time = time_match.group(1) if time_match else "LIVE"
                m_date = date_match.group(1) if date_match else ""
                time_str = f"{m_time} {m_date}".strip()

                # 2. Trích xuất tên BLV
                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league)', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', blv_name, flags=re.IGNORECASE).strip()

                # 3. Trích xuất tên 2 đội (Ưu tiên 1: Lấy từ URL Slug)
                teams_str = parse_teams_from_url(url)

                # Ưu tiên 2: Trích xuất từ DOM text nếu URL không có slug vs
                if not teams_str:
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
                        if len(line) >= 2 and re.search(r'[A-Za-zÀ-ỹ0-9]', line):
                            valid_lines.append(line)

                    vs_match = re.search(r'([A-Za-zÀ-ỹ0-9\s\.\-]+)\s+(?:vs|-)\s+([A-Za-zÀ-ỹ0-9\s\.\-]+)', clean_text_no_time, re.IGNORECASE)
                    if vs_match:
                        t1 = vs_match.group(1).split('\n')[-1].strip()
                        t2 = vs_match.group(2).split('\n')[0].strip()
                        if len(t1) >= 2 and len(t2) >= 2 and not t1.isdigit() and not t2.isdigit():
                            if not any(kw in t1.lower() for kw in FILTER_KEYWORDS) and not any(kw in t2.lower() for kw in FILTER_KEYWORDS):
                                teams_str = f"{t1} vs {t2}"

                    if not teams_str:
                        if len(valid_lines) >= 2:
                            teams_str = f"{valid_lines[0]} vs {valid_lines[1]}"
                        elif len(valid_lines) == 1:
                            teams_str = valid_lines[0]

                # Lọc kiểm tra trùng lặp giữa tên BLV và tiêu đề trận đấu
                if teams_str:
                    if re.search(r'^(gà|blv)\b', teams_str, re.IGNORECASE) or (blv_name and blv_name.lower() in teams_str.lower()):
                        teams_str = "Trận đấu Trực Tiếp"
                else:
                    teams_str = "Trận đấu Trực Tiếp"

                # 4. Định dạng BLV in hoa ở cuối tiêu đề
                blv_suffix = ""
                if clean_blv:
                    if clean_blv.lower() not in teams_str.lower():
                        blv_suffix = f" ({clean_blv.upper()})"

                full_title = f"{time_str} ⚽ {teams_str}{blv_suffix}"

                parsed_items.append({
                    "title": full_title,
                    "logo": item['logo'],
                    "url": item['url']
                })

            # 5. Lọc trùng lặp theo duy nhất URL trận đấu (Khắc phục hoàn toàn lặp trận)
            unique_dict = {}
            for p_item in parsed_items:
                url_key = p_item['url']
                if url_key not in unique_dict:
                    unique_dict[url_key] = p_item

            final_matches = list(unique_dict.values())
            print(f"[*] Tìm thấy tổng cộng {len(final_matches)} luồng trận đấu.")

            page.close()

            # Bóc tách luồng m3u8 cho các trận
            for idx, match in enumerate(final_matches):
                print(f"[{idx+1}/{len(final_matches)}] Kiểm tra luồng: {match['title']}")
                m3u8_url = get_m3u8_for_match(context, match['url'])
                match['m3u8_url'] = m3u8_url

        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
        finally:
            browser.close()

    # Xuất tất cả trận đấu vào file playlist.m3u
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        for item in final_matches:
            logo_attr = f'tvg-logo="{item["logo"]}"' if item["logo"] else ''
            
            if item.get('m3u8_url'):
                stream_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(item['m3u8_url'], safe='')}"
            else:
                stream_url = f"https://{WORKER_DOMAIN}/live?url={quote(item['url'], safe='')}"
            
            f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
            f.write(f'{stream_url}\n\n')

    print(f"[*] Đã xuất toàn bộ {len(final_matches)} trận đấu vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
