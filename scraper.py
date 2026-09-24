import time
import re
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright

WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
BASE_URL = "https://gavang33.me"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Gà Vàng 33 TV"

# Danh sách cờ quốc gia đầy đủ
LOGOS = {
    # Châu Âu
    "netherlands": "https://flagcdn.com/w320/nl.png", "hà lan": "https://flagcdn.com/w320/nl.png",
    "germany": "https://flagcdn.com/w320/de.png", "đức": "https://flagcdn.com/w320/de.png",
    "spain": "https://flagcdn.com/w320/es.png", "tây ban nha": "https://flagcdn.com/w320/es.png",
    "france": "https://flagcdn.com/w320/fr.png", "pháp": "https://flagcdn.com/w320/fr.png",
    "italy": "https://flagcdn.com/w320/it.png", "ý": "https://flagcdn.com/w320/it.png",
    "portugal": "https://flagcdn.com/w320/pt.png", "bồ đào nha": "https://flagcdn.com/w320/pt.png",
    "england": "https://flagcdn.com/w320/gb-eng.png", "anh": "https://flagcdn.com/w320/gb-eng.png",
    "wales": "https://flagcdn.com/w320/gb-wls.png", "scotland": "https://flagcdn.com/w320/gb-sct.png",
    "andorra": "https://flagcdn.com/w320/ad.png", "malta": "https://flagcdn.com/w320/mt.png",

    # Châu Á & Trung Đông
    "vietnam": "https://flagcdn.com/w320/vn.png", "việt nam": "https://flagcdn.com/w320/vn.png",
    "thailand": "https://flagcdn.com/w320/th.png", "thái lan": "https://flagcdn.com/w320/th.png",
    "indonesia": "https://flagcdn.com/w320/id.png", "malaysia": "https://flagcdn.com/w320/my.png",
    "japan": "https://flagcdn.com/w320/jp.png", "nhật bản": "https://flagcdn.com/w320/jp.png",
    "south korea": "https://flagcdn.com/w320/kr.png", "hàn quốc": "https://flagcdn.com/w320/kr.png", "korea": "https://flagcdn.com/w320/kr.png",
    "china": "https://flagcdn.com/w320/cn.png", "trung quốc": "https://flagcdn.com/w320/cn.png",
    "qatar": "https://flagcdn.com/w320/qa.png", "bahrain": "https://flagcdn.com/w320/bh.png",
    "united arab emirates": "https://flagcdn.com/w320/ae.png", "uae": "https://flagcdn.com/w320/ae.png",
    "yemen": "https://flagcdn.com/w320/ye.png", "maldives": "https://flagcdn.com/w320/mv.png",
    "myanmar": "https://flagcdn.com/w320/mm.png", "timor leste": "https://flagcdn.com/w320/tl.png",

    # Châu Phi & Nam Mỹ
    "namibia": "https://flagcdn.com/w320/na.png", "congo": "https://flagcdn.com/w320/cg.png", "republic of the congo": "https://flagcdn.com/w320/cg.png",
    "brazil": "https://flagcdn.com/w320/br.png", "argentina": "https://flagcdn.com/w320/ar.png",
    "uruguay": "https://flagcdn.com/w320/uy.png", "ecuador": "https://flagcdn.com/w320/ec.png"
}

def get_team_logo_url(teams_str: str) -> str:
    t_lower = teams_str.lower()
    for key, url in LOGOS.items():
        if key in t_lower:
            return url
    return "https://flagcdn.com/w320/un.png"

def clean_word(w: str) -> str:
    w_low = w.lower()
    if w_low in ['nu', 'nữ']: return 'Nữ'
    if w_low in ['nam']: return 'Nam'
    if w_low in ['u23', 'u21', 'u20', 'u19', 'u18', 'u17', 'u16', 'u15']: return w.upper()
    if w_low in ['ir', 'uae', 'usa', 'uk']: return w.upper()
    return w.capitalize()

def parse_teams_from_url(url: str) -> str:
    try:
        match = re.search(r'/(?:truc-tiep|match|live)/([^/?#]+)', url)
        if not match:
            return ""
        slug = match.group(1)
        
        parts = slug.split('-vs-')
        if len(parts) != 2:
            return ""
        
        team1_slug, team2_slug = parts[0], parts[1]
        
        team1_slug = re.sub(r'^(?:blv-)?ga-(?:sieu-)?[a-z0-9]+-', '', team1_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-luc-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-ngay-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-[a-z0-9]{8,35}$', '', team2_slug, flags=re.IGNORECASE)
        
        t1 = " ".join([clean_word(w) for w in team1_slug.split('-')])
        t2 = " ".join([clean_word(w) for w in team2_slug.split('-')])
        
        if t1 and t2 and len(t1) > 1 and len(t2) > 1:
            return f"{t1} vs {t2}"
    except Exception:
        pass
    return ""

def get_match_details(context, match_url):
    page = context.new_page()
    page.route("**/*.{png,jpg,jpeg,svg,css,woff,woff2}", lambda route: route.abort())
    
    m3u8_found = []
    def handle_request(request):
        url = request.url
        if ".m3u8" in url and "blob:" not in url and url not in m3u8_found:
            m3u8_found.append(url)
            
    page.on("request", handle_request)
    match_info = {"time_str": "", "m3u8_url": ""}

    try:
        page.goto(match_url, timeout=8000, wait_until="domcontentloaded")
        
        try:
            page.click('.play-btn, .btn-play, #player, iframe, video', timeout=1000)
        except Exception:
            pass

        for _ in range(5):
            if m3u8_found:
                break
            time.sleep(0.5)

        match_info["m3u8_url"] = m3u8_found[0] if m3u8_found else ""

        details = page.evaluate('''() => {
            let tStr = "";
            const timeEls = Array.from(document.querySelectorAll('span, div, p, time, b'));
            for (let el of timeEls) {
                const text = el.innerText ? el.innerText.trim() : '';
                if (/\\d{1,2}[:h]\\d{2}/.test(text) && text.length < 30) {
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
    today_str = datetime.now().strftime("%d/%m")
    
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
            time.sleep(2)

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

            print(f"[*] Đã cào được {len(raw_matches)} trận đấu. Đang quét chi tiết...")

            parsed_items = []
            for item in raw_matches:
                text = item['fullText']
                url = item['url']
                if not text:
                    continue

                details = get_match_details(context, url)

                # 1. Thời gian
                raw_time_text = details['time_str'] if details['time_str'] else text
                time_match = re.search(r'\b(\d{1,2}[:h]\d{2})\b', raw_time_text, re.I)
                date_match = re.search(r'\b(\d{1,2}/\d{1,2})\b', raw_time_text)
                extracted_date = date_match.group(1) if date_match else today_str

                time_str = f"{time_match.group(1).replace('h', ':')} {extracted_date}" if time_match else f"Trực Tiếp {extracted_date}"

                # 2. Tên BLV
                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV|Caster)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league)', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', blv_name, flags=re.IGNORECASE).strip()

                # 3. Tên trận & Logo Cờ Chuẩn
                teams_str = parse_teams_from_url(url)
                if not teams_str:
                    teams_str = "Trận đấu Trực Tiếp"

                logo = get_team_logo_url(teams_str)
                stream_type = "[flv]" if "flv" in url.lower() or "stream2" in url.lower() else "[hls]"

                blv_suffix = f" ({clean_blv.title()})" if clean_blv else ""
                status_icon = "🟢 " if details['m3u8_url'] or any(k in text.lower() for k in ["hiệp", "phút", "live", "đang diễn ra"]) else "🟡 "

                full_title = f"{status_icon}{time_str} ⚽ {teams_str}{blv_suffix} {stream_type}".strip()

                parsed_items.append({
                    "title": full_title,
                    "logo": logo,
                    "url": url,
                    "m3u8_url": details['m3u8_url']
                })

            # Lọc trùng link & Đánh dấu Server
            seen_urls = set()
            title_tracker = {}
            final_matches = []

            for p_item in parsed_items:
                if p_item['url'] in seen_urls:
                    continue
                seen_urls.add(p_item['url'])

                raw_title = p_item['title']
                if raw_title in title_tracker:
                    title_tracker[raw_title] += 1
                    p_item['title'] = f"{raw_title} (SV{title_tracker[raw_title]})"
                else:
                    title_tracker[raw_title] = 1

                final_matches.append(p_item)

        except Exception as e:
            print(f"[!] Lỗi: {e}")
        finally:
            browser.close()

    # Ghi file Playlist M3U Đầy Đủ
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")

        for item in final_matches:
            logo_attr = f'tvg-logo="{item["logo"]}"' if item["logo"] else ''
            
            # Ưu tiên link proxy trực tiếp nếu cào được m3u8, nếu chưa tới giờ đá sẽ quay về route /live
            if item.get('m3u8_url'):
                stream_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(item['m3u8_url'], safe='')}"
            else:
                stream_url = f"https://{WORKER_DOMAIN}/live?url={quote(item['url'], safe='')}"
            
            f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
            f.write(f'#EXTHTTP:{{"urls":["(.*)"],"headers":{{"Referer":"{BASE_URL}/"}}}}\n')
            f.write(f'{stream_url}\n\n')

    print(f"[*] Đã xuất thành công ĐẦY ĐỦ {len(final_matches)} trận đấu vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
