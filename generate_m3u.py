import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Referer chuẩn bắt buộc cho CDN Chuối Chiên TV
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REFERER = "https://live.chuoichien.tv/"

# Thứ tự ưu tiên hiển thị Tab nhóm thể thao
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

# Ánh xạ mã bộ môn thể thao
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

LIVE_STATUSES = {"live", "1h", "2h", "ht", "bt", "et", "pen", "p", "ns"}

def get_sport_info(sport_str, league_name="", title=""):
    """Phân loại bộ môn thể thao"""
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
    """Lấy danh sách các trận đấu từ API V2"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json, text/plain, */*',
        'Referer': REFERER
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
    """Bóc tách thông tin chi tiết từng trận"""
    status = str(match.get('status', '')).lower()
    
    if status in ['ft', 'canc', 'postp', 'abad']:
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

    if status not in LIVE_STATUSES:
        if not match_datetime:
            return []
        match_date = match_datetime.date()
        if match_date < today_vn or match_date > tomorrow_vn:
            return []

    if match_datetime:
        time_display = match_datetime.strftime("%H:%M")
        date_display = match_datetime.strftime("%d/%m")
    else:
        time_display = "LIVE"
        date_display = now_vn.strftime("%d/%m")

    # Xác định Icon trạng thái
    status_icon = "🟢" if status in ["live", "1h", "2h", "ht", "bt", "et", "pen"] else "🟡"

    teams = match.get('teams', {})
    home_name = str(teams.get('home', {}).get('name', '')).strip()
    away_name = str(teams.get('away', {}).get('name', '')).strip()
    
    if home_name and away_name:
        teams_str = f"{home_name} vs {away_name}"
    else:
        teams_str = home_name or away_name or "Trận đấu"

    logo = teams.get('home', {}).get('logo', '')
    if not logo:
        logo = match.get('league', {}).get('logo', '')

    sport = match.get('sport', '')
    league_name = match.get('league', {}).get('name', '')
    emoji, group_title = get_sport_info(sport, league_name, teams_str)

    blv_groups = [
        match.get('blvs', []),
        match.get('blvs_bonglau', []),
        match.get('blvs_nguoitho', [])
    ]

    results = []
    seen_streams_in_match = set()

    for group in blv_groups:
        if not group:
            continue
        for blv in group:
            blv_name = str(blv.get('name', 'Chuối TV')).strip()
            if not blv_name.startswith("Chuối"):
                blv_name = f"Chuối {blv_name}"
                
            streams = blv.get('streams', [])
            for stream in streams:
                label = str(stream.get('label', 'FHD')).strip()
                stream_url = str(stream.get('url', '')).strip()
                
                dedup_key = f"{blv_name}_{label}_{stream_url}"
                if stream_url and dedup_key not in seen_streams_in_match:
                    seen_streams_in_match.add(dedup_key)
                    results.append({
                        'status_icon': status_icon,
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

def generate_m3u():
    now_vn = datetime.now(timezone.utc).astimezone(VN_TZ)
    all_streams = []
    seen_urls = set()

    v2_matches = fetch_v2_matches()
    for m in v2_matches:
        parsed_items = parse_v2_match(m, now_vn)
        for item in parsed_items:
            if item['stream_url'] not in seen_urls:
                seen_urls.add(item['stream_url'])
                all_streams.append(item)

    def get_group_order(item):
        group_name = item['group']
        if group_name in GROUP_PRIORITY:
            return GROUP_PRIORITY.index(group_name)
        return 99

    all_streams.sort(key=get_group_order)

    # Xuất file playlist.m3u chuẩn khớp 100% mẫu hoạt động
    m3u_lines = ['#EXTM3U\n']
    
    for s in all_streams:
        display_name = f"{s['status_icon']} {s['time']} {s['date']} {s['emoji']} {s['teams']} ({s['blv']}) [{s['quality']}] [hls]"
        
        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{s["logo"]}" group-title="{s["group"]}" , {display_name}')
        m3u_lines.append(f'#EXTVLCOPT:http-referrer={REFERER}')
        m3u_lines.append(s['stream_url'])
        m3u_lines.append('')  # Dòng trống phân cách các kênh

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật playlist.m3u thành công với {len(all_streams)} luồng phát.")

if __name__ == "__main__":
    generate_m3u()
    
