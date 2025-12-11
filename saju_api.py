import json
from datetime import datetime, timedelta

# [여기에 추가] Flask에 필요한 모듈을 불러옵니다.
from flask import Flask, request, jsonify 
from flask_cors import CORS
# ==============================================================
# 1. 상수 정의
# ==============================================================
# 60갑자 표 (사장님께서 확인하신 정확한 순서, 60개 원소)
GANJI_60 = [
    "甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", # 1~10
    "甲戌", "乙亥", "丙子", "丁丑", "戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未", # 11~20
    "甲申", "乙酉", "丙戌", "丁亥", "戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳", # 21~30
    "甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑", "壬寅", "癸卯", # 31~40
    "甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑", # 41~50
    "甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥"  # 51~60
]

# 천간/지지 목록 (인덱스 계산용)
GANS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
JIS = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# 12절기 순서 (월주 계산 시 기준, 입춘=0, 인월 시작)
SOLAR_TERMS_ORDER = [
    "입춘", "경칩", "청명", "입하", "망종", "소서", 
    "입추", "백로", "한로", "입동", "대설", "소한"
]

# 월건표: 년주 천간에 따른 인월(寅月)의 천간 결정
MONTH_PILLAR_START_GAN = {
    '甲': '丙', '乙': '戊', '丙': '庚', '丁': '壬', '戊': '甲',
    '己': '丙', '庚': '戊', '辛': '庚', '壬': '壬', '癸': '甲'
}

# 시두표: 일주 천간에 따른 子시의 천간 결정
HOUR_PILLAR_START_GAN = {
    '甲': '甲', '乙': '丙', '丙': '戊', '丁': '庚', '戊': '壬',
    '己': '甲', '庚': '丙', '辛': '戊', '壬': '庚', '癸': '壬'
}

# 한국 서머타임(Daylight Saving Time) 시행 기간 정의 (시작일, 종료일)
KST_DST_PERIODS = [
    (datetime(1948, 6, 1, 0, 0), datetime(1948, 9, 13, 0, 0)),
    (datetime(1949, 4, 1, 0, 0), datetime(1949, 9, 11, 0, 0)),
    (datetime(1950, 4, 1, 0, 0), datetime(1950, 9, 11, 0, 0)),
    (datetime(1951, 5, 6, 0, 0), datetime(1951, 9, 9, 0, 0)),
    (datetime(1955, 5, 5, 0, 0), datetime(1955, 9, 11, 0, 0)),
    (datetime(1956, 5, 20, 0, 0), datetime(1956, 9, 30, 0, 0)),
    (datetime(1957, 5, 6, 0, 0), datetime(1957, 9, 29, 0, 0)),
    (datetime(1958, 5, 4, 0, 0), datetime(1958, 9, 28, 0, 0)),
    (datetime(1959, 5, 3, 0, 0), datetime(1959, 9, 20, 0, 0)),
    (datetime(1960, 5, 1, 0, 0), datetime(1960, 9, 18, 0, 0)),
    (datetime(1987, 5, 10, 2, 0), datetime(1987, 10, 11, 3, 0)),
    (datetime(1988, 5, 8, 2, 0), datetime(1988, 10, 9, 3, 0)),
]

def load_solar_terms_db(filename='solar_terms_db.json'):
    """절입시 JSON 파일을 불러와 메모리에 로드하는 함수"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            raw_db = json.load(f)
            solar_terms_db = {}
            for dt_str, term_name in raw_db.items():
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                solar_terms_db[dt_obj] = term_name
            print(f"✅ 절입시 DB 로딩 완료. 총 {len(solar_terms_db)}개 데이터.")
            return solar_terms_db
    except FileNotFoundError:
        print(f"🚨 오류: '{filename}' 파일을 찾을 수 없습니다.")
        return None
    except json.JSONDecodeError as e:
        print(f"🚨 오류: '{filename}' 파일의 JSON 형식이 잘못되었습니다.")
        return None

# ==============================================================
# 2. 년주(年柱) 계산 로직
# ==============================================================
def find_last_ipchun(birth_datetime, db):
    """주어진 생년월일시 이전에 가장 가까운 '입춘(立春)' 절입시를 찾는 함수"""
    last_ipchun_dt = None
    sorted_db_keys = sorted(db.keys())
    
    for dt_obj in sorted_db_keys:
        term_name = db[dt_obj]
        if term_name == "입춘" and dt_obj <= birth_datetime:
            last_ipchun_dt = dt_obj
        if dt_obj > birth_datetime:
            break
            
    return last_ipchun_dt

def calculate_year_pillar(birth_datetime, db):
    """주어진 생년월일시를 기준으로 년주(年柱)를 계산하는 함수"""
    
    last_ipchun_dt = find_last_ipchun(birth_datetime, db)
    
    if not last_ipchun_dt:
        return f"데이터 부족: {birth_datetime.year}년 직전의 입춘 정보를 찾을 수 없습니다."

    ipchun_year = last_ipchun_dt.year 
    
    # 60갑자 인덱스 계산 (1900년 庚子(36) 기준)
    START_YEAR = 1900
    START_INDEX = 36 
    
    ganji_index = (START_INDEX + (ipchun_year - START_YEAR)) % 60
    year_ganji = GANJI_60[ganji_index]
    
    print(f"> [디버그: 년주] 마지막 입춘: {last_ipchun_dt.strftime('%Y-%m-%d %H:%M')}, 해당 년주: {year_ganji}")

    return year_ganji


# ==============================================================
# 3. 월주(月柱) 계산 로직
# ==============================================================
def calculate_month_pillar(birth_datetime, year_ganji, db):
    """주어진 생년월일시와 해당 년주를 기준으로 월주(月柱)를 계산하는 함수"""
    
    last_term_dt = None
    last_term_name = None
    sorted_db_keys = sorted(db.keys())
    
    # 1. 생일 직전의 절기(節氣)를 찾습니다.
    for dt_obj in sorted_db_keys:
        term_name = db[dt_obj]
        if term_name in SOLAR_TERMS_ORDER and dt_obj <= birth_datetime:
            last_term_dt = dt_obj
            last_term_name = term_name
        if dt_obj > birth_datetime:
            break
            
    if not last_term_name:
        return "데이터 부족: 월주 계산을 위한 절기 정보를 찾을 수 없습니다."

    # 2. 절기 이름으로 인월(寅月) 기준 인덱스를 찾습니다. (입춘=0)
    month_index_offset = SOLAR_TERMS_ORDER.index(last_term_name) 

    # 3. 월건표를 이용해 시작 천간(인월 천간)을 찾습니다.
    year_gan = year_ganji[0] 
    start_gan = MONTH_PILLAR_START_GAN[year_gan] 

    # 4. 월 천간/지지를 계산합니다.
    start_gan_index = GANS.index(start_gan)
    month_gan_index = (start_gan_index + month_index_offset) % 10
    month_gan = GANS[month_gan_index]
    
    # 월 지지 인덱스 (寅(2)부터 시작)
    month_ji_index = (2 + month_index_offset) % 12
    month_ji = JIS[month_ji_index]
    
    month_ganji = month_gan + month_ji
    
    print(f"> [디버그: 월주] 마지막 절기: {last_term_dt.strftime('%Y-%m-%d %H:%M')} ({last_term_name}), 월주: {month_ganji}")
    
    return month_ganji


# ==============================================================
# 4. 일주(日柱) 계산 로직
# ==============================================================

# 기준일(Epoch Day) 설정: 1900년 1월 1일은 丙子 일(日)입니다.
EPOCH_DATE = datetime(1900, 1, 1)
EPOCH_GANJI_INDEX = 10 # 1900년 1월 1일은 甲戌 일(日) (인덱스 10)

def calculate_day_pillar(birth_datetime):
    """
    주어진 생년월일을 기준으로 일주(日柱)를 계산하는 함수
    """
    
    # 1. 기준일(1900-01-01)로부터 생일까지의 일수 차이 계산
    time_difference = birth_datetime.date() - EPOCH_DATE.date()
    day_count = time_difference.days
    
    # 2. 일수 차이를 60으로 나눈 나머지로 인덱스를 계산
    day_ganji_index = (EPOCH_GANJI_INDEX + day_count) % 60
    
    day_ganji = GANJI_60[day_ganji_index]
    
    print(f"> [디버그: 일주] 기준일로부터 {day_count}일 경과, 일주: {day_ganji}")
    
    return day_ganji


# ==============================================================
# 5. 시주(時柱) 계산 로직 (DST 보정 포함)
# ==============================================================
def calculate_hour_pillar(birth_datetime, day_ganji):
    """
    주어진 생시와 일주를 기준으로 시주(時柱)를 계산하는 함수
    """
    
    # 1. 서머타임(DST) 보정
    kst_datetime = birth_datetime
    is_dst_applied = False

    for start_dt, end_dt in KST_DST_PERIODS:
        if start_dt <= birth_datetime < end_dt:
            # DST 기간 내에 있다면 1시간을 뺌 (한국 DST는 KST+1 이었음)
            kst_datetime = birth_datetime - timedelta(hours=1)
            is_dst_applied = True
            break
            
    # 2. 보정된 KST 시간으로 時 인덱스 찾기
    
    # 시반분(時半) 기준: 30분을 빼서 해당 시를 기준으로 만듦
    corrected_hour_dt = kst_datetime - timedelta(minutes=30)
    current_hour = corrected_hour_dt.hour
    
   # 0=자시(23:30~01:30, index 0), 1=축시, ... 순서로 정확하게 매핑
    hour_index = ((current_hour + 1) % 24) // 2
    
    # 3. 시두표를 이용해 시작 천간(子시 천간)을 찾습니다.
    day_gan = day_ganji[0] 
    start_gan = HOUR_PILLAR_START_GAN.get(day_gan)
    
    if not start_gan:
        return "시주 계산 오류: 일주 천간을 찾을 수 없습니다."

    # 4. 시 천간/지지를 계산합니다.
    hour_ji = JIS[hour_index] # 0=子, 1=丑, ..., 11=亥

    # 시 천간 인덱스
    start_gan_index = GANS.index(start_gan)
    hour_gan_index = (start_gan_index + hour_index) % 10
    hour_gan = GANS[hour_gan_index]
    
    hour_ganji = hour_gan + hour_ji
    
    print(f"> [디버그: 시주] DST 보정: {is_dst_applied}, KST 시각: {kst_datetime.strftime('%Y-%m-%d %H:%M')}, 시주: {hour_ganji}")
    
    return hour_ganji


# ==============================================================
# 6. 메인 실행 함수
# ==============================================================
def calculate_manse(birth_date, birth_time):
    """
    사주 명조를 계산하는 메인 함수
    """
    db = load_solar_terms_db()
    if not db:
        return "계산 실패: 절입시 데이터베이스를 로드할 수 없습니다."

    # 입력값을 datetime 객체로 통합
    if isinstance(birth_date, str):
        full_dt_str = f"{birth_date} {birth_time}"
        birth_datetime = datetime.strptime(full_dt_str, "%Y-%m-%d %H:%M")
    else:
        birth_datetime = birth_date.replace(hour=int(birth_time.split(':')[0]), 
                                            minute=int(birth_time.split(':')[1]))
    
    # ----------------------------------------------------------
    # 1. 년주 계산 
    # ----------------------------------------------------------
    year_ganji = calculate_year_pillar(birth_datetime, db)
    
    # ----------------------------------------------------------
    # 2. 월주 계산
    # ----------------------------------------------------------
    if "데이터 부족" in year_ganji:
        month_ganji = "계산 불가"
    else:
        month_ganji = calculate_month_pillar(birth_datetime, year_ganji, db)
    
    # ----------------------------------------------------------
    # 3. 일주 계산
    # ----------------------------------------------------------
    day_ganji = calculate_day_pillar(birth_datetime) 
    
    # ----------------------------------------------------------
    # 4. 시주 계산 
    # ----------------------------------------------------------
    hour_ganji = calculate_hour_pillar(birth_datetime, day_ganji)
    
    # 함수 본문과 동일한 4칸 들여쓰기 (스페이스 4칸 또는 탭 1개)
    return {
        "year_pillar": year_ganji,
        "month_pillar": month_ganji,
        "day_pillar": day_ganji,
        "hour_pillar": hour_ganji
    }

# [수정 후] 메인 실행 블록 (Flask API 서버 시작 - 삭제한 자리에 대체)
# ==============================================================================

# 필요한 Flask 모듈을 파일 맨 위에서 불러왔다면 이 두 줄은 주석 처리하거나 지워도 됩니다.
# from flask import Flask, request, jsonify 

app = Flask(__name__)
CORS(app)

# 서버 시작 시 DB를 한 번만 로드합니다. (load_solar_terms_db 함수는 파일 안에 이미 정의되어 있음)
solar_terms_db = load_solar_terms_db("solar_terms_db.json")

# 웹사이트가 호출할 API 엔드포인트 정의
@app.route('/calculate', methods=['GET'])
def calculate_saju_api():
    # DB가 로딩되지 않았을 경우 (파일 없음)
    if solar_terms_db is None:
        return jsonify({"error": "사주 DB 로딩에 실패했습니다. solar_terms_db.json 파일이 같은 폴더에 있는지 확인해주세요."}), 500

    # 쿼리 파라미터에서 날짜와 시간을 가져옵니다. (예: /calculate?date=2000-09-22&time=16:12)
    date_input = request.args.get('date')
    time_input = request.args.get('time')

    if not date_input or not time_input:
        return jsonify({"error": "날짜(date)와 시간(time) 파라미터를 모두 입력해야 합니다."}), 400

    try:
        # 사주 로직 실행 (calculate_manse 함수는 파일 안에 이미 정의되어 있음)
        result = calculate_manse(date_input, time_input) 
        
        # 시주-일주-월주-년주 순서로 재정렬하여 반환
        output = {
            "天干": [result['hour_pillar'][0], result['day_pillar'][0], result['month_pillar'][0], result['year_pillar'][0]],
            "地支": [result['hour_pillar'][1], result['day_pillar'][1], result['month_pillar'][1], result['year_pillar'][1]]
        }
        
        return jsonify(output)

    except Exception as e:
        # 계산 중 오류 발생 시 사용자에게 에러 메시지를 전달
        return jsonify({"error": "계산 중 오류가 발생했습니다.", "details": str(e)}), 500

if __name__ == '__main__':
    # 서버 실행 (개발 모드, 포트 5000)
    app.run(debug=True, port=5000)