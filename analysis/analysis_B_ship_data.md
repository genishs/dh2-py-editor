# horiedit 분석 — B 파트 (선박/함대/항구 데이터)

> 분석 대상:
> - `D:\Documents\workspace\study\koukai2_edit\originalgame\koukai2\HORIEDIT.C`
> - `D:\Documents\workspace\study\koukai2_edit\originalgame\koukai2\HORIEDIT.H`
>
> 진입점: `select_menu()` (HORIEDIT.C:652~675) 의 case 3 → `hero_ship_edit()`, case 4 → `org_ship_edit()`. select_menu / sel_save / init_hori / conferm_hero 등 외곽 흐름은 **분석가 A 명세 참조**.

---

## 1. 개요

### 1-1. 편집 대상 파일
프로그램은 `koukai2.dat` 한 파일을 r+b 모드로 in-place 편집한다 (HORIEDIT.C:800).
```c
fp = fopen("koukai2.dat","r+b");
```
이 파일은 **세이브 슬롯 10개**가 연속해 저장된 구조이다. 각 슬롯 = **33340 byte 의 page** (HORIEDIT.H:195 `#define PAGE 33340L`). 따라서 본 에디터에서 "게임 원본 선박 데이터" 라는 말도 실제로는 **선택된 세이브 슬롯 안의 선박 템플릿 영역**을 의미한다 (각 슬롯이 자기 자신의 25개 선박 템플릿 사본을 가짐).

### 1-2. page 전역변수
```c
long page = 0;                        // HORIEDIT.H:197
#define PAGE 33340L;                  // HORIEDIT.H:195   ※ 매크로 끝의 ;는 의도되지 않은 것
```
`sel_save()` (HORIEDIT.C:785~786):
```c
page = PAGE;          // page = 33340L;
page *= (i-1);        // page = 33340L * (선택한 슬롯 인덱스 0..9)
```
모든 선박/항구 fseek 은 **저장된 베이스 주소(*_addr) + page** 형태.

### 1-3. 슬롯 헤더 (Init) 영역
파일 첫 부분에 슬롯 메타데이터 10개가 박힘. sel_save 에서 `fseek(fp, 1+sizeof(struct Init)*i, SEEK_SET)` (HORIEDIT.C:735). 즉 파일 오프셋 `1 + 15*i` (i=0..9). **선두 1 byte 는 의미 불명 — 분석가 A 영역**.

### 1-4. 본 문서가 다루는 fseek 베이스 주소

| 심볼 | 값 | 슬롯 내 의미 |
|---|---|---|
| `ship1_addr[c_hero]` | 영웅별 6개 (아래) | 영웅이 보유 중인 함대(현재 상태) Ship1 배열 시작 |
| `ship2_addr` | `0x4692` | 함대(현재 상태) Ship2 배열 시작 |
| `ship3_addr` | `0x4C35` | 함대(현재 상태) Ship3 배열 시작, 또한 Ship1.select 인덱싱의 베이스 |
| `ship4_addr` | `0x5291` | 25종 선박 템플릿(Ship4) 시작 |
| `s_addr` | `0x501D` | 25종 선박 템플릿 이름표(Ship5) 시작 |
| `port_addr` | `0x53BF` | 130개 항구(Port) 시작 |

```c
const long ship1_addr[6] = {0x2244, 0x2776, 0x31DA, 0x3C3E, 0x370C, 0x2CA8};  // HORIEDIT.H:127
const long ship2_addr = 0x4692L;     // HORIEDIT.H:128
const long ship3_addr = 0x4C35L;     // HORIEDIT.H:129
const long ship4_addr = 0x5291;      // HORIEDIT.H:130
const long s_addr     = 0x501DL;     // HORIEDIT.H:131
const long port_addr  = 0x53BF;      // HORIEDIT.H:140
```

`ship1_addr` 만 **6명의 주인공 인덱스(JOAN=0, CAT=1, OTTO=2, ROPEZ=3, PIET=4, AAL=5)** 별로 베이스가 다르다. Ship2/Ship3/Ship4/Ship5/Port 는 슬롯당 1세트만 존재.

---

## 2. 선박 관련 자료구조 (Ship1~Ship5) — 필드별 바이트 매핑

DOS 16-bit Borland C++ 환경 → `unsigned`/`unsigned int` = **2 byte little-endian**, `unsigned char` = 1 byte. 패킹은 자연 정렬되어 패딩 없음.

### 2-1. struct Ship1 — 함대 한 척의 현재 상태 (총 9 byte) — HORIEDIT.H:149~158
```c
struct Ship1 {
    unsigned       ccrew;     // 2B  현재 승무원 수
    unsigned char  chull;     // 1B  현재 선체 HP
    unsigned char  lhull;     // 1B  최대 선체
    unsigned char  crudder;   // 1B  현재 회전력
    unsigned char  csail;     // 1B  현재 돛
    unsigned char  cnowea;    // 1B  현재 무기 수
    unsigned char  select;    // 1B  Ship3 테이블 인덱스 (0xFF = 함대 끝)
    unsigned char  cselwea;   // 1B  현재 장착 무기 (0x10=없음, 0x11..0x17)
};
```
`select==0xFF` 가 함대 끝 sentinel (conferm_hero, HORIEDIT.C:687,697).

### 2-2. struct Ship2 — 함대 한 척의 운용 상태 (총 30 byte) — HORIEDIT.H:160~165
```c
struct Ship2 {
    unsigned char  captin;     // 1B  선장 (Person 인덱스로 추정)
    unsigned char  condition;  // 1B  컨디션
    unsigned char  ship_form;  // 1B  현재 진형 (form_name 인덱스 0..10)
    unsigned char  none[27];   // 27B 의미 미상 (편집 안 됨, 보존 필수)
};
```

### 2-3. struct Ship3 — 함대 한 척의 가변 함선 정보 (총 25 byte) — HORIEDIT.H:167~175
```c
struct Ship3 {
    char           ship_name[14];   // 14B 함선 이름 (NUL-terminated)
    unsigned char  none[4];         //  4B 의미 미상 (보존 필수)
    unsigned char  ship_select;     //  1B 함선 종류 인덱스 (0..24, 0xFF=끝)
    unsigned char  bform;           //  1B 함선 외형. 상위 4비트는 Ship5.bform, 하위 4비트는 사용자 편집 분
    unsigned char  f_weap;          //  1B 무기 적재 한도(현재 설정)
    unsigned int   f_crew;          //  2B 승무원 적재 한도(현재 설정)
    unsigned int   cargo;           //  2B 화물 가용 적재량 = capacity - f_weap - f_crew
};
```
크기 14+4+1+1+1+2+2 = **25 byte**.

### 2-4. struct Ship4 — 선박 템플릿(25종) 정적 스펙 (총 12 byte) — HORIEDIT.H:177~185
```c
struct Ship4 {
    unsigned char  lrudder;     // 1B  최대 회전력
    unsigned char  lsail;       // 1B  최대 돛
    unsigned char  lcrew;       // 1B  최대 승무원 / 10  (실제 최대치는 lcrew*10)
    unsigned char  dcrew;       // 1B  필요 승무원
    unsigned int   capacity;    // 2B  최대 적재량
    unsigned char  lnowea;      // 1B  최대 무기수
    unsigned char  none[5];     // 5B  의미 미상 (보존)
};
```
**중요**: 최대 승무원은 `ship4.lcrew * 10` (HORIEDIT.C:450,503,560,597,601~602). 사용자 입력은 10단위로 저장 (HORIEDIT.C:597 `ship4.lcrew = imsi/10;`).

### 2-5. struct Ship5 — 선박 템플릿(25종) 이름·외형 (총 25 byte) — HORIEDIT.H:187~192
```c
struct Ship5 {
    char           name[18];    // 18B 선박 이름(템플릿 이름)
    unsigned char  sform;       //  1B 함선 외형(평상시)
    unsigned char  bform;       //  1B 함선 외형(부울때) — 상위 4비트가 의미
    char           none[5];     //  5B 추가적인 부울때 데이터 (보존)
};
```

### 2-6. struct Init (총 15 byte) — HORIEDIT.H:133~138
```c
struct Init {
    char           memo[12];    // 12B 메모
    unsigned char  port;        //  1B 항구 번호 (0xFF = 해상)
    unsigned char  ending;      //  1B 엔딩 여부
    unsigned char  none;        //  1B
};
```
*분석가 A 영역. 단 port 필드가 port_name 인덱스로 쓰인다.*

### 2-7. struct Port (총 20 byte) — HORIEDIT.H:142~145
```c
struct Port {
    char           name[15];
    unsigned char  none[5];
};
```

---

## 3. 선박 종류 / 무기 / 진형 / 항구 #define 테이블

### 3-1. 선박 종류 #define ↔ ship_name[25] 인덱스 (HORIEDIT.H:56~80)
**#define 값 = ship_name[] 인덱스 그대로** (BALS=0..GWAN=24).

| #define | 값 | | #define | 값 | | #define | 값 |
|---|---|---|---|---|---|---|---|
| BALS | 0x00 | | NAO  | 0x08 | | LGAL | 0x12 |
| HANJ | 0x01 | | KARA | 0x09 | | PGAL | 0x13 |
| DAWO | 0x02 | | GAL  | 0x0A | | BGAL | 0x14 |
| BUS  | 0x03 | | JEBE | 0x0B | | RA   | 0x15 |
| TARE | 0x04 | | PANE | 0x0C | | CHEO | 0x16 |
| RATI | 0x05 | | SLOO | 0x0D | | AN   | 0x17 |
| REDO | 0x06 | | PREG | 0x0E | | GWAN | 0x18 |
| BRIG | 0x07 | | BAG  | 0x0F | | | |
|      |      | | SHIP | 0x10 | | | |
|      |      | | JUNK | 0x11 | | | |

`ship_name[25][18]` 은 헤더에서 **선언만**(HORIEDIT.H:82) — 텍스트는 `init_hori()` 가 koukai2.dat 의 s_addr 영역에서 25개 Ship5 를 읽어 `ship5.name` 을 strcpy 해서 채운다 (HORIEDIT.C:716~720). **즉 ship_name 텍스트는 슬롯마다 다를 수 있다.**

### 3-2. 무기 #define ↔ weapon_name[8] 인덱스 (HORIEDIT.H:84~100)
**weapon_name 인덱스와 #define 값은 다르다.** weapon_name[8] 은 컴파일 타임 초기화:

| weapon_name 인덱스 | 표시 이름 | 대응 #define | #define 값 |
|---|---|---|---|
| 0 | 없음 | (개념적으로 0x10) | 0x10 |
| 1 | 캐넌 | CANO | 0x11 |
| 2 | 더블캐넌 | DCAN | 0x12 |
| 3 | 캐넌포얼 | CANP | 0x13 |
| 4 | 쿨베린 | KBR  | 0x14 |
| 5 | 더블쿨베린 | DKBR | 0x15 |
| 6 | 세이커 | SEKE | 0x16 |
| 7 | 카로네이드 | KND  | 0x17 |

표시: `weapon_name[ship1.cselwea - 0x10]` (HORIEDIT.C:405). 0x10이면 weapon_name[0]="없음".

#### 무기 선택 UI (HORIEDIT.C:459~467)
```c
case 10 : do {
   for (j=0; j<8; j++) hprintf("%d) %s\n", j+1, weapon_name[j]);
   hscanf("%u", &imsi);
   if (imsi==0) break;
   imsi += 16;
   if (imsi <= (8+16)) ship1.cselwea = (unsigned char)(imsi-1);
   if (ship1.cselwea == 0x10) ship1.cnowea = 0;
} while (imsi > (8+16));
```
- 사용자 입력 1..8 → `+16` → 17..24 → `imsi-1` → 16..23 (0x10..0x17).
- **사용자 입력 1 ↔ "없음" (0x10), 입력 2 ↔ CANO (0x11)** ... 입력 8 ↔ KND (0x17).
- `cselwea == 0x10` 일 때 `cnowea` 강제 0 (무장 없음).

### 3-3. 진형 #define ↔ form_name[11] 인덱스 (HORIEDIT.H:102~124)
form_name[11] 컴파일 타임 초기화. **#define 값 = form_name 인덱스 그대로**:

| 인덱스 | 이름 | 대응 #define | 값 |
|---|---|---|---|
| 0  | 없음 | (없음) | 0x00 |
| 1  | 바다표범 | JAGU | 0x01 |
| 2  | 제독 | ADMI | 0x02 |
| 3  | 유니콘 | UNIC | 0x03 |
| 4  | 사자 | LION | 0x04 |
| 5  | 독수리 | EAGL | 0x05 |
| 6  | 왕자 | PERS | 0x06 |
| 7  | 포세이돈 | POSE | 0x07 |
| 8  | 용 | DRAG | 0x08 |
| 9  | 천사 | ANGE | 0x09 |
| 10 | 여신 | GOD  | 0x0A |

`ship2.ship_form` 은 form_name 인덱스 그대로 (0..10). 사용자 입력 1..11 → 저장값 0..10 (HORIEDIT.C:474).

### 3-4. 항구
별도 #define 없음. `port_name[130][15]` (HORIEDIT.H:147) — 헤더에서 선언만. sel_save 가 port_addr 영역에서 130개 Port 를 읽어 채운다 (HORIEDIT.C:791~795).

---

## 4. ship1_addr[6], ship2_addr, ship3_addr, ship4_addr, s_addr, port_addr 의 의미

`page` 가 결정된 상태에서 (page = 33340 * slot_index, slot_index=0..9):

### 4-1. 함대 데이터 — 주인공별 Ship1 분리
```c
load(sel):                                                       // HORIEDIT.C:322~333
  offset1 = ship1_addr[c_hero] + page + sel * sizeof(Ship1);     // 9 byte/entry
  offset2 = ship2_addr        + page + sel * sizeof(Ship2);      // 30 byte/entry
  offset3 = ship3_addr        + page + ship1.select * sizeof(Ship3);  // 25 byte/entry
```
- `ship1_addr[c_hero]` 만 영웅 의존(c_hero=0..5).
- `ship1.select` 는 **함선 슬롯 인덱스가 아니라 Ship3 테이블 안의 인덱스**. Ship1 와 Ship2 는 동일 sel 로 1:1 짝.
- Ship1 의 `select == 0xFF` 면 함대 끝.

### 4-2. 선박 템플릿 — 슬롯당 1세트
```c
load4(sel):  offset = page + ship4_addr + sizeof(Ship4)*sel;     // 12 byte/entry
load5(sel):  fseek(fp, s_addr + page + sizeof(Ship5)*sel, ...);  // 25 byte/entry
```
sel 은 0..24.

### 4-3. 항구 — 슬롯당 1세트
```c
offset = port_addr + 20*i + page;  (i=0..129)
```
sel_save 의 슬롯 목록 표시(HORIEDIT.C:750)에서는 `i*33340 + init.port*sizeof(Port) + port_addr` — 즉 page 변수가 아직 미설정이라 직접 곱한다. **page = i*33340 와 동등.**

### 4-4. 슬롯 헤더(Init) 위치는 page 와 무관
sel_save: `1 + sizeof(Init)*i` (HORIEDIT.C:735) — 파일 첫 부분의 별도 영역. **page 와 결합하지 않음.**

---

## 5. `hero_ship_edit()` — 영웅 함대 편집 (HORIEDIT.C:360~520)

### 5-1. 목적과 사용자 흐름
현재 주인공(`c_hero`)이 보유한 함대(0..ship_num-1)에서 한 척을 골라 가변 데이터를 편집.

#### 진입 조건
- `ship_num == 0` 이면 "보유 함선 없음" 메시지 후 종료 (HORIEDIT.C:366~370).

#### 메인 메뉴 (HORIEDIT.C:372~385)
```
0) 빠져 나간다
1) 제 1함선을 고친다
...
N) 제 N함선을 고친다
```
입력 sel: 0=종료, 1..ship_num → sel-- 후 함선 1대 편집.

#### 선택 후 로딩
```c
load(sel);                       // ship1, ship2, ship3 동시에 읽음
load4(ship3.ship_select);        // 해당 선박의 템플릿(Ship4) 로딩
```
**load5 는 호출하지 않음** (Ship5 는 함선 종류 변경 시에만 로드).

### 5-2. 함선 편집 메뉴 (HORIEDIT.C:391~411)
```
 0) 빠져나간다 (저장)
 1) 현재 승무원      : ship1.ccrew
 2) 현재 선체        : ship1.chull
 3) 최대 선체        : ship1.lhull
 4) 현재 회전력      : ship1.crudder
 5) 현재 돛          : ship1.csail
 6) 현재 무기수      : ship1.cnowea
 7) 현재 컨디션      : ship2.condition
    카르고           : ship3.cargo                    (편집 불가, 표시만)
 8) 최대 적재 승무원 : ship3.f_crew
 9) 최대 적재 무기수 : ship3.f_weap
10) 현재 무기        : weapon_name[ship1.cselwea-16]
11) 현재 진형        : form_name[ship2.ship_form]
12) 현재 함선        : ship_name[ship3.ship_select]
13) 함선 이름        : ship3.ship_name
```
검증: `do {...} while(i>13);`.

### 5-3. 각 case 동작

#### case 1 — `ship1.ccrew`
```c
ship1.ccrew = imsi;
if (ship1.ccrew > ship3.f_crew) ship1.ccrew = ship3.f_crew;
```

#### case 2 — `ship1.chull`
```c
ship1.chull = (unsigned char)imsi;
if (ship1.chull > ship1.lhull) ship1.chull = ship1.lhull;
```

#### case 3 — `ship1.lhull`
```c
ship1.lhull = (unsigned char)imsi;
if (ship1.chull > ship1.lhull) ship1.chull = ship1.lhull;
```

#### case 4 — `ship1.crudder`
```c
ship1.crudder = (unsigned char)imsi;
if (ship1.crudder > ship4.lrudder) ship1.crudder = ship4.lrudder;
```

#### case 5 — `ship1.csail`
```c
ship1.csail = (unsigned char)imsi;
if (ship1.csail > ship4.lsail) ship1.csail = ship4.lsail;
```

#### case 6 — `ship1.cnowea`
```c
ship1.cnowea = (unsigned char)imsi;
if (ship1.cnowea > ship3.f_weap) ship1.cnowea = ship3.f_weap;
if (ship1.cselwea == 0x10) ship1.cnowea = 0;
```

#### case 7 — `ship2.condition`
```c
ship2.condition = (unsigned char)imsi;     // 클램프 없음
```

#### case 8 — `ship3.f_crew`
```c
ship3.f_crew = imsi;
if (ship3.f_crew > (unsigned int)(ship4.lcrew*10)) ship3.f_crew = ship4.lcrew*10;
if (ship1.ccrew > ship3.f_crew) ship1.ccrew = ship3.f_crew;
```

#### case 9 — `ship3.f_weap`
```c
ship3.f_weap = (unsigned char)imsi;
if (ship3.f_weap > ship4.lnowea) ship3.f_weap = ship4.lnowea;
if (ship1.cnowea > ship3.f_weap) ship1.cnowea = ship3.f_weap;
```

#### case 10 — 무기 변경
§3-2 참조. 사용자 입력 1..8 → cselwea = 0x10..0x17. `imsi==0` 이면 break. cselwea==0x10 면 cnowea=0.

#### case 11 — 진형 변경 (HORIEDIT.C:468~475)
사용자 입력 1..11, 0=취소.
```c
if (imsi==0) break;
if (imsi<=11) ship2.ship_form = (unsigned char)(imsi-1);
```

#### case 12 — 함선 종류 변경 (HORIEDIT.C:476~506) **가장 복잡**
사용자 입력 1..25. 0=취소.
```c
if (imsi==0) break;
if (imsi<=25) ship3.ship_select = (unsigned char)(imsi-1);

load4(ship3.ship_select);
load5(ship3.ship_select);

bitmask1 = ship5.bform;  bitmask1 &= 0xF0;
bitmask2 = ship3.bform;  bitmask2 &= 0x0F;
bitmask1 |= bitmask2;
ship3.bform = bitmask1;          // 상위 4비트=새 함선, 하위 4비트=기존값

if (ship1.crudder > ship4.lrudder) ship1.crudder = ship4.lrudder;
if (ship1.csail   > ship4.lsail)   ship1.csail   = ship4.lsail;
if (ship1.cnowea  > ship4.lnowea)  ship1.cnowea  = ship4.lnowea;
if (ship3.f_crew  > (unsigned int)(ship4.lcrew*10)) ship3.f_crew = ship4.lcrew*10;
if (ship1.ccrew   > ship3.f_crew)  ship1.ccrew   = ship3.f_crew;
ship3.cargo = ship4.capacity - (unsigned int)ship3.f_weap - ship3.f_crew;
```

#### case 13 — 함선 이름 (HORIEDIT.C:507~511)
```c
hgetln(ship3.ship_name, 14);    // 14 byte 중 13자 + NUL
```
`_hangulmode = true` 후 입력, 다시 false.

### 5-4. 매 메뉴 루프 끝의 cargo 재계산 (HORIEDIT.C:513)
```c
ship3.cargo = ship4.capacity - (unsigned int)ship3.f_weap - ship3.f_crew;
```
**모든 case 후 매 루프마다** 실행. case 12 안에서도 추가로 한 번 더.

> **함정**: 16-bit unsigned 산술 → 음수가 되면 언더플로우. Python 옮길 시 `(capacity - f_weap - f_crew) & 0xFFFF`.

### 5-5. 저장 (HORIEDIT.C:516, store HORIEDIT.C:335~343)
```c
store():
  fwrite(&ship1) at offset1;
  fwrite(&ship2) at offset2;
  fwrite(&ship3) at offset3;
```
i==0 일 때 한 함선 편집 끝에서 store() 호출. 외부 메뉴에서 0 입력 시 함수 종료.

---

## 6. `org_ship_edit()` — 원본 선박 템플릿 편집 (HORIEDIT.C:522~651)

### 6-1. 목적
선박 25종(ship_name 인덱스 0..24)의 **템플릿(Ship4 + Ship5)** 을 편집한다. 한 슬롯 안의 함대 스펙(최대치, 이름)을 바꾼다. **편집 대상은 koukai2.dat 그 자체이지만, 위치는 슬롯 내 영역(ship4_addr/s_addr)** 이다 — 즉 슬롯별로 별도 사본이 존재한다. "원본"이라는 용어가 오해를 일으키나, 코드상 슬롯 내 25종 템플릿을 직접 수정. 게다가 한도 변경 시 그 종류를 사용 중인 모든 함대 인스턴스의 ship1/ship3 을 새 한도에 자동 클램프 한다.

### 6-2. 사용자 흐름
1. ship_name[0..24] 25개 메뉴 표시 (2열 배치, HORIEDIT.C:534~542). 0=종료.
2. 선택값 sel--, sel = 0..24.
3. 슬롯의 Ship4 + Ship5 를 page 결합 오프셋에서 read (HORIEDIT.C:549~553).
4. 편집 메뉴 진입. 0=저장하고 종료, 1..7 편집.
5. 종료 시 Ship4 만 fwrite (Ship5 는 case 7 안에서 즉시 저장).

### 6-3. 편집 메뉴 (HORIEDIT.C:555~568)
```
0) 빠져 나간다 (저장)
1) 최대 회전력 : ship4.lrudder
2) 최대 돛     : ship4.lsail
3) 최대 승무원 : ship4.lcrew * 10        (※ 표시 *10)
4) 필요 승무원 : ship4.dcrew
5) 최대 적재량 : ship4.capacity
6) 최대 무기수 : ship4.lnowea
7) 배이름      : ship5.name
```
검증: `do {...} while (i>7);`.

### 6-4. 각 case 동작

> **공통 패턴**: 한도(case 1,2,3,5,6) 변경 시 **모든 함대(0..ship_num-1)** 를 순회하며 해당 종류를 쓰는 함선들의 ship1/ship3 을 새 한도에 맞게 클램프 후 store(). 임시변수 i 를 for 루프에 재사용 (HORIEDIT.C:574 이후).

#### case 1 — `ship4.lrudder`
```c
ship4.lrudder = (unsigned char)imsi;
for (i=0; i<ship_num; i++) {
    load(i);
    if (ship3.ship_select == sel) {
        if (ship1.crudder > ship4.lrudder) {
            ship1.crudder = ship4.lrudder;
            store();
        }
    }
}
```
*주의*: `load(i)` 가 ship4 를 갱신하지 않음 (load4 호출 없음). 비교에 쓰는 `ship4.lrudder` 는 막 입력한 값.

#### case 2 — `ship4.lsail`
구조 동일. `ship1.csail` 클램프.

#### case 3 — `ship4.lcrew` (사용자 입력은 *10 단위)
```c
ship4.lcrew = (unsigned char)(imsi/10);
for (i=0; i<ship_num; i++) {
    load(i);
    if (ship3.ship_select == sel) {
        if (ship3.f_crew > (unsigned int)(ship4.lcrew*10)) {
            ship3.f_crew = (unsigned int)(ship4.lcrew*10);
            if (ship1.ccrew > ship3.f_crew) ship1.ccrew = ship3.f_crew;
            ship3.cargo = ship4.capacity - (unsigned int)ship3.f_weap - ship3.f_crew;
            store();
        }
    }
}
```

#### case 4 — `ship4.dcrew`
```c
ship4.dcrew = (unsigned char)imsi;     // 클램프/연쇄 없음
```

#### case 5 — `ship4.capacity`
```c
ship4.capacity = imsi;
for (i=0; i<ship_num; i++) {
    load(i);
    if (ship3.ship_select == sel) {
        ship3.cargo = ship4.capacity - (unsigned int)ship3.f_weap - ship3.f_crew;
        store();                          // 무조건 store
    }
}
```

#### case 6 — `ship4.lnowea`
```c
ship4.lnowea = (unsigned char)imsi;
for (i=0; i<ship_num; i++) {
    load(i);
    if (ship3.ship_select == sel) {
        if (ship3.f_weap > ship4.lnowea) {
            ship3.f_weap = ship4.lnowea;
            if (ship1.cnowea > ship3.f_weap) ship1.cnowea = ship3.f_weap;
            ship3.cargo = ship4.capacity - (unsigned int)ship3.f_weap - ship3.f_crew;
            store();
        }
    }
}
```

#### case 7 — `ship5.name`
```c
hgetln(name, 18);
strcpy(ship5.name, name);
fseek(fp, s_addr + page + sizeof(Ship5)*sel, SEEK_SET);
fwrite(&ship5, sizeof(Ship5), 1, fp);
strcpy(ship_name[sel], ship5.name);          // 메모리 캐시도 갱신
```
**여기서만 Ship5 즉시 디스크 기록.** 메모리 ship_name 캐시도 동기화.

### 6-5. 종료 시 Ship4 저장 (HORIEDIT.C:648~649)
```c
fseek(fp, offset, SEEK_SET);
fwrite(&ship4, sizeof(struct Ship4), 1, fp);
```
*offset = `page + ship4_addr + sizeof(Ship4)*sel`* (HORIEDIT.C:549).

---

## 7. 항구 데이터 (struct Port, port_name)

- struct Port 20 byte (name[15] + none[5]).
- 슬롯 내 base = `port_addr (0x53BF) + page`, 130 entry.
- `port_name[130][15]` 는 sel_save 가 채운다 (HORIEDIT.C:789~795).
- **port 데이터 자체는 본 에디터에서 편집되지 않음**. 단지 표시·참조.
  - sel_save 슬롯 목록 표시(HORIEDIT.C:750~754) — 분석가 A
  - person_edit 인물 위치 변경(HORIEDIT.C:167~170, 239, 295~311) — 분석가 A

```c
// sel_save 의 port_name 캐시 채우기
offset = page + port_addr;
fseek(fp, offset, SEEK_SET);
for (i=0; i<130; i++) {
    fread(&port, sizeof(struct Port), 1, fp);
    strcpy(port_name[i], port.name);
}
```
Init.port == 0xFF 면 "해상", 그 외에는 port_name[Init.port] 가 현재 항구.

---

## 8. 외부 데이터 파일 의존성 (선박/항구 이름이 어디서 오는지)

| 배열 | source | 채우는 함수 |
|---|---|---|
| `ship_name[25][18]` | **koukai2.dat** 의 s_addr 영역 (Ship5.name) | `init_hori()` HORIEDIT.C:716~720. 슬롯마다 다를 수 있음. |
| `weapon_name[8][13]` | **헤더 정적 초기화** HORIEDIT.H:92~100 | 컴파일 타임. 8개 고정. |
| `form_name[11][11]` | **헤더 정적 초기화** HORIEDIT.H:113~124 | 컴파일 타임. 11개 고정. |
| `port_name[130][15]` | **koukai2.dat** 의 port_addr 영역 (Port.name) | `sel_save()` HORIEDIT.C:791~795. |
| `Epeer / Ipeer` | **헤더 정적 초기화** HORIEDIT.H:32~54 | 분석가 A 영역. |
| `hero[6][26]` | **koukai2.dat** 의 person_addr 영역 | `init_hori()`. 분석가 A 영역. |

`org_ship_edit` case 7 에서 사용자가 이름을 바꾸면 ship_name 캐시도 즉시 동기화 (HORIEDIT.C:644).

---

## 9. Python 구현가에게 전달할 핵심 주의사항

### 9-1. 엔디안 / 정수 크기
- DOS 16-bit Borland C: `unsigned int = unsigned` = **2 byte little-endian**, `unsigned char` = 1 byte, `unsigned long` = 4 byte (page, offset, money 등).
- `struct.pack/unpack` 권장 포맷:
  - **Ship1**: `<HBBBBBBB` (9 byte)
  - **Ship2**: `<BBB27s` (30 byte)
  - **Ship3**: `<14s4sBBBHH` (25 byte) — 14s=ship_name, 4s=none[4]
  - **Ship4**: `<BBBBHB5s` (12 byte)
  - **Ship5**: `<18sBB5s` (25 byte)
  - **Init**: `<12sBBB` (15 byte)
  - **Port**: `<15s5s` (20 byte)

### 9-2. 슬롯 결합 식
```python
page = 33340 * slot_index   # slot_index = 0..9
```
모든 데이터 영역은 `base_addr + page` 또는 `base_addr + entry_size*entry_idx + page`.

### 9-3. ship1.select vs ship3.ship_select
- `ship1.select` = **Ship3 테이블 내의 인덱스**. 0xFF = "함대 끝" 센티넬.
- `ship3.ship_select` = **선박 종류 인덱스 (0..24)**. 0xFF = "함대 끝" (conferm_hero).
- 두 필드 의미가 다른 것에 주의.

### 9-4. ship_num 결정 (분석가 A 영역, 참고)
conferm_hero 가 Ship1 배열을 순차 읽으며: `ship1.select == 0xFF` 면 break, 아니면 Ship2/Ship3 read 후 `ship3.ship_select == 0xFF` 면 break. 그 외 ship_num++.

### 9-5. 무기 인코딩
- `ship1.cselwea`: 0x10..0x17. 0x10=무장 없음. 표시: `weapon_name[cselwea - 0x10]`.
- 무장 없음(0x10)이면 cnowea 강제 0.

### 9-6. 진형 인코딩
- `ship2.ship_form`: 0..10. form_name[0..10] 직접 인덱싱.

### 9-7. 함선 종류 인코딩
- `ship3.ship_select`: 0..24. ship_name[0..24] 직접 인덱싱.

### 9-8. 최대 승무원
- 저장값 `ship4.lcrew` 는 **(실제 최대치 / 10)**. 표시·비교는 `lcrew*10`. 사용자 입력은 그대로 받아 `/10` 후 저장.

### 9-9. cargo 재계산
```python
ship3.cargo = (ship4.capacity - ship3.f_weap - ship3.f_crew) & 0xFFFF
```
- hero_ship_edit: 매 메뉴 루프 끝에서 재계산 (HORIEDIT.C:513).
- org_ship_edit: capacity 변경(case 5), case 3/6 의 클램프 시.

### 9-10. ship3.bform 비트 합성 (hero_ship_edit case 12 만)
```python
ship3.bform = (ship5.bform & 0xF0) | (ship3.bform & 0x0F)
```
**hero_ship_edit case 12 에서만**. org_ship_edit 에서는 일어나지 않음.

### 9-11. 클램프 체인 순서
함선 종류 변경 시(hero_ship_edit case 12), 한도 편집 시(org_ship_edit case 1~6) 클램프 체인 발생. **순서가 의미있다** (예: f_crew 클램프 → ccrew 클램프 → cargo 재계산). §5-3 case 12, §6-4 참고.

### 9-12. read-modify-write 시 미사용 필드 보존
- `Ship2.none[27]`, `Ship3.none[4]`, `Ship4.none[5]`, `Ship5.none[5]`, `Port.none[5]`, `Init.none` — 절대 0으로 덮지 말고 read 한 byte 그대로 유지 (편집 메뉴에서 다루지 않음).

### 9-13. ship_name / port_name 캐시 일관성
- 디스크의 Ship5.name / Port.name 이 진짜 source.
- 메모리 ship_name / port_name 은 캐시. 슬롯 변경 시(`init_hori()` / `sel_save()`) 다시 채워짐.
- 사용자가 ship5.name 편집 시(org_ship_edit case 7) 캐시 즉시 동기화.

### 9-14. 파일 검증 / 오류 처리
원본 코드는 fseek/fread/fwrite 의 반환값을 검사하지 않음. Python 에서도 동일하게 두되 `seek` 후 `read(N)` / `write(bytes)` 가 정확히 N byte 다루도록 binary mode 보장.

### 9-15. hero_ship_edit 의 hprintxf 인자 불일치 (HORIEDIT.C:407)
```c
hprintxf(" 12) 현재 함선 : $1c%s\n", ship_name[ship3.ship_select], sel);
```
포맷 specifier 1개에 인자 2개. `sel` 인자는 무시됨. Python 옮길 때 `ship_name[ship3.ship_select]` 만 출력.

### 9-16. PAGE 매크로의 함정 (HORIEDIT.H:195)
```c
#define PAGE 33340L;
```
세미콜론이 매크로 본문에 포함 → `page = PAGE;` 가 `page = 33340L;;` 로 확장. 동작 문제없음. Python 에서는 `PAGE = 33340`.

### 9-17. weapon_name 길이 = 8 / form_name 길이 = 11 인 이유
- weapon: ["없음", "캐넌", "더블캐넌", "캐넌포얼", "쿨베린", "더블쿨베린", "세이커", "카로네이드"]. #define 7개 (CANO..KND, 0x11..0x17) + "없음"(0x10).
- form: ["없음", "바다표범", "제독", "유니콘", "사자", "독수리", "왕자", "포세이돈", "용", "천사", "여신"]. #define 10개 (JAGU..GOD, 0x01..0x0A) + "없음"(0x00).

### 9-18. ship_name row 크기 vs Ship5.name 크기
- 두 영역의 한 entry 의 이름 크기는 18 byte로 같음. Ship5 전체는 25 byte.
