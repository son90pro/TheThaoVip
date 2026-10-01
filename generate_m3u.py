import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Thứ tự ưu tiên của các Tab nhóm thể thao trong IPTV
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

# Ánh xạ emoji và tên nhóm
SPORT_MAP = {
    "bong-da": ("⚽", "Bóng Đá"),
    "bong-chuyen": ("🏐", "Bóng Chuyền"),
    "bong-ro": ("🏀", "Bóng Rổ"),
    "quan-vot": ("🎾", "Quần Vợt"),
    "cau-long": ("🏸", "Cầu Lông"),
    "vo-thuat": ("🥊", "Võ Thuật"),
    "dua-xe": ("🏎️", "Đua Xe")
}

def detect_sport(tags, title, content):
    """Phân loại bộ môn thể thao chính xác"""
    text = f"{' '.join(tags)} {title} {content}".lower()
    
    if any(k in text for k in ["bóng chuyền", "volleyball", "vnl"]):
        return SPORT_MAP["bong-chuyen"]
    elif any(k in text for k in ["bóng rổ", "basketball", "nba", "vba"]):
        return SPORT_MAP["bong-ro"]
    elif any(k in text for k in ["quần vợt", "tennis", "atp", "wta"]):
        return SPORT_MAP["quan-vot"]
    elif any(k in text for k in ["cầu lông", "badminton", "bwf"]):
        return SPORT_MAP["cau-long"]
    elif any(k in text for k in ["ufc", "mma", "boxing", "võ thuật", "one championship"]):
        return SPORT_MAP["vo-thuat"]
    elif any(k in text for k in ["f1", "motogp", "đua xe"]):
        return SPORT_MAP["dua-xe"]
    
    return SPORT_MAP["bong-da"]

def extract_clean_teams(title):
    """Cắt lọc tên 2 đội bóng gọn gàng"""
    clean_title = re.split(r'[:–\-]', title)[0].strip()
    if re.search(r'\bvs\b', clean_title, re.IGNORECASE):
        return clean_title
        
    match = re.search(r'([A-Za-z0-9\s\.\p{L}]+?\s+vs\s+[A-Za-z0-9\s\.\p{L}]+)', title, re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    return clean_title

def extract_blv(content_html):
    """Trích xuất gọn tên BLV"""
    match_full = re.search(r'BLV(?:[\s\wTV:\–\-]+)?:\s*([^\.\<\n]+)', content_html, re.IGNORECASE)
    if match_full:
        blv = match_full.group(1).strip()
        if len(blv) <= 20 and not any(bad in blv.lower() for bad in ["anh em", "theo dõi", "phân tích", "cộng đồng"]):
            return blv if blv.startswith("Chuối") else f"Chuối {blv}"
            
    match_short = re.search(r'\bBLV\s+([A-ZÀ-Ỹ][a-zà-ỹ0-9_]+)', content_html)
    if match_short:
        name = match_short.group(1)
        return name if name.startswith("Chuối") else f"Chuối {name}"
        
    return "Chuối TV"

def parse_article(item, now_vn):
    """Bóc tách bài viết & kiểm tra lọc theo ngày"""
    title = item.get('title', '')
    content = item.get('content', '')
    tags = item.get('tags', [])
    soup = BeautifulSoup(content, 'html.parser')
    
    match_datetime = None
    time_display = ""
    date_display = ""
    
    # Bóc tách ngày giờ từ HTML
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

    # Lọc chỉ lấy các trận Hôm Nay và Ngày Mai
    today_vn = now_vn.date()
    tomorrow_vn = today_vn + timedelta(days=1)
    
    if match_datetime:
        match_date = match_datetime.date()
        if match_date < today_vn or match_date > tomorrow_vn:
            return None
    else:
        return None

    teams_str = extract_clean_teams(title)
    blv = extract_blv(content)
    emoji, group_title = detect_sport(tags, title, content)
    
    images = soup.find_all('img')
    logo = ""
    if images and 'src' in images[0].attrs:
        logo = images[0]['src']
    if not logo:
        logo = item.get('thumbnail', '')
        
    stream_urls = re.findall(r'https?://[^\s\'"]+\.m3u8', content)
    if not stream_urls:
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            if 'src' in iframe.attrs and iframe['src'].startswith('http'):
                stream_urls.append(iframe['src'])
                
    article_slug = item.get('slug', '')
    fallback_url = f"https://live08.chuoichientv.me/{article_slug}"
    
    return {
        'time': time_display,
        'date': date_display,
        'emoji': emoji,
        'group': group_title,
        'teams': teams_str,
        'blv': blv,
        'logo': logo,
        'streams': stream_urls if stream_urls else [fallback_url]
    }

def fetch_all_articles():
    """Cào toàn bộ danh sách bài viết bằng cách duyệt từng trang API"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://live08.chuoichientv.me/'
    }
    
    all_articles = []
    page = 1
    max_pages = 5  # Duyệt tối đa 5 trang đầu (tương đương 250 bài viết)
    
    while page <= max_pages:
        api_url = f"https://api.chuoichientv.net/v1/articles?page={page}&limit=50"
        try:
            res = requests.get(api_url, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                items = data.get('data', [])
                if not items:
                    break
                all_articles.extend(items)
                
                # Kiểm tra nếu đã hết trang
                pagination = data.get('pagination', {})
                total_pages = pagination.get('totalPages', 1)
                if page >= total_pages:
                    break
                page += 1
            else:
                break
        except Exception as e:
            print(f"Lỗi kết nối trang {page}: {e}")
            break
            
    print(f"Tổng số bài viết thu thập được từ API: {len(all_articles)}")
    return all_articles

def generate_m3u():
    now_vn = datetime.now(timezone.utc).astimezone(VN_TZ)
    articles = fetch_all_articles()
    
    matches_list = []

    for item in articles:
        try:
            parsed = parse_article(item, now_vn)
            if parsed:
                matches_list.append(parsed)
        except Exception as err:
            continue

    # SẮP XẾP THỨ TỰ NHÓM (Bóng Đá lên đầu tiên)
    def get_group_order(item):
        group_name = item['group']
        if group_name in GROUP_PRIORITY:
            return GROUP_PRIORITY.index(group_name)
        return 99

    matches_list.sort(key=get_group_order)

    # Ghi file M3U
    m3u_lines = ['#EXTM3U x-tvg-url=""']
    qualities = ["FHD", "HD1", "HD2"]

    for parsed in matches_list:
        for idx, stream_url in enumerate(parsed['streams']):
            quality = qualities[idx] if idx < len(qualities) else f"HD{idx+1}"
            display_name = f"🟢 {parsed['time']} {parsed['date']} {parsed['emoji']} {parsed['teams']} ({parsed['blv']}) [{quality}] [hls]"
            
            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{parsed["logo"]}" group-title="{parsed["group"]}",{display_name}\n{stream_url}'
            )

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    print(f"Đã cập nhật file playlist.m3u thành công với {len(m3u_lines)-1} luồng phát.")

if __name__ == "__main__":
    generate_m3u()
    
