import time
import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright

WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

FILTER_KEYWORDS = [
    "cup", "cúp", "league", "championship", "asian games", "emperor's cup", 
    "v-league", "premier", "champions", "euro", "copa", "afc", "oca", "fifa", 
    "uefa", "serie", "liga", "bundesliga", "k-league", "j-league", "lfp", "giải",
    "xem ngay", "sắp diễn ra", "phút", "categoría", "primera", "hiệp 1", "hiệp 2"
]

def extract_match_time(text: str) -> str:
    """Trích xuất chính xác ngày giờ 08:40 24/09"""
    if not text:
        return "LIVE"
        
    # 1. Tìm dạng HH:MM DD/MM hoặc HH:MM
    time_match = re.search(r'\b(\d{1,2}[:h]\d{2})\b', text, re.I)
    date_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', text, re.I)
    
    if time_match:
        m_time = time_match.group(1).replace('h', ':')
        m_date = date_match.group(1) if date_match else ""
        return f"{m_time} {m_date}".strip()
        
    # 2. Bắt dạng Luc HHMM Ngay DD MM (Luc 0840 Ngay 24 09)
    luc_match = re.search(r'\b(?:luc|lúc)\s*(\d{2})(\d{2})\s*(?:ngay|ngày)?\s*(\d{1,2})\s*(\d{1,2})?\b', text, re.I)
    if luc_match:
        hh, mm = luc_match.group(1), luc_match.group(2)
        dd, m_m = luc_match.group(3), luc_match.group(4)
        m_time = f"{int(hh):02d}:{mm}"
        m_date = f"{int(dd):02d}/{int(m_m):02d}" if m_m else ""
        return f"{m_time} {m_date}".strip()

    return "LIVE"

def clean_time_and_date_trash(text: str) -> str:
    """Lọc sạch các chuỗi ngày giờ lặp rác đằng sau tên trận"""
    if not text:
        return ""
    cleaned = re.sub(r'\b(?:luc|lúc)?\s*\d{3,4}\s*(?:ngay|ngày)?\s*\d{1,2}\s*[/_\s]?\s*\d{1,2}\s*[/_\s]?\s*(?:\d{2,4})?\b', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:luc|lúc)\s*\d{3,4}\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:ngay|ngày)\s*\d{1,2}\s*[/_\s]?\s*\d{1,2}\s*[/_\s]?\s*(?:\d{2,4})?\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b\d{1,2}[:h]\d{2}\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def parse_teams_from_url(url: str) -> str:
    """Trích xuất tên 2 đội bóng từ URL slug"""
    try:
        match = re.search(r'/(?:truc-tiep|match|live)/([^/?#]+)', url)
        if not match:
            return ""
        slug = match.group(1)
        
        parts = slug.split('-vs-')
        if len(parts) != 2:
            return ""
        
        team1_slug, team2_slug = parts[0], parts[1]
        
        # Lọc tên BLV dính ở team 1
        team1_slug = re.sub(r'^(?:blv-)?ga-(?:sieu-)?[a-z0-9]+-', '', team1_slug, flags=re.IGNORECASE)
        
        # Lọc Luc... Ngay... dính ở team 2
        team2_slug = re.sub(r'-luc-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-ngay-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
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
        
        t1 = clean_time_and_date_trash(t1)
        t2 = clean_time_and_date_trash(t2)
        
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
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )
        page = context.new_page()

        final_matches = []
        try:
            print(f"[*] Đang tải trang Gà Vàng 33 TV: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            raw_matches = page.evaluate('''() => {
                const matches = [];
                const links = Array.from(document.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"]'));
                const seenUrls = new Set();

                links.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href) return;

                    const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                    if (seenUrls.has(fullUrl)) return;
                    seenUrls.add(fullUrl);

                    let card = link;
                    let parent = link.parentElement;
                    while (parent && parent.tagName !== 'BODY') {
                        if (parent.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"]').length === 1) {
                            card = parent;
                            parent = parent.parentElement;
                        } else {
                            break;
                        }
                    }

                    const fullText = card ? card.innerText || '' : link.innerText || '';

                    // Lọc logo: Bỏ hẳn ảnh Avatar BLV (chứa avatar, blv, ga-sieu) để lấy Logo Đội bóng/Quốc kỳ
                    let logo = '';
                    if (card) {
                        const imgs = Array.from(card.querySelectorAll('img'));
                        for (let img of imgs) {
                            let src = img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('srcset') || '';
                            const lowSrc = src.toLowerCase();
                            if (src && !lowSrc.includes('favicon') && !lowSrc.includes('avatar') && !lowSrc.includes('blv') && !lowSrc.includes('ga-sieu') && !lowSrc.includes('logo-gavang')) {
                                logo = src.startsWith('http') ? src : window.location.origin + src;
                                break;
                            }
                        }
                    }

                    matches.push({
                        url: fullUrl,
                        fullText: fullText,
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

                # 1. Trích xuất Ngày Giờ CHUẨN TRƯỚC
                time_str = extract_match_time(text)

                # 2. Trích xuất tên BLV
                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league|luc|lúc|ngay|ngày)', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', blv_name, flags=re.IGNORECASE).strip()

                # 3. Trích xuất Tên 2 Đội
                teams_str = parse_teams_from_url(url)
                if not teams_str:
                    clean_text = clean_time_and_date_trash(text)
                    lines = [l.strip() for l in clean_text.split('\n') if l.strip()]
                    valid_lines = []
                    for line in lines:
                        l_lower = line.lower()
                        if any(kw in l_lower for kw in FILTER_KEYWORDS): continue
                        if blv_name and l_lower in blv_name.lower(): continue
                        if re.search(r'^(gà|blv)\s+', l_lower): continue
                        if len(line) >= 2 and re.search(r'[A-Za-zÀ-ỹ0-9]', line):
                            valid_lines.append(line)

                    vs_match = re.search(r'([A-Za-zÀ-ỹ0-9\s\.\-]+)\s+(?:vs|-)\s+([A-Za-zÀ-ỹ0-9\s\.\-]+)', clean_text, re.IGNORECASE)
                    if vs_match:
                        t1 = vs_match.group(1).split('\n')[-1].strip()
                        t2 = vs_match.group(2).split('\n')[0].strip()
                        if len(t1) >= 2 and len(t2) >= 2 and not t1.isdigit() and not t2.isdigit():
                            if not any(kw in t1.lower() for kw in FILTER_KEYWORDS) and not any(kw in t2.lower() for kw in FILTER_KEYWORDS):
                                teams_str = f"{t1} vs {t2}"

                    if not teams_str:
                        if len(valid_lines) >= 2: teams_str = f"{valid_lines[0]} vs {valid_lines[1]}"
                        elif len(valid_lines) == 1: teams_str = valid_lines[0]

                teams_str = clean_time_and_date_trash(teams_str)
                if not teams_str or re.search(r'^(gà|blv)\b', teams_str, re.IGNORECASE):
                    teams_str = "Trận đấu Trực Tiếp"

                # 4. Luồng stream [flv] hay [hls]
                stream_type = "[flv]" if "flv" in url.lower() or "stream2" in url.lower() else "[hls]"

                # 5. Ghép tên BLV dạng (Gà Siêu Bệu)
                blv_suffix = ""
                if clean_blv:
                    if not clean_blv.lower().startswith('gà'):
                        clean_blv = f"Gà {clean_blv}"
                    blv_suffix = f" ({clean_blv.title()})"

                full_title = f"{time_str} ⚽ {teams_str}{blv_suffix} {stream_type}".strip()

                parsed_items.append({
                    "title": full_title,
                    "logo": item['logo'],
                    "url": item['url']
                })

            # Lọc trùng theo URL
            unique_dict = {}
            for p_item in parsed_items:
                if p_item['url'] not in unique_dict:
                    unique_dict[p_item['url']] = p_item

            final_matches = list(unique_dict.values())
            print(f"[*] Tìm thấy {len(final_matches)} luồng trận đấu.")

            page.close()

            for idx, match in enumerate(final_matches):
                print(f"[{idx+1}/{len(final_matches)}] Lấy stream: {match['title']}")
                m3u8_url = get_m3u8_for_match(context, match['url'])
                match['m3u8_url'] = m3u8_url

        except Exception as e:
            print(f"[!] Lỗi: {e}")
        finally:
            browser.close()

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

    print(f"[*] Đã xuất xong vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
