import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Headers chuẩn bắt buộc truyền cho trình phát IPTV để bypass chống leech CDN
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REFERER = "https://live08.chuoichientv.me/"
ORIGIN = "https://live08.chuoichientv.me"

# Thứ tự ưu tiên hiển thị Tab nhóm thể thao trên ứng dụng IPTV
GROUP_PRIORITY = [
    "Bóng Đá",
    "Bóng Chuyền",
    "Bóng Rổ",
    "Quần Vợt",
    "Cầu Lông",
    "Võ Thuật",
    "Đua Xe",
    "Thể Thao Khác"
]

# Ánh xạ mã bộ môn thể thao từ API V2 & từ khóa
SPORT_MAPPING = {
    "football": ("⚽", "Bóng Đá"),
    "soccer": ("⚽", "Bóng Đá"),
    "volleyball": ("🏐", "Bóng Chuyền"),
    "basketball": ("🏀", "Bóng Rổ"),
    "tennis": ("🎾", "Quần Vợt"),
    "badminton": ("🏸", "Cầu Lông"),
    "martial-arts": ("🥊", "Võ Thuật"),
    "mma": ("🥊", "Võ Thuật"),
    "boxing": ("🥊", "Võ Thuật"),
    "ufc": ("🥊", "Võ Thuật"),
    "racing": ("🏎️", "Đua Xe"),
    "f1": ("🏎️", "Đua Xe"),
    "motogp": ("🏎️", "Đua Xe")
}

def get_sport_info(sport_str, league_name="", title=""):
    """Phân loại bộ môn thể thao chính xác"""
    sport_key = str(sport_str).lower().strip()
    if sport_key in SPORT_MAPPING:
        return SPORT_MAPPING[sport_key]
    
    text = f"{sport_str} {league_name} {title}".lower()
    if any(k in text for k in ["bóng chuyền", "volleyball", "vnl"]):
        return ("🏐", "Bóng Chuyền")
    elif any(k in text for k in ["bóng rổ", "basketball", "nba", "vba"]):
        return ("🏀", "Bóng Rổ")
    elif any(k in text for k in ["quần vợt", "tennis", "atp", "wta"]):
        return ("🎾", "Quần Vợt")
    elif any(k in text for k in ["cầu lông", "badminton", "bwf"]):
        return ("🏸", "Cầu Lông")
    elif any(k in text for k in ["ufc", "mma", "boxing", "võ thuật", "one championship"]):
        return ("🥊", "Võ Thuật")
    elif any(k in text for k in ["f1", "motogp", "đua xe", "racing"]):
        return ("🏎️", "Đua Xe")
    
    return ("⚽", "Bóng Đá")

def fetch_v2_matches():
    """Lấy danh sách tất cả các trận đấu từ API V2"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json, text/plain, */*',
        'Referer': REFERER,
        'Origin': ORIGIN
    }
    
    matches_list = []
    page = 1
    max_pages = 10
    
    while page <= max_pages:
        url = f"https://api-v2.chuoichientv.net/v2/matches?page={page}&limit=50&type=blv"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                items = data.get('matches', [])
                if not items:
                    break
                matches_list.extend(items)
                
                pagination = data.get('pagination', {})
                total_pages = pagination.get('totalPages', 1)
                if page >= total_pages:
                    break
                page += 1
            else:
                break
        except Exception as e:
            print(f"Lỗi kết nối API V2 trang {page}: {e}")
            break
            
    print(f"Tổng số trận lấy từ API V2: {len(matches_list)}")
    return matches_list

def parse_v2_match(match, now_vn):
    """Bóc tách thông tin chi tiết từng trận từ API V2"""
    status = str(match.get('status', '')).lower()  # 'live', 'ns', 'ft'
    
    # Bỏ qua trận đã kết thúc
    if status == 'ft':
        return []

    match_time_str = match.get('matchTime', '')
    match_datetime = None
    if match_time_str:
        try:
            dt_utc = datetime.fromisoformat(match_time_str.replace('Z', '+00:00'))
            match_datetime = dt_utc.astimezone(VN_TZ)
        except Exception:
            pass

    today_vn = now_vn.date()
    tomorrow_vn = today_vn + timedelta(days=1)

    # Lọc chỉ lấy các trận Đang Live hoặc sắp diễn ra trong Hôm Nay & Ngày Mai
    if status != 'live':
        if not match_datetime:
            return []
        match_date = match_datetime.date()
        if match_date < today_vn or match_date > tomorrow_vn:
            return []

    # Định dạng ngày giờ hiển thị
    if match_datetime:
        time_display = match_datetime.strftime("%H:%M")
        date_display = match_datetime.strftime("%d/%m")
    else:
        time_display = "LIVE"
        date_display = now_vn.strftime("%d/%m")

    # Tên hai đội thi đấu
    teams = match.get('teams', {})
    home_name = str(teams.get('home', {}).get('name', '')).strip()
    away_name = str(teams.get('away', {}).get('name', '')).strip()
    
    if home_name and away_name:
        teams_str = f"{home_name} vs {away_name}"
    else:
        teams_str = home_name or away_name or "Trận đấu"

    # Logo
    logo = teams.get('home', {}).get('logo', '')
    if not logo:
        logo = match.get('league', {}).get('logo', '')

    # Phân loại bộ môn thể thao
    sport = match.get('sport', '')
    league_name = match.get('league', {}).get('name', '')
    emoji, group_title = get_sport_info(sport, league_name, teams_str)

    # Danh sách BLV & Luồng phát stream
    blvs = match.get('blvs', [])
    if not blvs:
        blvs = match.get('blvs_bonglau', []) or match.get('blvs_nguoitho', [])

    results = []
    if blvs:
        for blv in blvs:
            blv_name = str(blv.get('name', 'Chuối TV')).strip()
            if not blv_name.startswith("Chuối"):
                blv_name = f"Chuối {blv_name}"
                
            streams = blv.get('streams', [])
            for stream in streams:
                label = str(stream.get('label', 'FHD')).strip()
                stream_url = str(stream.get('url', '')).strip()
                if stream_url:
                    results.append({
                        'time': time_display,
                        'date': date_display,
                        'emoji': emoji,
                        'group': group_title,
                        'teams': teams_str,
                        'blv': blv_name,
                        'quality': label,
                        'logo': logo,
                        'stream_url': stream_url
                    })
    
    return results

def fetch_v1_articles():
    """Lấy danh sách bài viết từ API V1 bổ sung"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json, text/plain, */*',
        'Referer': REFERER,
        'Origin': ORIGIN
    }
    
    articles = []
    page = 1
    while page <= 3:
        url = f"https://api.chuoichientv.net/v1/articles?page={page}&limit=50"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get('data', [])
                if not items:
                    break
                articles.extend(items)
                page += 1
            else:
                break
        except Exception:
            break
    return articles

def parse_v1_article(item, now_vn):
    """Bóc tách bài viết từ API V1"""
    title = item.get('title', '')
    content = item.get('content', '')
    tags = item.get('tags', [])
    soup = BeautifulSoup(content, 'html.parser')
    
    match_datetime = None
    time_display = ""
    date_display = ""
    
    p_time = soup.find('p')
    if p_time:
        match_time = re.search(r'(\d{1,2}:\d{2})\s+(\d{1,2}/\d{1,2}/\d{4})', p_time.text)
        if match_time:
            time_str = match_time.group(1)
            date_str = match_time.group(2)
            try:
                dt_naive = datetime.strptime(f"{time_str} {date_str}", "%H:%M %d/%m/%Y")
                match_datetime = dt_naive.replace(tzinfo=VN_TZ)
                time_display = time_str
                date_display = dt_naive.strftime("%d/%m")
            except Exception:
                pass

    if not match_datetime and item.get('createdAt'):
        try:
            created_utc = datetime.fromisoformat(item['createdAt'].replace('Z', '+00:00'))
            match_datetime = created_utc.astimezone(VN_TZ)
            time_display = match_datetime.strftime("%H:%M")
            date_display = match_datetime.strftime("%d/%m")
        except Exception:
            pass

    today_vn = now_vn.date()
    tomorrow_vn = today_vn + timedelta(days=1)
    
    if match_datetime:
        match_date = match_datetime.date()
        if match_date < today_vn or match_date > tomorrow_vn:
            return []
    else:
        return []

    clean_title = re.split(r'[:–\-]', title)[0].strip()
    match_teams = re.search(r'(.+?\s+vs\s+.+)', title, re.IGNORECASE)
    teams_str = match_teams.group(1).strip() if match_teams else clean_title

    blv_name = "Chuối TV"
    blv_match = re.search(r'BLV\s+([A-Za-z0-9_\u00C0-\u1EF9]+)', content)
    if blv_match:
        blv_name = f"Chuối {blv_match.group(1)}"

    emoji, group_title = get_sport_info("", "", f"{' '.join(tags)} {title} {content}")
    
    images = soup.find_all('img')
    logo = images[0]['src'] if images and 'src' in images[0].attrs else item.get('thumbnail', '')
    
    stream_urls = re.findall(r'https?://[^\s\'"]+\.m3u8', content)
    if not stream_urls:
        return []

    results = []
    qualities = ["FHD", "HD1", "HD2"]
    for idx, stream_url in enumerate(stream_urls):
        q = qualities[idx] if idx < len(qualities) else f"HD{idx+1}"
        results.append({
            'time': time_display,
            'date': date_display,
            'emoji': emoji,
            'group': group_title,
            'teams': teams_str,
            'blv': blv_name,
            'quality': q,
            'logo': logo,
            'stream_url': stream_url
        })
    return results

def generate_m3u():
    now_vn = datetime.now(timezone.utc).astimezone(VN_TZ)
    all_streams = []
    seen_urls = set()

    # 1. Thu thập dữ liệu từ API V2 chuẩn
    v2_matches = fetch_v2_matches()
    for m in v2_matches:
        parsed_items = parse_v2_match(m, now_vn)
        for item in parsed_items:
            if item['stream_url'] not in seen_urls:
                seen_urls.add(item['stream_url'])
                all_streams.append(item)

    # 2. Thu thập dữ liệu từ API V1 bổ sung
    v1_articles = fetch_v1_articles()
    for a in v1_articles:
        parsed_items = parse_v1_article(a, now_vn)
        for item in parsed_items:
            if item['stream_url'] not in seen_urls:
                seen_urls.add(item['stream_url'])
                all_streams.append(item)

    # SẮP XẾP THỨ TỰ NHÓM TAB
    def get_group_order(item):
        group_name = item['group']
        if group_name in GROUP_PRIORITY:
            return GROUP_PRIORITY.index(group_name)
        return 99

    all_streams.sort(key=get_group_order)

    # Xuất dữ liệu ra file playlist.m3u kèm theo Headers đa tầng
    m3u_lines = ['#EXTM3U x-tvg-url=""']
    for s in all_streams:
        display_name = f"🟢 {s['time']} {s['date']} {s['emoji']} {s['teams']} ({s['blv']}) [{s['quality']}]"
        
        # Định dạng Pipe chuẩn truyền tham số cho TiviMate / OTT Navigator
        stream_with_headers = f"{s['stream_url']}|User-Agent={USER_AGENT}&Referer={REFERER}&Origin={ORIGIN}"
        
        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{s["logo"]}" group-title="{s["group"]}",{display_name}')
        # Header dành riêng cho TiviMate & OTT Navigator
        m3u_lines.append(f'#EXTHTTP:{{"User-Agent":"{USER_AGENT}","Referer":"{REFERER}","Origin":"{ORIGIN}"}}')
        # Header dành cho VLC Player & IPTV Smarters Pro
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
        m3u_lines.append(f'#EXTVLCOPT:http-referrer={REFERER}')
        m3u_lines.append(f'#EXTVLCOPT:http-origin={ORIGIN}')
        m3u_lines.append(stream_with_headers)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật playlist.m3u thành công với {len(all_streams)} luồng phát.")

if __name__ == "__main__":
    generate_m3u()
    
