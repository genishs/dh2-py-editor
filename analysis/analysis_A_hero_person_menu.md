# horiedit 분석 — A 파트 (영웅/인물/메뉴/IO)

분석 대상:
- `D:\Documents\workspace\study\koukai2_edit\originalgame\koukai2\HORIEDIT.C`
- `D:\Documents\workspace\study\koukai2_edit\originalgame\koukai2\HORIEDIT.H`

본 문서는 Python 재구현을 위한 정밀 명세이다. 라인 번호는 위 두 소스 파일을 기준으로 한다. 선박 관련 함수(`hero_ship_edit`, `org_ship_edit`)와 `Ship1~Ship5` 구조체는 다른 분석가(B)의 명세를 참조하라. 다만 본 명세에 등장하는 `load/store/load4/load5`와 `conferm_hero` 내부의 선박 구조체 접근은 IO 측면에서 설명한다.

---

## 1. 개요

`horiedit`는 대항해시대 II (코에이) 의 세이브 파일 `KOUKAI2.DAT` 를 직접 바이트 단위로 편집하는 도구다. Borland Turbo C / DOS 환경에서 빌드되었고, `hanlib/hanin/hancode` 한글 콘솔 라이브러리를 이용해 한글을 입출력한다.

전체 흐름:
1. `main()` 에서 `KOUKAI2.DAT` 를 `r+b` (읽기/쓰기 바이너리) 로 열고 (HORIEDIT.C:800), 한글 콘솔 초기화 후 (HORIEDIT.C:805-810) `sel_save()` → `select_menu()` 로 진입.
2. `sel_save()` 가 10개 세이브 슬롯 중 하나를 고르게 하여 슬롯 베이스 오프셋(`page`) 을 설정.
3. `select_menu()` 에서 5개 메뉴(주인공/인물/주인공의배/오리지널배/세이브선택) 분기.
4. 각 편집 함수가 `fseek(fp, addr+page, SEEK_SET)` → `fread/fwrite` 로 직접 IO.

세이브 파일 한 슬롯의 크기는 `PAGE = 33340L` 바이트 (HORIEDIT.H:195). 파일 선두에 10개 세이브 슬롯의 메타데이터(`struct Init`) 가 있고, 그 뒤로 슬롯별 33340 바이트 데이터 영역이 10개 이어지는 것으로 보인다 (단, `sel_save()` 가 슬롯을 인덱싱할 때 `1 + sizeof(struct Init)*i` 를 쓰는 점은 §4 에서 다룬다).

엔디안: Turbo C / DOS x86 → **little-endian**. 모든 다바이트 정수는 little-endian 으로 직렬화되어 있다.

`userinithan()` 은 한글 콘솔(KSC5601/EUC-KR 출력 + IME) 초기화이며 데이터 수정 로직과 무관 — Python 에서는 일반 콘솔 입출력으로 대체.

---

## 2. 파일 구조와 오프셋 테이블

HORIEDIT.H 의 const long / #define 으로 선언된 모든 절대 오프셋 (슬롯 0 기준, 즉 `page=0` 일 때의 파일 오프셋):

| 심볼 | 값 | 라인 | 데이터 |
|---|---|---|---|
| `abil_addr[6]` | `{0x064D, 0x065B, 0x0669, 0x0677, 0x0685, 0x0693}` | H:16 | 6명 주인공의 `struct Abil` (sizeof = 14 bytes; §7) |
| `money_addr` | `0x06A1` | H:242 | `unsigned long money` (4 bytes) |
| `c_addr` | `0x06A8` | H:11 | `unsigned char` 1바이트 — 현재 선택된 주인공 번호 (0..5) |
| `person_addr` | `0x06A9` | H:236 | `struct Person` 배열 (sizeof = 50 bytes; §8) — 인물 데이터의 시작 |
| `ship1_addr[6]` | `{0x2244, 0x2776, 0x31DA, 0x3C3E, 0x370C, 0x2CA8}` | H:127 | 주인공별 `struct Ship1` 배열 (선박 분석가 명세 참조) |
| `ship2_addr` | `0x4692` | H:128 | `struct Ship2` 배열 |
| `ship3_addr` | `0x4C35` | H:129 | `struct Ship3` 배열 |
| `s_addr` | `0x501D` | H:131 | `struct Ship5` 배열 (선박 25척 원본 데이터) |
| `ship4_addr` | `0x5291` | H:130 | `struct Ship4` 배열 |
| `port_addr` | `0x53BF` | H:140 | `struct Port` 배열 130개 |

주의: `JOAN..AAL` (H:4-9) 는 6명 주인공 인덱스 상수(JOAN(0)=조안, CAT(1)=카탈리나, OTTO(2)=오토, ROPEZ(3)=로페즈, PIET(4)=피에트로, AAL(5)=알). `c_hero` 와 `abil_addr[c_hero]`, `ship1_addr[c_hero]` 의 인덱스로 쓰인다.

`PAGE = 33340L` 매크로 (H:195) 가 슬롯 간 거리.

```
실제 파일 오프셋 (슬롯 i, i=0..9) = (위 표의 값) + page,    page = 33340 * i
```

Person 영역의 끝은 `0x1DE7` 로 하드코딩 (HORIEDIT.C:211 `if (offset>(0x1DE7+page))`). 즉 person 영역은 `0x06A9..0x1DE7` (총 0x173F = 5951 바이트). `(0x1DE7 - 0x06A9 + 1) / 50 = 5951 / 50 = 119.02` → 약 119 명이 들어갈 수 있다 (추정).

---

## 3. main() / init_hori()

### main() (HORIEDIT.C:798-817)
```c
fp = fopen("koukai2.dat","r+b");   // 800
if (fp==NULL) { printf("I don't find save file.."); exit(-1); }
userinithan();                      // 805 한글 콘솔 초기화
hsetbkcolor(7); hsetcolor(0);       // 806-807
registerkssfont(KSS1);              // 808 한글 폰트 등록
hallowautoscroll(true);             // 809
_hangulmode = false;                // 810
sel_save();                         // 812
if (eXit==1) { fclose(fp); exit(0); } // 813
select_menu();                      // 815
fclose(fp);                         // 816
```

핵심: 파일명은 **"koukai2.dat"** (소문자 리터럴, 현재 디렉토리에서 열림). 모드 `"r+b"` → 읽기/쓰기 동시 가능, 바이너리. 파일이 없으면 표준 stdout 으로 영문 메시지 후 `exit(-1)`.

`eXit` 는 전역 `int eXit=0` (HORIEDIT.C:35). `sel_save()` 에서 사용자가 슬롯 0(취소) 또는 빈 슬롯을 선택하면 1 로 설정 → main 이 즉시 종료.

### init_hori() (HORIEDIT.C:701-721)
선택된 슬롯에서 다음을 메모리에 로드:

1. 6명 주인공 표시 이름 `hero[6][26]` (HORIEDIT.H:13) — `person_addr+page` 부터 sizeof(Person) 단위로 6개 읽고 `fname + " " + lname` 을 합쳐 저장.
   ```c
   offset = person_addr;           // 0x06A9
   fseek(fp, offset+page, SEEK_SET);
   for (i=0;i<6;i++) {
       fread(&ps, sizeof(Person), 1, fp);
       hero[i] = ps.fname + " " + ps.lname;
   }
   ```
   주의: `fseek` 는 루프 밖에서 한 번만, 이후 `fread` 가 파일 포인터를 자동 진행시킴. Python 재구현 시에도 6 × sizeof(Person) 만큼 순차 읽기.

2. 25개 선박 원본 이름 `ship_name[25][18]` (HORIEDIT.H:82) — `s_addr+page` 부터 sizeof(Ship5) 단위로 25개 읽고 `ship5.name` 복사.
   ```c
   fseek(fp, page+s_addr, SEEK_SET);  // 0x501D + page
   for (i=0;i<25;i++) { fread(&ship5,...); strcpy(ship_name[i], ship5.name); }
   ```
   `Ship5` 구조: `char name[18]; unsigned char sform; unsigned char bform; char none[5];` → sizeof = 25 bytes (H:187-192).

`init_hori()` 는 `sel_save()` 의 마지막에서 호출된다 (HORIEDIT.C:787). 따라서 `page` 가 이미 설정된 상태.

---

## 4. sel_save() — 세이브 슬롯 선택

HORIEDIT.C:723-796. 사용자에게 10개 세이브 슬롯의 요약(메모/항구/주인공이름)을 표시하고 하나를 고르게 한다.

### 슬롯 메타데이터 위치 (중요)
```c
fseek(fp, 1+sizeof(struct Init)*i, SEEK_SET);    // 735
fread(&init, sizeof(struct Init), 1, fp);        // 736
```

→ **파일 맨 앞 1바이트는 건너뛰고** 그 뒤부터 `struct Init` 가 10개 연속한다. 즉:
- offset 0 : 알 수 없는 1바이트 (헤더/매직 추정 — 본 에디터는 이 바이트를 읽기/쓰기 하지 않음)
- offset `1 + 15*i` : 슬롯 i 의 `struct Init` (sizeof = 12+1+1+1 = 15 bytes, HORIEDIT.H:133-138)

`struct Init` 구성:
```c
char memo[12];             // 사용자 메모 (널 종료, 빈 슬롯이면 memo[0]==0)
unsigned char port;        // 현재 항구 번호 (0xFF 이면 "해상")
unsigned char ending;      // 엔딩 도달 플래그 (0이 아니면 '*' 표시)
unsigned char none;        // 패딩
```

### 화면 표시 루프 (C:734-767) — 의사 코드
```
for i in 0..9:
    fseek(1 + 15*i); read(Init)
    if init.memo[0] == 0:
        "%2d) No data"; save_flg[i]=0
    else:
        save_flg[i]=1
        if init.port == 0xFF:
            "*" if init.ending else " ";  "해상"
        else:
            "*" if init.ending else " "
            offset = i*33340 + init.port*sizeof(Port) + port_addr
            seek/read Port → port.name 출력
        # 주인공 이름:
        seek(c_addr + i*33340); read 1 byte → c_hero
        offset  = person_addr
        offset += sizeof(Person) * c_hero
        offset += i * 33340L
        seek/read Person → "fname lname"
```

여기서 슬롯 인덱스 `i` 에 대해 `i*33340` (==`PAGE*i`) 를 더해 슬롯별 베이스 오프셋을 만든다. `sel_save` 단계에서는 `page` 변수를 아직 설정하지 않았기 때문에 `i*33340` 을 직접 곱한다.

`c_hero` 는 `unsigned int` 로 선언되어 있지만(`unsigned c_hero;` H:238) 여기서 `fread(&c_hero, 1, 1, fp)` 로 **딱 1바이트만 읽는다**. little-endian 이므로 하위 바이트(즉 0..5 범위의 값)에 들어가고 상위 바이트는 이전 값이 남을 수 있다. Python 재구현 시 `c_hero` 는 1바이트 정수로 다뤄야 한다 (절대 2바이트로 읽지 말 것).

### 입력 처리 (C:769-778)
```c
hscanf("%d", &i);
if (i!=0 && i<11 && save_flg[i-1]==0) {
    "데이타가 없는 번호는 지정하실 수 없습니다."
    pause();
    i = 11;     // 루프 재진입 강제
}
} while (i > 10);
```
- 사용자는 0 (취소) 또는 1..10 (슬롯 번호) 입력.
- 빈 슬롯을 입력하면 `i=11` 로 강제하여 do-while 재진입.
- 음수나 11 이상 → do-while 재진입 (i>10 조건). 음수가 입력되면 `i>10` 이 false 라 루프를 빠져나오지만 그 뒤 `save_flg[i-1]==0` 체크에서 인덱스 음수 접근 위험. 추정: 원본은 양수만 입력된다고 가정.

### 종료 / 슬롯 확정 (C:780-795)
```c
if (i==0 || save_flg[i-1]==0) { eXit=1; return; }   // 취소
page = PAGE; page *= (i-1);    // 33340 * (slot-1)
init_hori();                   // hero[], ship_name[] 초기화
conferm_hero();                // c_hero 갱신, ship_num 계산
offset = page + port_addr;
fseek(fp, offset, SEEK_SET);
for (i=0;i<130;i++) {
    fread(&port, sizeof(Port), 1, fp);
    strcpy(port_name[i], port.name);     // port_name[130][15]
}
```

따라서 슬롯 선택 후:
- `page = 33340 * (slot_number - 1)` (slot_number 는 1..10)
- 130개 항구 이름이 `port_name[130][15]` (H:147) 에 캐시됨
- `c_hero` 가 갱신되고 `ship_num` 이 카운트됨 (conferm_hero)

`struct Port` 는 `char name[15]; unsigned char none[5];` → sizeof = 20 bytes (H:142-145).

---

## 5. select_menu() — 메인 메뉴

HORIEDIT.C:652-675. 단순한 숫자 입력 분기 메뉴 (커서 이동/방향키 없음, ENTER/ESC 도 사용하지 않음. `hscanf("%d", ...)` 로 정수 입력만 받는다).

```
0) 끝낸다                       → return
1) 주인공 데이타 에디트         → hero_abil_edit()
2) 인물 데이타 에디트           → person_edit()
3) 주인공 선박 에디트           → hero_ship_edit()    (선박 분석가 명세)
4) 오리지날 선박 에디트         → org_ship_edit()     (선박 분석가 명세)
5) 다른 세이브번호 선택         → sel_save()
```

루프는 `select != 0` 동안 반복. `select` 는 `char` 타입 (C:654). 0 입력 시 `return;` (메뉴 빠져나가서 main 이 fclose 후 종료).

주의: 메뉴 5번을 누르면 `sel_save()` 가 다시 실행되어 `page` 가 다시 세팅된다. 이때 `eXit=1` 이 되더라도 `select_menu` 는 그것을 검사하지 않으므로 그대로 메인 메뉴로 돌아오고, 0 을 눌러 빠져나오면 main 의 `fclose(fp)` 만 실행된다 (eXit==1 종료 분기는 main 의 첫 진입 시에만 검사됨, C:813).

---

## 6. conferm_hero() — 주인공 확인 + 선박 카운트

HORIEDIT.C:677-699. 슬롯의 현재 주인공 번호를 읽고, 그 주인공이 보유한 함대 선박 수(`ship_num`) 를 카운트한다.

```c
fseek(fp, c_addr+page, SEEK_SET);     // 0x06A8 + page
fread(&c_hero, 1, 1, fp);             // 1바이트만 읽음

ship_num = 0;
while (1) {
    offset1 = ship1_addr[c_hero] + page + (ship_num * sizeof(Ship1));
    fseek(fp, offset1, SEEK_SET); fread(&ship1,...);
    if (ship1.select != 0xff) {
        offset2 = ship2_addr + page + (ship_num * sizeof(Ship2));
        fseek/read ship2;
        offset3 = ship3_addr + page + (ship1.select * sizeof(Ship3));
        //                              ^^^^^^^^^^^^ ship_num 이 아니라 ship1.select
        fseek/read ship3;
        if (ship3.ship_select == 0xff) break;
        ship_num++;
    }
    else if (ship1.select == 0xff) break;
}
```

핵심:
- `ship1.select` 가 `0xFF` 면 빈 슬롯 → 루프 종료.
- 그렇지 않으면 `ship_num` 만큼 진행한 ship2 와, **`ship1.select`** 인덱스의 ship3 를 읽고, `ship3.ship_select==0xFF` 도 종료 조건.
- ship3 는 별도의 선박 데이터 풀이고, ship1 가 어느 ship3 를 가리키는지 포인터 역할 (선박 분석가 명세 참조).
- 카운트 결과 `ship_num` 은 hero_ship_edit 에서 사용된다.

---

## 7. hero_abil_edit() — 영웅 능력치 편집

HORIEDIT.C:38-128.

### 진입 시 데이터 로드 (C:45-48)
```c
fseek(fp, abil_addr[c_hero]+page, SEEK_SET);
fread(&abil, sizeof(struct Abil), 1, fp);     // 14 bytes
fseek(fp, money_addr+page, SEEK_SET);
fread(&money, sizeof(money), 1, fp);          // 4 bytes (unsigned long)
```

### `struct Abil` 메모리 레이아웃 (HORIEDIT.H:18-30)
| 오프셋 | 크기 | 필드 | 의미 |
|---|---|---|---|
| 0  | 2 | `unsigned trade`  | 무역 명성 (uint16 LE) |
| 2  | 2 | `unsigned robber` | 해적 명성 (uint16 LE) |
| 4  | 2 | `unsigned adven`  | 모험 명성 (uint16 LE) |
| 6  | 1 | `unsigned char pro`  | 포르투갈 친밀도 (실제 표시는 `pro - 100`) |
| 7  | 1 | `unsigned char spa`  | 스페인 친밀도 |
| 8  | 1 | `unsigned char osm`  | 오스만(터키) 친밀도 |
| 9  | 1 | `unsigned char eng`  | 영국 친밀도 |
| 10 | 1 | `unsigned char ita`  | 이탈리아 친밀도 |
| 11 | 1 | `unsigned char ned`  | 네덜란드 친밀도 |
| 12 | 1 | `unsigned char none` | 패딩 |
| 13 | 1 | `unsigned char peer` | 작위 (0..9) |

→ sizeof(Abil) = 14 bytes. Python 포맷: `<3H 8B`.

### 친밀도 ±100 변환 (C:50-55, 118-123)
저장된 값은 0..200 의 `unsigned char` 이지만 사용자에겐 -100..+100 범위로 보이도록 표시/입력 시 100 을 빼고 더한다:
```
표시: pro_display = (signed) abil.pro - 100;
입력: abil.pro = (unsigned char)(pro_input + 100);
```
표시할 때 음수면 `$4c` (빨간색), 양수면 `$1c` 컬러 코드(hprintxf 마크업) 적용. 색상 분기는 시각 효과일 뿐이고 데이터에는 영향 없음.

### 작위(peer) 선택 (C:104-114)
```c
case 10:
    do {
        " 0) 고치지 않고 빠져나간다"
        if (c_hero == 5) { for j=0..9: print Ipeer[j] }
        else            { for j=0..9: print Epeer[j] }
        hscanf("%u", &imsi);
    } while (imsi > 10);
    if (imsi == 0) break;
    abil.peer = (unsigned char)(imsi - 1);
```

`Ipeer[10][7]` (H:44-54) 와 `Epeer[10][7]` (H:32-42) 는 작위 표시명 테이블. **알(c_hero==5) 만 Ipeer 사용, 나머지는 Epeer 사용** (알이 이탈리아계 캐릭터 — 추정). 실제 저장 값(`abil.peer` 0..9) 은 동일하게 인덱스로 저장한다.

### money 편집 (C:91, 115)
- `money` 는 전역 `unsigned long` (H:240) — 4바이트, little-endian.
- 표시는 `%lu`, 입력도 `%lu`.
- 위치: `money_addr + page = 0x06A1 + page` (4 bytes).

### 메뉴 입력 / 종료 (C:57-117)
- `i = 0` 입력하면 do-while 종료 후 저장.
- 다른 번호(1..11) 입력 시 해당 항목 편집.
- 잘못된 번호에 대한 default 처리 없음 — 무동작으로 다시 루프.

### 저장 (C:118-127)
```c
abil.pro = pro+100; ... abil.ned = ned+100;
fseek(fp, abil_addr[c_hero]+page, SEEK_SET);
fwrite(&abil, sizeof(Abil), 1, fp);
fseek(fp, money_addr+page, SEEK_SET);
fwrite(&money, sizeof(money), 1, fp);
```

### Python 재구현 시 주의
- `struct Abil` 직렬화 포맷 (little-endian): `<3H 8B` → 3개 uint16 + 8개 uint8 = 14 bytes.
- friendly 값 입력 시 `value + 100` 의 결과가 0..255 범위를 벗어나면 C 에서는 `(unsigned char)` 캐스트로 wrap. 원본 동작을 그대로 옮기려면 `& 0xFF`.
- `abil.peer` 입력 do-while 은 `imsi>10` 이므로 0..10 만 통과. 0 이면 변경 없음, 1..10 이면 `peer = imsi-1` (0..9).

---

## 8. person_edit() — 일반 인물 편집

HORIEDIT.C:130-320. 인물(NPC + 동료) 데이터를 이름으로 검색하여 편집.

### `struct Person` 레이아웃 (HORIEDIT.H:211-234)
| 오프셋 | 크기 | 필드 |
|---|---|---|
| 0  | 13 | `char fname[13]` 첫이름 |
| 13 | 13 | `char lname[13]` 성 |
| 26 | 2  | `char none[2]` 패딩 |
| 28 | 1  | `unsigned char command` 통솔 |
| 29 | 1  | `unsigned char sail`    항해 |
| 30 | 1  | `unsigned char know`    지식 |
| 31 | 1  | `unsigned char hunch`   직감 |
| 32 | 1  | `unsigned char tool`    공구(기술) |
| 33 | 1  | `unsigned char sword`   검술 |
| 34 | 1  | `unsigned char charm`   매력 |
| 35 | 1  | `unsigned char death`   행운 |
| 36 | 1  | `unsigned char l_sail`   항해 레벨 |
| 37 | 1  | `unsigned char l_battle` 전투 레벨 |
| 38 | 2  | `unsigned int  exp_sail`   항해 경험치 (uint16 LE) |
| 40 | 2  | `unsigned int  exp_battle` 전투 경험치 (uint16 LE) |
| 42 | 1  | `unsigned char age` 나이 |
| 43 | 1  | `unsigned char none1` 패딩 |
| 44 | 1  | `unsigned char pos` 소속 (`0xFF` 이면 항구 정착민) |
| 45 | 1  | `unsigned char port` 위치 항구 (0..129) |
| 46 | 2  | `unsigned char none2[2]` 패딩 |
| 48 | 1  | `struct babil ability` 비트필드 (td:1, ac:1, gu:1, mp:1, me:1, padding:3) |
| 49 | 1  | `char none3` 패딩 |

→ **sizeof(Person) = 50 bytes**. Person 영역 5951 / 50 ≈ 119 명.

### `struct babil` 비트필드 (H:199-208)
```c
struct babil {
    unsigned char td: 1;   // 점술
    unsigned char ac: 1;   // 회계
    unsigned char gu: 1;   // 구급(의술)
    unsigned char mp: 1;   // 지도 작성
    unsigned char me: 1;   // 검술 메뉴
    // 3비트 패딩
};
```

Turbo C/Borland 비트필드 패킹은 LSB-first. 즉 1바이트 안에서:
- bit 0 = td, bit 1 = ac, bit 2 = gu, bit 3 = mp, bit 4 = me, bit 5..7 = unused

### 검색 흐름 (C:147-217)
```c
char fname[13]={0}; char lname[13]={0};
char fname_flag=0, lname_flag=0;       // 일치(또는 검색 미사용) 플래그
char fname_exist=0, lname_exist=0;     // 입력값 유무

_hangulmode = true;
hgetln(fname, 12);  // 첫이름 입력 (한글, 최대 12자)
hgetln(lname, 12);  // 성   입력
_hangulmode = false;

if (fname[0]==0) fname_flag=1; else fname_exist=1;
if (lname[0]==0) lname_flag=1; else lname_exist=1;
if (fname_flag && lname_flag) return;   // 둘 다 비었으면 종료
```

→ 사용자가 비워둔 필드는 "체크 안 함" 으로 처리:
- 둘 다 입력: 두 이름 모두 일치하는 인물 찾기.
- 첫이름만 입력: 첫이름만 일치하면 OK.
- 성만 입력: 성만 일치하면 OK.
- 둘 다 비움: 즉시 return.

```c
offset = person_addr;       // 0x06A9
no = 0;
while (1) {
    fseek(fp, offset+page, SEEK_SET);
    fread(&person, sizeof(Person), 1, fp);
    if (person.pos == 0xFF) {
        // 항구 정착민이면 port 정보 미리 로드
        offset1 = port_addr + person.port*sizeof(Port) + page;
        fseek/read port;
    }
    if (fname_exist) { if (strcmp(fname, person.fname)==0) fname_flag=1; }
    if (lname_exist) { if (strcmp(lname, person.lname)==0) lname_flag=1; }
    if (fname_flag && lname_flag) {
        // 인물 정보 화면 표시 (no, fname, lname, command, sail, know, ..., ability, port)
        ...
        c=0;
        while (c!='n' && c!='N' && c!='y' && c!='Y') c=hgetche();
        if (c=='n' || c=='N') {
            if (fname_exist) fname_flag=0;
            if (lname_exist) lname_flag=0;
        }
        else break;     // y → 편집 진행
    }
    offset += sizeof(Person);
    if (offset > (0x1DE7 + page)) {
        "원하시는 데이타를 찾을수가 없습니다.";
        pause();
        return;
    }
    no++;
}
```

핵심:
- `no` 는 **0부터 시작하는 인물 번호**. 발견 시 표시("인물 번호 : Dec ##  Hex ##").
- "y" 를 누르면 break → 편집 루프로 진입.
- "n" 을 누르면 다음 매치 검색.
- 종료 조건은 `offset > 0x1DE7 + page` (Person 데이터 영역의 끝).

### 편집 루프 (C:219-315)

`while (i!=0)` 로 진입. 검색 break 직후 `i` 가 명시적으로 초기화되지 않지만 첫 do-while 의 `hscanf` 가 새 값을 덮어쓰므로 실질적 문제는 없다. (Python 재구현 시 `while True: ... if i == 0: break` 형태로 작성.)

화면 메뉴 (각 case 의 매핑):
| 입력값 | 필드 | 캐스트 |
|---|---|---|
| 0 | (저장 후 종료) | — |
| 1 | `person.fname[]` | hgetln(.., 12), 한글 모드 |
| 2 | `person.lname[]` | hgetln(.., 12), 한글 모드 |
| 3 | `person.command` | uint8 |
| 4 | `person.sail` | uint8 |
| 5 | `person.know` | uint8 |
| 6 | `person.hunch` | uint8 |
| 7 | `person.tool` | uint8 |
| 8 | `person.sword` | uint8 |
| 9 | `person.charm` | uint8 |
| 10 | `person.death` | uint8 ("1-100" 안내, 검증 없음) |
| 11 | `person.l_sail` | uint8 |
| 12 | `person.l_battle` | uint8 |
| 13 | `person.exp_sail` | uint16 (그대로 imsi 대입) |
| 14 | `person.exp_battle` | uint16 |
| 15 | `person.ability.td` | 0/1 (비트) |
| 16 | `person.ability.ac` | 0/1 |
| 17 | `person.ability.gu` | 0/1 |
| 18 | `person.ability.mp` | 0/1 |
| 19 | `person.ability.me` | 0/1 |
| 20 | `person.port` | uint8 (`person.pos==0xFF` 인 경우만), 항구 리스트 0..129 표시, do-while `imsi>129` |

`age` 필드 편집 코드는 주석 처리되어 있다 (C:289-290). 현재 버전(1.4)에서는 나이 편집 미지원.

### 저장 (C:317-318)
```c
fseek(fp, offset+page, SEEK_SET);
fwrite(&person, sizeof(Person), 1, fp);
```

검증: 검색 루프에서 매치 후 `c=='y'` 분기는 안쪽 `else break;` 로 빠져나오기 때문에 `offset += sizeof(Person)` 를 실행하지 않는다. 따라서 `offset` 은 발견된 인물의 시작 오프셋과 일치하여 fwrite 가 올바른 위치에 쓴다.

### Python 재구현 시 주의
- `struct Person` 직렬화 포맷 (little-endian, 패킹 없음, total 50 bytes):
  ```
  <13s 13s 2s 8B 2B 2H 4B 2s B B
  ```
  멤버 순서: `fname(13)`, `lname(13)`, `none(2)`, `command/sail/know/hunch/tool/sword/charm/death(8B)`, `l_sail/l_battle(2B)`, `exp_sail/exp_battle(2H)`, `age/none1/pos/port(4B)`, `none2(2s)`, `ability(1B 비트필드)`, `none3(1B)`.
- 검색 loop 종료 조건은 **항상 `0x1DE7 + page`** (헤더에 매크로 없음 — 코드 내 매직 넘버).
- `hgetln` 은 EUC-KR/KS_C_5601 한글 입력. Python 에서는 `input()` 결과를 EUC-KR 로 인코딩 후 13바이트 고정 길이 배열에 채워 넣음 (널 종료 포함).
- 비트필드 1바이트 = `(me<<4)|(mp<<3)|(gu<<2)|(ac<<1)|td`.

---

## 9. load / store / load4 / load5 — 파일 IO

선박 편집 함수가 사용하는 IO 헬퍼들. 본 분석가의 책임 범위는 IO 메커니즘만 명세한다.

### load(int sel) (C:322-333)
함대 슬롯 `sel` 의 ship1/ship2 와, 그 ship1 이 가리키는 ship3 데이터를 메모리로 읽음.
```c
offset1 = ship1_addr[c_hero] + page + (sel * sizeof(Ship1));
offset2 = ship2_addr        + page + (sel * sizeof(Ship2));
fseek/read ship1; fseek/read ship2;
offset3 = ship3_addr + page + (ship1.select * sizeof(Ship3));
fseek/read ship3;
```
- `ship1_addr` 은 주인공별로 다름 (6개 테이블).
- `ship2_addr` 와 `ship3_addr` 는 글로벌 (모든 주인공 공유).
- `ship3` 는 `ship_num` 이 아닌 **`ship1.select`** 가 인덱스. (ship3 가 진짜 선박 데이터 풀, ship1 이 포인터/장비 정보 — 선박 분석가 명세 참조.)
- 전역 변수 `offset1, offset2, offset3` 에 마지막 읽은 위치를 저장 → store() 가 그대로 사용.

### store(void) (C:335-343)
```c
fseek/write ship1 (at offset1);
fseek/write ship2 (at offset2);
fseek/write ship3 (at offset3);
```
load 후의 offset1/2/3 위치에 그대로 다시 쓴다. load → 편집 → store 가 페어로 사용되어야 함.

### load4(int sel) (C:346-351)
선박 원본 능력 데이터 `Ship4` 를 인덱스 `sel` 로 읽음.
```c
offset = page + ship4_addr + sizeof(Ship4) * sel;
fseek/read ship4;
```
- `offset` 은 전역 변수 (C:33). 다른 함수가 덮어쓸 수 있으므로 주의.

### load5(int sel) (C:353-357)
선박 원본 데이터 `Ship5` 를 인덱스 `sel` 로 읽음.
```c
fseek(s_addr + page + sizeof(Ship5)*sel); read ship5;
```
- 전역 offset 은 갱신되지 않음.

Python 재구현 시: `load4/load5` 는 함대 슬롯과 무관, 절대 인덱스(0..24) 로 선박 종류 풀에 접근.

---

## 10. 외부 데이터 파일 의존성 (NAME.TBL 등)

본 코드를 정독한 결과, **`horiedit.c` 자체는 `KOUKAI2.DAT` 외에 어떠한 외부 파일도 열지 않는다**. `fopen` 호출은 `main()` 의 한 곳뿐이다 (C:800).

문자열 테이블은 모두 헤더(HORIEDIT.H)에 정적 배열로 컴파일되어 있다:
- `Epeer[10][7]`, `Ipeer[10][7]` (작위명, H:32-54)
- `weapon_name[8][13]` (포 종류, H:92-100)
- `form_name[11][11]` (선수상/형태, H:113-124)

런타임에 채워지는 캐시:
- `hero[6][26]` ← `init_hori()` 에서 슬롯의 6명 주인공 이름 (Person.fname + " " + lname)
- `ship_name[25][18]` ← `init_hori()` 에서 슬롯의 25개 선박 원본 이름 (Ship5.name) — 단 `org_ship_edit()` 에서 사용자가 선박 이름을 변경하면 메모리 캐시도 갱신됨 (C:644)
- `port_name[130][15]` ← `sel_save()` 의 끝에서 130개 항구 이름 캐싱 (C:791-795)

**NAME.TBL 같은 별도 파일은 없다**. Python 재구현에도 별도 파일 의존성을 추가할 필요가 없다. 한글 폰트(KSS1)는 `registerkssfont(KSS1)` 로 등록 — hanlib 내부 리소스, Python 에서는 무시.

---

## 11. Python 구현가에게 전달할 핵심 주의사항

### 11.1 파일 IO 모델
- 파일 한 번만 열고(`open("koukai2.dat", "r+b")`) 프로그램 전체 수명 동안 fseek/fread/fwrite. Python 에서도 `f = open(...)` + `f.seek/read/write` 또는 mmap.
- 모든 다바이트 정수는 little-endian. `struct.pack/unpack` 의 `<` 포맷.

### 11.2 page 변수
```
PAGE = 33340
page = PAGE * (slot_index)       # slot_index = 0..9
```
`sel_save()` 에서 슬롯을 고른 후 한 번만 설정. 메인 메뉴 5번(다른 세이브 선택) 시 다시 갱신. 모든 데이터 접근은 `addr + page` (단, 파일 맨 앞의 `struct Init` 배열은 예외 — 슬롯 메타이므로 page 사용 안 함).

### 11.3 주인공 인덱스
- `c_hero` (0..5) 는 `c_addr+page = 0x06A8+page` 의 1바이트.
- `unsigned int c_hero` 라고 선언되어 있지만 1바이트만 읽으므로 Python 에서는 단일 바이트 정수로 다룬다 (`f.read(1)[0]`).
- `abil_addr[c_hero]` 와 `ship1_addr[c_hero]` 가 주인공별 데이터 위치.

### 11.4 친밀도 ±100
저장: 0..200 (uint8). 표시/입력: -100..+100. 변환 `display = stored - 100`, `stored = display + 100`. 입력 검증 없음 — 원본 동작을 그대로 옮긴다면 `& 0xFF` wrap.

### 11.5 Person 구조체 sizeof = 50 bytes
모든 필드가 1 또는 2 바이트라서 어떤 정렬이든 결과는 같다. 패킹 1로 직렬화.

### 11.6 검색 루프 종료 매직 넘버
`0x1DE7` (인물 데이터 영역의 끝) 은 헤더에 정의되어 있지 않다. Python 코드에는 이 종료 오프셋을 상수로 명시.

### 11.7 비트필드 (struct babil)
```
byte = (me<<4) | (mp<<3) | (gu<<2) | (ac<<1) | td
td = byte & 1
ac = (byte >> 1) & 1
gu = (byte >> 2) & 1
mp = (byte >> 3) & 1
me = (byte >> 4) & 1
```

### 11.8 한글 입력 처리
`hgetln(buf, n)` 은 EUC-KR/KS_C_5601 입력. 길이 제한:
- person.fname / lname: 12 (널 종료 포함 최대 13 바이트)
- ship3.ship_name: 14
- ship5.name: 18

### 11.9 잘못된 메뉴 입력
원본은 잘못된 번호에 대해 default 처리가 거의 없음. switch 의 default 가 없는 경우 무동작으로 다시 루프. do-while 의 종료 조건이 `i > N` 인 경우만 재입력 강제.

### 11.10 sel_save() 의 슬롯 0 베이스 메타데이터
파일 맨 앞 1 바이트는 미상의 헤더(읽거나 쓰지 않음). 그 뒤 `struct Init * 10` (slot=0..9). 각 슬롯의 풀 데이터는 별도로 `33340 * slot` 위치부터 시작. 정리:
```
slot_meta_offset(i) = 1 + 15 * i        # struct Init = 15 bytes
slot_data_base(i)   = 33340 * i
abs_addr(symbol, i) = symbol + slot_data_base(i)
```

### 11.11 c_addr / c_hero / abil_addr 의미 정리
- `c_addr (0x06A8)`: 슬롯 베이스 + 0x06A8 위치의 1 바이트가 **현재 주인공 번호(0..5)**.
- `c_hero`: 위 1바이트를 보관. abil_addr/ship1_addr 의 인덱스로 사용.
- `abil_addr[c_hero]`: 6명 주인공 각각의 `struct Abil` (14 bytes) 위치. 한 슬롯 안에 모든 주인공의 능력치가 동시에 저장되어 있고, 그 중 `c_hero` 가 가리키는 한 명만 "현재 주인공" 으로 적용된다.
- `money_addr (0x06A1)`: 4 bytes uint32 LE. 모든 주인공이 공유 (게임 진행 중 한 명만 활성이므로 단일 변수).

### 11.12 메뉴 키 입력
모든 메뉴는 `hscanf("%d", &x)` 로 정수만 받음. 화살표/ENTER/ESC 처리는 없음. 다만 person_edit 의 "이 데이타가 맞습니까?(y/n)" 만 `hgetche()` (단일 키) 사용. Python 에서는 `input()` 으로 한 줄 받고 정수 변환. 단일 키 응답 부분만 `msvcrt.getch()` (Windows) 또는 단순히 `input()` 한 줄로 대체.

### 11.13 horiedit 가 건드리지 않는 영역
- 파일 첫 1 바이트 (offset 0)
- 슬롯 데이터 영역 안에서 헤더에 명시되지 않은 모든 영역 (예: 0x06A8 직전, person 영역과 ship1 영역 사이의 0x1DE8..0x2243 등)
- ship1 안의 `select=0xFF` 슬롯 (빈 함대 슬롯) — 표시도 편집도 없음

이 영역들은 게임이 사용하는 다른 데이터(이벤트 플래그, 시간, 화물 인벤토리 등)일 가능성이 높지만, 본 에디터의 책임 영역이 아니다.
