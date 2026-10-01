import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

# URL API của Chuối Chiên TV
API_URL = "https://api.chuoichientv.net/v1/articles?page=1&limit=50"

# Bảng ánh xạ bộ môn thể thao -> Emoji + Tên nhóm M3U
SPORT_MAP = {
    "bong-da": ("⚽", "Bóng Đá"),
    "bong-chuyen": ("🏐", "Bóng Chuyền"),
    "bong-ro": ("🏀", "Bóng Rổ"),
    "quan-vot": ("🎾", "Quần Vợt"),
    "cau-long": ("🏸", "Cầu Lông"),
    "vo-thuat": ("🥊", "Võ Thuật / MMA"),
    "dua-xe": ("🏎️", "Đua Xe")
}

def detect_sport(tags, title, content):
    """Phân loại bộ môn thể thao dựa trên tags và nội dung bài viết"""
    text_search = (str(tags) + " " + title + " " + content).lower()
    
    if "bóng chuyền" in text_search or "volleyball" in text_search:
        return SPORT_MAP["bong-chuyen"]
    elif "bóng rổ" in text_search or "basketball" in text_search or "nba" in text_search:
        return SPORT_MAP["bong-ro"]
    elif "quần vợt" in text_search or "tennis" in text_search:
        return SPORT_MAP["quan-vot"]
    elif "cầu lông" in text_search or "badminton" in text_search:
        return SPORT_MAP["cau-long"]
    elif "ufc" in text_search or "mma" in text_search or "boxing" in text_search:
        return SPORT_MAP["vo-thuat"]
    elif "f1" in text_search or "motogp" in text_search:
        return SPORT_MAP["dua-xe"]
    
    return SPORT_MAP["bong-da"]

def parse_content(content_html):
    """Bóc tách thông tin từ đoạn HTML trong trường content an toàn"""
    soup = BeautifulSoup(content_html, 'html.parser')
    
    time_str = ""
    date_str = ""
    
    # 1. Lấy thời gian & ngày an toàn
    p_time = soup.find('p')
    if p_time:
        match_time = re.search(r'(\d{1,2}:\d{2})\s+(\d{1,2}/\d{1,2}/\d{4})', p_time.text)
        if match_time:
            time_str = match_time.group(1)
            raw_date = match_time.group(2)
            try:
                dt = datetime.strptime(raw_date, "%d/%m/%Y")
                date_str = dt.strftime("%d/%m")
            except Exception:
                date_str = raw_date[:5]

    # 2. Lấy Logo 2 đội bóng
    images = soup.find_all('img')
    home_logo = ""
    away_logo = ""
    if len(images) > 0 and 'src' in images[0].attrs:
        home_logo = images[0]['src']
    if len(images) > 1 and 'src' in images[1].attrs:
        away_logo = images[1]['src']

    # 3. Lấy tên BLV
    blv_name = "Chuối TV"
    blv_match = re.search(r'BLV\s+([^\.\<]+)', content_html, re.IGNORECASE)
    if blv_match:
        blv_name = f"Chuối {blv_match.group(1).strip()}"

    # 4. Tìm link luồng phát hls (.m3u8) hoặc iframe stream
    stream_urls = re.findall(r'https?://[^\s\'"]+\.m3u8', content_html)
    if not stream_urls:
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            if 'src' in iframe.attrs and iframe['src'].startswith('http'):
                stream_urls.append(iframe['src'])

    return {
        'time': time_str,
        'date': date_str,
        'home_logo': home_logo,
        'away_logo': away_logo,
        'blv': blv_name,
        'streams': stream_urls
    }

def generate_m3u():
    # Cấu hình Headers giả lập trình duyệt chuẩn tránh bị chặn API
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://live08.chuoichientv.me/'
    }
    
    m3u_lines = ['#EXTM3U x-tvg-url=""']

    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Lỗi khi kết nối tới API: {e}")
        data = {}

    if data.get('success') and 'data' in data:
        articles = data['data']
        print(f"Lấy thành công {len(articles)} bài viết từ API.")
        
        for item in articles:
            # Xử lý cô lập từng bài viết, bài nào lỗi bỏ qua bài đó
            try:
                title = item.get('title', '')
                content = item.get('content', '')
                tags = item.get('tags', [])
                
                emoji, group_title = detect_sport(tags, title, content)
                details = parse_content(content)
                
                time_display = details['time'] if details['time'] else "LIVE"
                date_display = details['date'] if details['date'] else datetime.now().strftime("%d/%m")
                logo = details['home_logo'] if details['home_logo'] else item.get('thumbnail', '')
                blv = details['blv']
                
                # Tách tên 2 đội từ title
                match_teams = re.search(r'([^\-]+)\s+vs\s+([^\-]+)', title, re.IGNORECASE)
                if match_teams:
                    teams_str = f"{match_teams.group(1).strip()} vs {match_teams.group(2).strip()}"
                else:
                    teams_str = title.split('–')[0].strip()

                qualities = ["FHD", "HD1", "HD2"]
                
                if details['streams']:
                    for idx, stream_url in enumerate(details['streams']):
                        quality = qualities[idx] if idx < len(qualities) else f"HD{idx+1}"
                        display_name = f"🟢 {time_display} {date_display} {emoji} {teams_str} ({blv}) [{quality}] [hls]"
                        m3u_lines.append(
                            f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_title}",{display_name}\n{stream_url}'
                        )
                else:
                    article_slug = item.get('slug', '')
                    fallback_url = f"https://live08.chuoichientv.me/{article_slug}"
                    display_name = f"🟢 {time_display} {date_display} {emoji} {teams_str} ({blv}) [FHD] [hls]"
                    m3u_lines.append(
                        f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_title}",{display_name}\n{fallback_url}'
                    )
            except Exception as item_err:
                print(f"Lỗi bỏ qua bài viết ID {item.get('_id')}: {item_err}")
                continue
    else:
        print("API không trả về dữ liệu hoặc thuộc tính success=False")

    # Ghi file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Đã cập nhật xong file playlist.m3u với {len(m3u_lines) - 1} luồng phát.")

if __name__ == "__main__":
    generate_m3u()
    
