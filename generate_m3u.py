import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# API URL của Chuối Chiên TV
API_URL = "https://api.chuoichientv.net/v1/articles?page=1&limit=50"

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Ánh xạ emoji và tên nhóm bộ môn
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
    """Phân loại chính xác bộ môn thể thao"""
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
    """Làm sạch tên 2 đội, cắt bỏ các câu nhận định dài dòng"""
    # Lấy phần trước các dấu chia câu giật gân (:, –, -)
    clean_title = re.split(r'[:–\-]', title)[0].strip()
    
    if re.search(r'\bvs\b', clean_title, re.IGNORECASE):
        return clean_title
        
    # Bắt cụm 'Đội A vs Đội B' nếu tiêu đề nằm ở định dạng khác
    match = re.search(r'([A-Za-z0-9\s\.\p{L}]+?\s+vs\s+[A-Za-z0-9\s\.\p{L}]+)', title, re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    return clean_title

def extract_blv(content_html):
    """Trích xuất gọn tên BLV"""
    # Tìm dạng 'BLV trên Chuối Chiên TV: Chuối Ngao'
    match_full = re.search(r'BLV(?:[\s\wTV:\–\-]+)?:\s*([^\.\<\n]+)', content_html, re.IGNORECASE)
    if match_full:
        blv = match_full.group(1).strip()
        # Loại bỏ nếu trích xuất nhầm câu văn dài
        if len(blv) <= 20 and not any(bad in blv.lower() for bad in ["anh em", "theo dõi", "phân tích", "cộng đồng"]):
            return blv if blv.startswith("Chuối") else f"Chuối {blv}"
            
    # Tìm dạng 'BLV Chuối Ngao'
    match_short = re.search(r'\bBLV\s+([A-ZÀ-Ỹ][a-zà-ỹ0-9_]+)', content_html)
    if match_short:
        name = match_short.group(1)
        return name if name.startswith("Chuối") else f"Chuối {name}"
        
    return "Chuối TV"

def parse_article(item, now_vn):
    """Bóc tách chi tiết từng trận và kiểm tra điều kiện ngày"""
    title = item.get('title', '')
    content = item.get('content', '')
    tags = item.get('tags', [])
    soup = BeautifulSoup(content, 'html.parser')
    
    match_datetime = None
    time_display = ""
    date_display = ""
    
    # 1. Trích xuất thời gian & ngày thi đấu chính xác từ nội dung HTML
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

    # Nếu không tìm thấy trong nội dung, dùng ngày tạo bài viết
    if not match_datetime and item.get('createdAt'):
        try:
            created_utc = datetime.fromisoformat(item['createdAt'].replace('Z', '+00:00'))
            match_datetime = created_utc.astimezone(VN_TZ)
            time_display = match_datetime.strftime("%H:%M")
            date_display = match_datetime.strftime("%d/%m")
        except Exception:
            pass

    # LỌC NGÀY: Chỉ giữ lại trận Hôm nay và Ngày mai theo giờ VN
    today_vn = now_vn.date()
    tomorrow_vn = today_vn + timedelta(days=1)
    
    if match_datetime:
        match_date = match_datetime.date()
        if match_date < today_vn or match_date > tomorrow_vn:
            return None
    else:
        return None

    # 2. Xử lý tên đội, BLV, bộ môn
    teams_str = extract_clean_teams(title)
    blv = extract_blv(content)
    emoji, group_title = detect_sport(tags, title, content)
    
    # 3. Lấy Logo
    images = soup.find_all('img')
    logo = ""
    if images and 'src' in images[0].attrs:
        logo = images[0]['src']
    if not logo:
        logo = item.get('thumbnail', '')
        
    # 4. Tìm luồng stream (.m3u8 hoặc iframe)
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

def generate_m3u():
    # Giờ hiện tại theo múi giờ Việt Nam
    now_vn = datetime.now(timezone.utc).astimezone(VN_TZ)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://live08.chuoichientv.me/'
    }
    
    m3u_lines = ['#EXTM3U x-tvg-url=""']

    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Lỗi kết nối API: {e}")
        data = {}

    if data.get('success') and 'data' in data:
        articles = data['data']
        valid_count = 0
        
        for item in articles:
            try:
                parsed = parse_article(item, now_vn)
                if not parsed:
                    continue  # Bỏ qua các trận cũ hoặc không đúng điều kiện ngày
                    
                qualities = ["FHD", "HD1", "HD2"]
                for idx, stream_url in enumerate(parsed['streams']):
                    quality = qualities[idx] if idx < len(qualities) else f"HD{idx+1}"
                    
                    # Định dạng hiển thị chuẩn gọn gàng:
                    # 🟢 19:30 01/10 ⚽ Việt Nam vs Philippines (Chuối Ngao) [FHD] [hls]
                    display_name = f"🟢 {parsed['time']} {parsed['date']} {parsed['emoji']} {parsed['teams']} ({parsed['blv']}) [{quality}] [hls]"
                    
                    m3u_lines.append(
                        f'#EXTINF:-1 tvg-logo="{parsed["logo"]}" group-title="{parsed["group"]}",{display_name}\n{stream_url}'
                    )
                valid_count += 1
            except Exception as item_err:
                print(f"Bỏ qua bài viết lỗi ID {item.get('_id')}: {item_err}")
                continue
                
        print(f"Đã lọc thành công {valid_count} trận đấu hợp lệ cho hôm nay và ngày mai.")

    # Ghi file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

if __name__ == "__main__":
    generate_m3u()
    
