import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Headers chuẩn giả lập trình duyệt Firefox/Chrome trên thiết bị
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

# Các trạng thái trận đấu được coi là đang diễn ra hoặc sắp diễn ra
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
    status = str(match.get('status', '')).lower()  # 'live', '1h', '2h', 'ht', 'ns', 'ft'
    
    # Bỏ qua trận đã kết thúc hoặc bị hủy
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

    # Nếu trận đấu không thuộc danh sách live_status thì kiểm tra ngày
    if status not in LIVE_STATUSES:
        if not match_datetime:
            return []
        match_date = match_datetime.date()
        if match_date < today_vn or match_date > tomorrow_vn:
            return []

    # Định dạng thời gian
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

    # Logo đội bóng / giải đấu
    logo = teams.get('home', {}).get('logo', '')
    if not logo:
        logo = match.get('league', {}).get('logo', '')

    # Bộ môn thể thao
    sport = match.get('sport', '')
    league_name = match.get('league', {}).get('name', '')
    emoji, group_title = get_sport_info(sport, league_name, teams_str)

    # Tạo Referer chính xác theo URL trận đấu thực tế trên web
    external_id = match.get('externalId', '')
    match_referer = REFERER
    if external_id:
        slug = re.sub(r'[^a-z0-9]+', '-', teams_str.lower()).strip('-')
        match_referer = f"https://live08.chuoichientv.me/live/{external_id}/{slug}"

    # Gộp danh sách các nguồn BLV
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
                
                # Tránh trùng lặp luồng trong cùng 1 trận
                dedup_key = f"{blv_name}_{label}_{stream_url}"
                if stream_url and dedup_key not in seen_streams_in_match:
                    seen_streams_in_match.add(dedup_key)
                    results.append({
                        'time': time_display,
                        'date': date_display,
                        'emoji': emoji,
                        'group': group_title,
                        'teams': teams_str,
                        'blv': blv_name,
                        'quality': label,
                        'logo': logo,
                        'stream_url': stream_url,
                        'match_referer': match_referer
                    })
    
    return results

def generate_m3u():
    now_vn = datetime.now(timezone.utc).astimezone(VN_TZ)
    all_streams = []
    seen_urls = set()

    # 1. Thu thập dữ liệu từ API V2
    v2_matches = fetch_v2_matches()
    for m in v2_matches:
        parsed_items = parse_v2_match(m, now_vn)
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

    # Xuất dữ liệu ra file playlist.m3u với bộ Header đa tầng
    m3u_lines = ['#EXTM3U x-tvg-url=""']
    
    for s in all_streams:
        display_name = f"🟢 {s['time']} {s['date']} {s['emoji']} {s['teams']} ({s['blv']}) [{s['quality']}]"
        ref_url = s['match_referer']

        # Dạng Pipe hỗ trợ TiviMate / OTT Navigator
        pipe_url = f"{s['stream_url']}|User-Agent={USER_AGENT}&Referer={ref_url}&Origin={ORIGIN}"

        # JSON Header tương thích ExoPlayer / TiviMate
        http_json = json.dumps({
            "User-Agent": USER_AGENT,
            "Referer": ref_url,
            "Origin": ORIGIN
        })

        m3u_lines.append(f'#EXTINF:-1 tvg-logo="{s["logo"]}" group-title="{s["group"]}",{display_name}')
        # Header dành cho TiviMate / ExoPlayer
        m3u_lines.append(f'#EXTHTTP:{http_json}')
        # Header dành cho Kodi / IPTV Simple Client
        m3u_lines.append(f'#KODPROP:inputstream.adaptive.stream_headers=User-Agent={USER_AGENT}&Referer={ref_url}&Origin={ORIGIN}')
        # Header dành cho VLC Player / IPTV Smarters
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
        m3u_lines.append(f'#EXTVLCOPT:http-referrer={ref_url}')
        m3u_lines.append(f'#EXTVLCOPT:http-origin={ORIGIN}')
        m3u_lines.append(pipe_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã xuất thành công playlist.m3u với {len(all_streams)} luồng phát.")

if __name__ == "__main__":
    generate_m3u()
    
