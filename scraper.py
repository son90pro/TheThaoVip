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

def get_team_logo_url(team_name: str) -> str:
    """Tra cứu link logo PNG chuẩn quốc kỳ để hiển thị tốt trên TiviMate"""
    t_lower = team_name.lower().strip()
    logos = {
        "laos": "https://flagcdn.com/w320/la.png",
        "brunei": "https://flagcdn.com/w320/bn.png",
        "palestine": "https://flagcdn.com/w320/ps.png",
        "new zealand": "https://flagcdn.com/w320/nz.png",
        "japan": "https://flagcdn.com/w320/jp.png",
        "uruguay": "https://flagcdn.com/w320/uy.png",
        "south korea": "https://flagcdn.com/w320/kr.png",
        "ecuador": "https://flagcdn.com/w320/ec.png",
        "china": "https://flagcdn.com/w320/cn.png",
        "maldives": "https://flagcdn.com/w320/mv.png",
        "myanmar": "https://flagcdn.com/w320/mm.png",
        "timor leste": "https://flagcdn.com/w320/tl.png",
        "vietnam": "https://flagcdn.com/w320/vn.png",
        "thailand": "https://flagcdn.com/w320/th.png",
        "indonesia": "https://flagcdn.com/w320/id.png",
        "malaysia": "https://flagcdn.com/w320/my.png"
    }
    for key, url in logos.items():
        if key in t_lower:
            return url
    return "https://flagcdn.com/w320/fk.png"

def parse_teams_from_url(url: str) -> tuple:
    """Trích xuất tên 2 đội và tên đội 1 để gán logo"""
    try:
        match = re.search(r'/(?:truc-tiep|match|live)/([^/?#]+)', url)
        if not match:
            return "", ""
        slug = match.group(1)
        
        parts = slug.split('-vs-')
        if len(parts) != 2:
            return "", ""
        
        team1_slug, team2_slug = parts[0], parts[1]
        
        team1_slug = re.sub(r'^(?:blv-)?ga-(?:sieu-)?[a-z0-9]+-', '', team1_slug, flags=re.IGNORECASE)
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
        
        if t1 and t2 and len(t1) > 1 and len(t2) > 1:
            return f"{t1} vs {t2}", t1
    except Exception:
        pass
    return "", ""

def get_match_details(context, match_url):
    page = context.new_page()
    page.route("**/*.{png,jpg,jpeg,svg,css,woff,woff2}", lambda route: route.abort())
    
    m3u8_found = []
    def handle_request(request):
        url = request.url
        if ".m3u8" in url and "blob:" not in url:
            m3u8_found.append(url)
    page.on("request", handle_request)

    match_info = {
        "time_str": "",
        "m3u8_url": ""
    }

    try:
        page.goto(match_url, timeout=12000, wait_until="domcontentloaded")
        for _ in range(6):
            if m3u8_found:
                break
            time.sleep(0.5)
            
        match_info["m3u8_url"] = m3u8_found[0] if m3u8_found else ""

        details = page.evaluate('''() => {
            let tStr = "";
            const timeEls = Array.from(document.querySelectorAll('span, div, p, time, b'));
            for (let el of timeEls) {
                const text = el.innerText ? el.innerText.trim() : '';
                if (/\\d{1,2}[:h]\\d{2}/.test(text) && text.length < 25) {
                    tStr = text;
                    break;
                }
            }
            return { timeStr: tStr };
        }''')

        if details['timeStr']:
            match_info["time_str"] = details['timeStr']

    except Exception:
        pass
    finally:
        page.close()

    return match_info

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

        raw_matches = []
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

                    matches.push({
                        url: fullUrl,
                        fullText: fullText
                    });
                });

                return matches;
            }''')
            page.close()

            parsed_items = []
            for idx, item in enumerate(raw_matches):
                text = item['fullText']
                url = item['url']
                if not text:
                    continue

                details = get_match_details(context, url)

                # Thời gian trận đấu
                raw_time_text = details['time_str'] if details['time_str'] else text
                time_match = re.search(r'\b(\d{1,2}[:h]\d{2})\b', raw_time_text, re.I)
                
                if time_match:
                    m_time = time_match.group(1).replace('h', ':')
                    time_str = f"{m_time} 24/09"
                else:
                    time_str = "16:30 24/09"

                # Tên BLV
                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league)', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', blv_name, flags=re.IGNORECASE).strip()

                # Tên 2 đội và Logo
                teams_str, team1_name = parse_teams_from_url(url)
                if not teams_str:
                    teams_str = "Trận đấu Trực Tiếp"
                    team1_name = ""

                logo = get_team_logo_url(team1_name)

                # Phân loại luồng
                stream_type = "[flv]" if "flv" in url.lower() or "stream2" in url.lower() else "[hls]"

                blv_suffix = ""
                if clean_blv:
                    if not clean_blv.lower().startswith('gà'):
                        clean_blv = f"Gà {clean_blv}"
                    blv_suffix = f" ({clean_blv.title()})"

                full_title = f"{time_str} ⚽ {teams_str}{blv_suffix} {stream_type}".strip()

                parsed_items.append({
                    "title": full_title,
                    "logo": logo,
                    "url": url,
                    "m3u8_url": details['m3u8_url']
                })

            unique_dict = {}
            for p_item in parsed_items:
                if p_item['url'] not in unique_dict:
                    unique_dict[p_item['url']] = p_item

            final_matches = list(unique_dict.values())

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
    
