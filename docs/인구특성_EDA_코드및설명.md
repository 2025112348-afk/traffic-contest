# 인구 특성(이동취약계층) EDA — 코랩 코드 + 노션 설명 정리

담당: 지안 · 대상 변수: 고령인구비율 / 장애인인구비율 / 기초생활수급자비율
공간 단위: **시군구(229개)** · 시점: **2025년**으로 3개 데이터셋 통일 완료

---

## 0. 데이터 통일 작업 요약 (먼저 읽어주세요)

업로드해주신 3개 파일을 확인한 결과, 아래처럼 **서로 다른 원본 구조**를 갖고 있었고, 전부 시군구 단위·2025년 기준으로 통일해서 처리했습니다.

| 데이터 | 원본 출처 | 원본 해상도 | 비고 |
|---|---|---|---|
| 고령인구 (연령 및 성별 인구) | KOSIS, `DT_1IN1503` | 읍면동 단위 원자료 (71,940행) | 실제 `.xls`가 아니라 SpreadsheetML(XML)로 위장된 파일 |
| 장애인 인구 (장애유형별 장애인) | GSIS(여가부) | 시군구 단위 (246개 지역) | 이번에 새로 받아주신 파일은 시군구 단위가 맞음 ✅ |
| 기초생활수급자 (한국사회보장정보원) | 사회보장정보원 | 시군구 단위, 2025-12 기준 | 이미 시군구 단위였음 |

세 데이터셋 모두 **시군구 표기 방식이 제각각**이라(예: KOSIS는 "창원시"를 통합 표기, GSIS는 "통합창원시", 사회보장정보원은 "창원시"+"창원시의창구" 등을 따로 표기), 아래 코드에서 **공통 키(`sigungu`)로 표준화**한 뒤 병합했습니다. 실제로 코드를 돌려 세 데이터셋의 시군구 목록을 서로 대조해봤고, **229개 지역이 하나도 빠짐없이 완벽하게 일치**하는 것을 확인했습니다(교차 검증 결과, 세 데이터셋 간 불일치 지역 0개).

전국 총인구(51,817,499명), 전국 등록장애인 수(2,627,761명) 합계도 통계청 공표치와 정확히 일치하는 것을 재확인했습니다.

> 참고: 이 EDA는 지역별 인구 특성을 있는 그대로 살펴보는 탐색적 분석이라 **서울 포함 전체 229개 시군구**를 다 넣었습니다. 나중에 팀 전체의 "이동격차지수" 본계산 단계에서는 서론에서 정한 대로 서울을 제외하면 됩니다. (이 노트북 결과 자체를 지수 계산에 그대로 재사용해도, 서울 행만 걸러내면 됩니다.)

---

## 1. 코랩 셀: 공통 전처리 코드

아래 코드를 새 코랩 노트북에 순서대로 붙여넣으시면 됩니다. 파일 업로드는 `google.colab.files.upload()`로 3개 파일(`101_DT_1IN1503_....xls`, `장애유형별_장애인_...xlsx`, `...수급권자_현황....csv`)을 한 번에 올려주세요.

### 셀 1) 파일 업로드 + 폰트 설정

```python
from google.colab import files
uploaded = files.upload()  # 3개 파일 한꺼번에 선택해서 업로드

# 한글 폰트 설정
!apt-get -qq install fonts-nanum > /dev/null
import matplotlib.font_manager as fm
fontpath = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
fm.fontManager.addfont(fontpath)
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False

import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
```

### 셀 2) 시도/시군구 이름 표준화 공통 함수

```python
# ============================================================
# 공통: 시도/시군구 이름 표준화
# ============================================================
SIDO_NAMES = {
    '서울특별시','부산광역시','대구광역시','인천광역시','광주광역시','대전광역시','울산광역시',
    '세종특별자치시','경기도','강원특별자치도','충청북도','충청남도','전북특별자치도',
    '전라남도','경상북도','경상남도','제주특별자치도'
}
SIDO_ALIASES = {'강원도':'강원특별자치도','전라북도':'전북특별자치도'}
NON_REGION = {'전국','동부','읍부','면부'}
GU_HAVING_CITIES = {'수원시','성남시','안양시','안산시','고양시','용인시',
                     '청주시','천안시','전주시','포항시','창원시','부천시'}

def canonical_key(sido, sigungu):
    """3개 데이터셋 모두에서 동일하게 사용할 최종 조인 키.
       세종은 '시도=시군구'가 같은 특수 케이스라 '세종특별자치시' 하나로 고정."""
    if sido is None:
        return None
    if '세종' in sido:
        return '세종특별자치시'
    return f"{sido} {sigungu}"
```

### 셀 3) 고령인구비율 — KOSIS 원자료 로딩 함수

```python
# ============================================================
# 1) 고령인구 파일 (KOSIS, XML 위장 .xls, 읍면동 단위 원자료)
# ============================================================
def read_kosis_xml_xls(path):
    """KOSIS에서 받은 '.xls'가 실제로는 SpreadsheetML(엑셀 XML) 포맷이라
       pandas.read_excel로 못 엶 -> 직접 XML 파싱"""
    with open(path, 'rb') as f:
        raw = f.read()
    text = raw.decode('euc-kr', errors='replace').lstrip()
    text = text.replace('encoding="EUC-KR"', 'encoding="UTF-8"')
    # '메타정보' 시트에 이스케이프 안 된 '<' 문자가 있어 전체 파싱시 에러남 -> 데이터 시트까지만 자름
    idx = text.find('메타정보')
    if idx != -1:
        idx2 = text.rfind('<Worksheet', 0, idx)
        text = text[:idx2] + '</Workbook>'
    root = ET.fromstring(text)
    ns = '{urn:schemas-microsoft-com:office:spreadsheet}'
    rows_out = []
    for ws in root.findall(f'{ns}Worksheet'):
        table = ws.find(f'{ns}Table')
        if table is None:
            continue
        for row in table.findall(f'{ns}Row'):
            cells = []
            for cell in row.findall(f'{ns}Cell'):
                data = cell.find(f'{ns}Data')
                cells.append(data.text if data is not None else None)
            rows_out.append(cells)
    return rows_out


def build_sigungu_keys(raw_names):
    """KOSIS 형식: 한 열에 전국/동부·읍부·면부/시도/시군구/읍면동이 순서대로
       평평하게(계층 구분 없이) 나열되어 있음.
       ※ 동부/읍부/면부는 전국 밑뿐 아니라 각 시도 밑에도 반복 등장하므로,
          이걸 만나도 cur_sido를 리셋하지 않아야 함."""
    keys = []
    cur_sido = None
    skip_sub_gu = False
    for raw in raw_names:
        if pd.isna(raw):
            keys.append(None); continue
        name = str(raw).strip()
        if name in NON_REGION:
            keys.append(None); continue          # cur_sido는 유지
        canon = SIDO_ALIASES.get(name, name)
        if canon in SIDO_NAMES:
            cur_sido, skip_sub_gu = canon, False
            keys.append(None); continue           # 시도 총계행 자체는 제외
        if skip_sub_gu and name.endswith('구'):
            keys.append(None); continue           # 특례시 하위 구 -> 제외(중복 방지)
        skip_sub_gu = False
        if name.endswith(('시', '군', '구')):
            if name in GU_HAVING_CITIES:
                skip_sub_gu = True
            keys.append(canonical_key(cur_sido, name) if cur_sido else None)
            continue
        keys.append(None)                          # 읍면동 이하 상세행 -> 제외
    return keys


def load_age_sigungu(path):
    raw_rows = read_kosis_xml_xls(path)
    data_rows = [r for r in raw_rows[2:] if r and len(r) >= 5]
    long_df = pd.DataFrame(data_rows, columns=['행정구역_raw', '연령별', '항목', '단위', '2025'])
    long_df['2025'] = pd.to_numeric(long_df['2025'], errors='coerce')
    long_df['sigungu'] = build_sigungu_keys(long_df['행정구역_raw'])
    long_valid = long_df[long_df['sigungu'].notna()].copy()

    total_pop = (long_valid[(long_valid['연령별'] == '합계') & (long_valid['항목'] == '총인구(명)')]
                 .groupby('sigungu')['2025'].sum().reset_index(name='전체인구'))
    # KOSIS가 '65세이상' 합계를 이미 별도 행으로 제공하므로 직접 더할 필요 없음
    elderly = (long_valid[(long_valid['연령별'] == '65세이상') & (long_valid['항목'] == '총인구(명)')]
               .groupby('sigungu')['2025'].sum().reset_index(name='고령인구'))

    age_sigungu = total_pop.merge(elderly, on='sigungu', how='left')
    age_sigungu['고령인구비율'] = age_sigungu['고령인구'] / age_sigungu['전체인구']
    return age_sigungu

age_sigungu = load_age_sigungu(list(uploaded.keys())[0])  # 101_DT_1IN1503_....xls
print(age_sigungu.shape)          # (229, 4) 나와야 정상
print('전체인구 합:', age_sigungu['전체인구'].sum())   # 51,817,499 나와야 정상
age_sigungu.head()
```

**설명 (노션용 — 고령인구비율 데이터 처리)**

- 원본은 KOSIS 「연령 및 성별 인구(읍면동)」통계(`DT_1IN1503`)로, 실제 최소 행정단위인 읍면동 단위 71,940행짜리 원자료입니다. 파일 확장자는 `.xls`이지만 실제로는 SpreadsheetML(엑셀 XML) 포맷이라 `pandas.read_excel`로 열리지 않아 XML을 직접 파싱했습니다.
- 지역 표기가 "전국 → 동/읍/면부 → 17개 시도 → 시군구 → 읍면동"이 한 열에 계층 구분 없이 순서대로 나열되는 구조라, 현재 읽고 있는 행이 시도인지 시군구인지 읍면동인지를 상태값(state)으로 추적하는 파서(`build_sigungu_keys`)를 만들어 처리했습니다.
- 수원시·성남시·안양시·안산시·고양시·용인시·청주시·천안시·전주시·포항시·창원시·부천시(특례시/구가 있는 12개 시)는 "시 합계 행" 하나가 이미 전체 합계이고, 그 아래 "구" 행은 시 합계에 포함된 하위 항목이라 이중집계를 막기 위해 구 행은 제외했습니다.
- 고령인구는 KOSIS가 이미 '65세이상' 합계를 별도 행으로 제공해서, 65~69세부터 100세이상까지 일일이 더할 필요 없이 그 행을 바로 사용했습니다.
- **검증**: 처리 후 229개 시군구, 전체인구 합계 51,817,499명으로 통계청 공표 전국 인구와 정확히 일치함을 확인했습니다.

---

### 셀 4) 장애인인구비율 — GSIS 원자료 로딩 함수

```python
# ============================================================
# 2) 장애인 파일 (GSIS, 시군구 단위, 들여쓰기로 시도-시군구 계층 표시)
# ============================================================
GSIS_SIDO_PREFIX_MAP = {
    '부산': '부산광역시', '대구': '대구광역시', '인천': '인천광역시',
    '광주': '광주광역시', '대전': '대전광역시', '울산': '울산광역시',
    '경남': '경상남도',
}

def parse_gsis_region(raw_name, cur_sido):
    """GSIS 표시명 하나를 (갱신된 cur_sido, 시군구 key)로 변환.
       - 들여쓰기 없는 이름  -> 시도 헤더행
       - 들여쓰기 있는 이름  -> 시군구행 (동명이인 방지용 '시도약칭-' 접두어 제거,
         예: '부산-중구' -> '중구', '경남-고성군' -> '고성군')
       - '통합창원시'        -> '창원시'로 정규화 (이 파일은 창원시를 구 분리 없이 통합 표기)"""
    if raw_name is None:
        return cur_sido, None
    raw = str(raw_name)
    stripped = raw.strip()
    if stripped == '':
        return cur_sido, None
    is_indented = raw != stripped
    name = stripped
    if not is_indented:
        canon = SIDO_ALIASES.get(name, name)
        if canon in SIDO_NAMES:
            return canon, None
        return cur_sido, None
    for prefix, full_sido in GSIS_SIDO_PREFIX_MAP.items():
        if name.startswith(prefix + '-'):
            name = name[len(prefix) + 1:]
            break
    if name == '통합창원시':
        name = '창원시'
    return cur_sido, canonical_key(cur_sido, name)


def load_disability_sigungu(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb['데이터']
    rows = list(ws.iter_rows(values_only=True))
    data_rows = rows[2:]  # 상위 2행은 헤더

    keys, total_disabled = [], []
    cur_sido, cur_key = None, None
    for r in data_rows:
        region_raw, item, total_col = r[0], r[1], r[2]
        if region_raw is not None and str(region_raw).strip() != '':
            cur_sido, cur_key = parse_gsis_region(region_raw, cur_sido)
        if cur_key is None:
            continue
        if item == '총계':          # 지체/시각/청각 등 유형별 중복 없이 '총계' 행만 사용
            keys.append(cur_key)
            total_disabled.append(total_col)

    disability_sigungu = pd.DataFrame({'sigungu': keys, '장애인수': total_disabled})
    disability_sigungu['장애인수'] = pd.to_numeric(disability_sigungu['장애인수'], errors='coerce')
    disability_sigungu = disability_sigungu.groupby('sigungu', as_index=False)['장애인수'].sum()
    return disability_sigungu

disability_sigungu = load_disability_sigungu(list(uploaded.keys())[1])  # 장애유형별_..._시군구별.xlsx
print(disability_sigungu.shape)          # (229, 2) 나와야 정상
print('장애인수 합:', disability_sigungu['장애인수'].sum())   # 2,627,761 나와야 정상
disability_sigungu.head()
```

**설명 (노션용 — 장애인인구비율 데이터 처리)**

- 원본은 GSIS(여성가족부 통계, `DT_2GC0111N`) 「장애유형별 장애인(성/시군구별)」 통계이며, 이번에 다시 받아주신 파일은 처음 업로드했던 파일(시도 단위 18개 지역)과 달리 **실제로 시군구 단위(246개 지역)**로 잘 받아진 파일이었습니다.
- 이 파일은 시도명은 들여쓰기 없이, 시군구명은 앞에 전각공백(들여쓰기)을 붙여 계층을 표현합니다. 또한 "중구/동구/서구/남구/북구/고성군"처럼 여러 시도에 동시에 존재하는 지명은 "부산-중구", "대구-동구", "경남-고성군"처럼 시도 약칭을 접두어로 붙여 동명이인을 구분해뒀습니다. → 파싱할 때 이 접두어를 제거하고 실제 소속 시도와 다시 결합했습니다.
- 창원시는 이 데이터에서는 "통합창원시"라는 이름으로 구 분리 없이 이미 하나의 행으로 합쳐져 있어서 별도 합산 작업 없이 이름만 "창원시"로 통일했습니다.
- 장애유형은 지체/시각/청각/언어/지적/뇌병변/자폐 등 10여 개로 나뉘는데, 이는 한 사람이 하나의 유형에만 속하는 상호배타적 분류라 유형별로 합산해도 되지만, 데이터에 이미 제공되는 **'총계' 행**을 그대로 사용했습니다.
- **검증**: 처리 후 229개 시군구, 전체 등록장애인 수 합계 2,627,761명으로 공표치와 정확히 일치, 그리고 앞서 만든 고령인구 데이터의 229개 시군구 목록과 **완전히 동일**함을 확인했습니다.

---

### 셀 5) 기초생활수급자비율 — 사회보장정보원 CSV 로딩 함수

```python
# ============================================================
# 3) 기초생활수급자 CSV (시도/시군구 분리 컬럼, 특례시=구 합산 필요)
# ============================================================
def load_welfare_sigungu(path):
    for enc in ['utf-8-sig', 'cp949', 'euc-kr']:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    # 기초생계/의료/주거/교육급여는 서로 중복(한 수급자가 여러 급여를 동시 수급) 되므로
    # 합산하지 않고, 헤드라인 집계 항목인 '기초생활보장(맞춤형급여)' 하나만 사용
    target = df[df['사업명'] == '기초생활보장(맞춤형급여)'].copy()

    def normalize_city(sigungu):
        """이 CSV는 KOSIS와 반대로 특례시 합계 행이 '잔여치'이고,
           시 전체 합계를 구하려면 시 행 + 하위 구 행들을 모두 더해야 함
           (예: 창원시 146 + 창원시의창구 12029 + ... = 창원시 전체 53,779).
           -> 시-구 이름을 전부 상위 '시' 이름으로 묶은 뒤 groupby에서 합산."""
        s = str(sigungu).strip()
        for city in GU_HAVING_CITIES:
            if s.startswith(city):
                return city
        return s

    target['sido_norm'] = target['시도'].apply(lambda x: SIDO_ALIASES.get(str(x).strip(), str(x).strip()))
    target['sigungu_norm'] = target['시군구'].apply(normalize_city)
    target['sigungu'] = target.apply(lambda r: canonical_key(r['sido_norm'], r['sigungu_norm']), axis=1)

    welfare_sigungu = (target.groupby('sigungu', as_index=False)
                        .agg(기초생활수급자수=('수급권자수', 'sum')))
    return welfare_sigungu

welfare_sigungu = load_welfare_sigungu(list(uploaded.keys())[2])  # ...수급권자_현황....csv
print(welfare_sigungu.shape)   # (229, 2) 나와야 정상
welfare_sigungu.head()
```

**설명 (노션용 — 기초생활수급자비율 데이터 처리)**

- 원본은 한국사회보장정보원 「복지사업별 시군구별 수급권자 현황」으로, 기준월 2025-12(2025년 기준으로 이미 통일되어 있음) 자료입니다.
- 이 CSV의 사업명은 10종류(기초생활보장/기초생계급여/기초의료급여/기초주거급여/기초교육급여/차상위장애인/차상위자활/차상위본인부담경감/기초연금/장애인연금)인데, 이 중 **기초생계·의료·주거·교육급여 4종은 '기초생활보장(맞춤형급여)'의 세부 급여 유형별 중복 집계**입니다(한 수급자가 여러 급여를 동시에 받을 수 있음). 따라서 이 4종을 따로 더하지 않고, 중복 없는 헤드라인 수치인 **'기초생활보장(맞춤형급여)'** 한 항목만 "기초생활수급자수"로 사용했습니다.
- **중요한 구조적 특이사항**: 이 데이터는 특례시(창원·수원·성남·안양·부천·안산·고양·용인·청주·천안·전주·포항)의 "시" 행이 KOSIS와 반대로 **전체 합계가 아니라 일부만 담긴 잔여값**이고, 시 전체 수급자 수를 구하려면 시 행과 그 아래 구 행들을 **모두 더해야** 합니다. (예: 창원시 146명 + 창원시의창구 12,029명 + 창원시성산구 6,418명 + 창원시마산합포구 12,659명 + 창원시마산회원구 11,596명 + 창원시진해구 10,931명 = 창원시 전체 53,779명). 실제 코드에서 이 합산까지 정확히 반영해서 검증했습니다.
- **검증**: 처리 후 229개 시군구로, 앞의 두 데이터셋과 시군구 목록이 완전히 일치함을 확인했습니다.

---

## 2. 코랩 셀: 3개 데이터 병합 + 비율 계산

```python
# 시군구 키 기준으로 3개 데이터셋 병합 (교차검증: 아래에서 불일치 지역이 있는지 확인)
age_keys = set(age_sigungu['sigungu'])
dis_keys = set(disability_sigungu['sigungu'])
wel_keys = set(welfare_sigungu['sigungu'])
print('고령-장애인 불일치:', (age_keys - dis_keys) | (dis_keys - age_keys))
print('고령-수급자 불일치:', (age_keys - wel_keys) | (wel_keys - age_keys))
# -> 둘 다 빈 set()이 나와야 정상 (229개 지역 완전 일치)

merged = (age_sigungu
          .merge(disability_sigungu, on='sigungu', how='inner')
          .merge(welfare_sigungu, on='sigungu', how='inner'))

merged['장애인인구비율'] = merged['장애인수'] / merged['전체인구']
merged['기초생활수급자비율'] = merged['기초생활수급자수'] / merged['전체인구']

merged[['시도', '시군구']] = merged['sigungu'].str.split(' ', n=1, expand=True)
merged.loc[merged['sigungu'] == '세종특별자치시', ['시도', '시군구']] = ['세종특별자치시', '세종특별자치시']

print(merged.shape)  # (229, 10)
merged.to_csv('인구특성_시군구_2025.csv', index=False, encoding='utf-8-sig')
merged.describe()
```

---

## 3. 코랩 셀: 시각화 (분석별 상위/하위 지역 + 분포)

```python
def plot_ratio(df, col, title, color):
    top = df.nlargest(15, col).sort_values(col)
    bottom = df.nsmallest(15, col).sort_values(col, ascending=False)

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # (1) 상위 15개 지역
    axes[0].barh(top['sigungu'], top[col], color=color)
    axes[0].set_title(f'{title} 상위 15개 지역')
    axes[0].set_xlabel(title)

    # (2) 하위 15개 지역
    axes[1].barh(bottom['sigungu'], bottom[col], color='lightgray')
    axes[1].set_title(f'{title} 하위 15개 지역')
    axes[1].set_xlabel(title)

    # (3) 전체 분포 히스토그램
    axes[2].hist(df[col], bins=25, color=color, edgecolor='white')
    axes[2].axvline(df[col].mean(), color='red', linestyle='--', label=f'평균 {df[col].mean():.1%}')
    axes[2].set_title(f'{title} 분포 (전국 229개 시군구)')
    axes[2].legend()

    plt.tight_layout()
    plt.savefig(f'{title}.png', dpi=150, bbox_inches='tight')
    plt.show()

plot_ratio(merged, '고령인구비율', '고령인구비율', '#4C72B0')
plot_ratio(merged, '장애인인구비율', '장애인인구비율', '#DD8452')
plot_ratio(merged, '기초생활수급자비율', '기초생활수급자비율', '#55A868')
```

```python
# 시도별 평균 비교 (수도권 vs 비수도권, 도시 vs 농촌 맥락 파악용)
sido_avg = merged.groupby('시도')[['고령인구비율', '장애인인구비율', '기초생활수급자비율']].mean()
sido_avg = sido_avg.sort_values('고령인구비율', ascending=True)

fig, ax = plt.subplots(figsize=(10, 8))
sido_avg.plot(kind='barh', ax=ax)
ax.set_title('시도별 평균 인구특성 지표 비교')
ax.set_xlabel('비율')
plt.tight_layout()
plt.savefig('시도별_평균비교.png', dpi=150, bbox_inches='tight')
plt.show()
```

```python
# 3개 지표 간 상관관계 (index 가중치 설계에 참고용 — 아래 설명 참고)
import seaborn as sns
corr = merged[['고령인구비율', '장애인인구비율', '기초생활수급자비율']].corr()
plt.figure(figsize=(5, 4))
sns.heatmap(corr, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
plt.title('인구특성 3개 지표 간 상관관계')
plt.tight_layout()
plt.savefig('상관관계.png', dpi=150, bbox_inches='tight')
plt.show()
```

### (선택) 지도 기반 시각화 — 코로플레스 맵

막대그래프 대신/추가로 지도에 표현하고 싶으시면 아래처럼 `folium` + 공개 시군구 경계 GeoJSON을 사용하시면 됩니다. (코랩은 인터넷이 열려 있어서 다운로드가 되지만, 이 GeoJSON은 제가 직접 열어서 검증은 못 했으니 실행해보시고 지역명이 매칭이 안 되면 아래 `alias` 딕셔너리에 추가해서 보정해주세요. 안 되면 위 막대그래프만으로도 충분합니다.)

```python
import folium
import requests
import json

geo_url = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_municipalities_geo_simple.json"
geo_json = requests.get(geo_url).json()

# geojson 속성명은 실행 후 아래로 확인
print(geo_json['features'][0]['properties'])

m = folium.Map(location=[36.5, 127.8], zoom_start=7, tiles='cartodbpositron')
folium.Choropleth(
    geo_data=geo_json,
    data=merged,
    columns=['시군구', '고령인구비율'],   # geojson 속성명에 맞춰 columns[0]을 조정하세요
    key_on='feature.properties.name',      # geojson 속성명 확인 후 수정
    fill_color='YlOrRd',
    legend_name='고령인구비율',
).add_to(m)
m
```

---

## 4. 노션 정리용 종합 설명

### 분석 개요
- **분석 대상**: 전국 229개 시군구 (2025년 기준)
- **분석 변수**: 고령인구비율(65세 이상 / 전체인구), 장애인인구비율(등록장애인 / 전체인구), 기초생활수급자비율(맞춤형급여 수급권자 / 전체인구)
- **목적**: 이동취약계층(고령·장애·경제적 취약) 인구가 지역별로 어떻게 분포하는지 파악하여, 이동격차지수의 "인구특성" 축 설계 근거를 마련

### 주요 결과
- **고령인구비율**이 가장 높은 지역은 경북 의성군(48.6%), 대구 군위군(47.5%), 경남 합천군(45.8%), 전남 고흥군(45.2%), 경북 봉화군(44.4%)으로 모두 전형적인 농산어촌 초고령 지역입니다. 반대로 가장 낮은 지역은 경기 화성시(11.1%), 세종시(11.8%), 광주 광산구(12.9%) 등 신도시·산업단지형 지역입니다.
- **장애인인구비율**도 전북 임실군(12.5%), 경북 의성군(12.5%), 대구 군위군(12.0%) 등 고령인구비율 상위 지역과 거의 겹칩니다. 반대로 서울 서초구(2.6%), 서울 강남구(3.0%), 경기 과천시(3.1%)가 가장 낮습니다.
- **기초생활수급자비율**은 다른 양상을 보입니다 — 부산 영도구(13.5%), 부산 중구(13.3%), 부산 동구(13.2%), 대구 남구(12.5%), 대구 서구(11.6%)처럼 **원도심 노후 지역**이 상위권입니다. 이는 지난번 DRT 스크리닝 EDA에서 나왔던 "원도심 노후구" 유형과 정확히 일치하는 패턴입니다.
- **가장 낮은 지역**은 경기 과천시(1.8%), 서울 서초구(2.2%), 경기 화성시(2.2%)로, 고령/장애 비율이 낮은 지역과 대체로 겹칩니다.

### ⚠️ 가중치 설계 시 꼭 감안해야 할 점 — 변수 간 상관관계
세 지표 간 상관관계를 확인해보니:

| | 고령인구비율 | 장애인인구비율 | 기초생활수급자비율 |
|---|---|---|---|
| 고령인구비율 | 1.00 | **0.95** | 0.55 |
| 장애인인구비율 | 0.95 | 1.00 | 0.57 |
| 기초생활수급자비율 | 0.55 | 0.57 | 1.00 |

**고령인구비율과 장애인인구비율의 상관계수가 0.95로 거의 완벽하게 겹칩니다.** 이는 등록장애인 중 다수가 노년층(지체·뇌병변 등 노화 관련 장애)이기 때문에 나타나는 자연스러운 현상이지만, 이동격차지수 계산 시 두 변수를 각각 독립적인 가중치로 그대로 넣으면 사실상 "고령 농촌형 인구구조"라는 같은 신호를 두 번 반영하는 셈이 되어 해당 축의 영향력이 부풀려질 위험이 있습니다.

**제안**: (1) 두 변수를 하나의 하위 지표로 합치거나(예: 평균 또는 주성분분석), (2) 엔트로피 가중치법을 적용할 때 이 상관관계를 인지하고 사후에 보정하거나, (3) 장애인인구비율은 상관관계가 낮은 다른 축(예: 접근성)의 세부 변수로 재배치하는 방안을 팀 논의에서 검토해보면 좋을 것 같습니다. 기초생활수급자비율은 상대적으로 독립적인 신호(도시 내 경제적 취약지역 포착)를 담고 있어 그대로 유지해도 될 것 같습니다.

### 데이터 출처
- 고령인구: KOSIS, 「연령 및 성별 인구(읍면동)」, `DT_1IN1503`, 2025년
- 장애인 인구: GSIS(여성가족부 통계), 「장애유형별 장애인(성/시군구별)」, `DT_2GC0111N`, 2025년
- 기초생활수급자: 한국사회보장정보원, 「복지사업별 시군구별 수급권자 현황」, 2025년 12월 기준

### 데이터 처리 방법 요약
1. 세 데이터셋 모두 시군구 단위·2025년 기준으로 통일
2. 시도별 특례시(창원·수원·성남 등 12개 시)의 구 단위 하위행은 데이터셋마다 합산 방향이 반대라 각각 다르게 처리 (KOSIS·GSIS는 시 합계 행 그대로 사용, 사회보장정보원 CSV는 시+구 행을 모두 합산)
3. 복지급여 데이터는 중복 수급 가능한 세부 급여 유형을 빼고 헤드라인 집계('기초생활보장 맞춤형급여')만 사용
4. 표준화된 "시도 시군구" 키로 병합, 229개 지역 완전 일치 검증 완료
