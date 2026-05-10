"""hero_abil_edit / person_edit / sel_save / conferm_hero / init_hori / select_menu.

원본: HORIEDIT.C — 분석 A 명세 그대로 옮김.
"""

from __future__ import annotations

from .common import (
    EditorState,
    PAGE,
    PERSON_AREA_END,
    INIT_HEADER_OFFSET,
    Abil,
    Person,
    Init,
    Ship1,
    Ship2,
    Ship3,
    Ship5,
    Port,
    Epeer,
    Ipeer,
    abil_addr,
    money_addr,
    c_addr,
    person_addr,
    ship1_addr,
    ship2_addr,
    ship3_addr,
    s_addr,
    port_addr,
    decode_kr,
    encode_kr_fixed,
)


# ---------------------------------------------------------------------------
# 입력 헬퍼
# ---------------------------------------------------------------------------

def _ask_int(prompt: str, default: int = 0) -> int:
    """정수 입력. 공백/잘못된 입력 시 default."""
    try:
        s = input(prompt).strip()
        if not s:
            return default
        return int(s)
    except (ValueError, EOFError):
        return default


def _ask_str(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _pause() -> None:
    try:
        input("계속하려면 Enter 키를 누르세요...")
    except EOFError:
        pass


def _clear_screen() -> None:
    # 원본의 hclrscr 대용. 단순 줄바꿈으로 시각적 구분.
    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# init_hori (HORIEDIT.C:701-721)
# ---------------------------------------------------------------------------

def init_hori(state: EditorState) -> None:
    """슬롯의 6명 주인공 이름과 25개 선박 이름을 캐시."""
    # 6명 주인공 이름
    base = person_addr + state.page
    for i in range(6):
        data = state.read(base + Person.SIZE * i, Person.SIZE)
        ps = Person.from_bytes(data)
        fname = decode_kr(ps.fname)
        lname = decode_kr(ps.lname)
        state.hero[i] = f"{fname} {lname}"

    # 25개 선박 원본 이름
    base = s_addr + state.page
    for i in range(25):
        data = state.read(base + Ship5.SIZE * i, Ship5.SIZE)
        ship5 = Ship5.from_bytes(data)
        state.ship_name[i] = decode_kr(ship5.name)


# ---------------------------------------------------------------------------
# conferm_hero (HORIEDIT.C:677-699)
# ---------------------------------------------------------------------------

def conferm_hero(state: EditorState) -> None:
    """현재 주인공 번호 c_hero 갱신 + 보유 함대 수 ship_num 카운트."""
    # c_hero 는 1바이트
    raw = state.read(c_addr + state.page, 1)
    state.c_hero = raw[0] if raw else 0

    state.ship_num = 0
    while True:
        offset1 = ship1_addr[state.c_hero] + state.page + state.ship_num * Ship1.SIZE
        ship1 = Ship1.from_bytes(state.read(offset1, Ship1.SIZE))
        if ship1.select == 0xFF:
            break
        # ship2 는 형식상 읽고 (원본과 동일) 즉시 버린다
        offset2 = ship2_addr + state.page + state.ship_num * Ship2.SIZE
        _ship2 = Ship2.from_bytes(state.read(offset2, Ship2.SIZE))
        offset3 = ship3_addr + state.page + ship1.select * Ship3.SIZE
        ship3 = Ship3.from_bytes(state.read(offset3, Ship3.SIZE))
        if ship3.ship_select == 0xFF:
            break
        state.ship_num += 1


# ---------------------------------------------------------------------------
# sel_save (HORIEDIT.C:723-796)
# ---------------------------------------------------------------------------

def sel_save(state: EditorState) -> None:
    """세이브 슬롯 선택 메뉴.

    메뉴:
      0  = 프로그램 종료
      1..10 = 세이브 슬롯 선택 → 메인 메뉴로 진입
      11 = 게임 기본 설정 변경 (MAIN.EXE 편집)
    """
    while True:
        _clear_screen()
        print("\n                    대항해시대 II 세이브 에디터  Ver 0.1\n")
        print("    {:<11s}  {:<14s} {:<26s}".format("메 모", " 항 구", "주 인 공"))

        for i in range(10):
            data = state.read(INIT_HEADER_OFFSET + Init.SIZE * i, Init.SIZE)
            init = Init.from_bytes(data)
            if init.memo[0] == 0:
                print(f"{i+1:2d}) 데이터 없음")
                state.save_flg[i] = 0
            else:
                state.save_flg[i] = 1
                memo = decode_kr(init.memo)
                star = "*" if init.ending != 0 else " "
                if init.port == 0xFF:
                    port_disp = "해상"
                else:
                    off = i * PAGE + init.port * Port.SIZE + port_addr
                    port = Port.from_bytes(state.read(off, Port.SIZE))
                    port_disp = decode_kr(port.name)
                # 주인공 이름
                raw = state.read(c_addr + i * PAGE, 1)
                cur = raw[0] if raw else 0
                off = person_addr + Person.SIZE * cur + i * PAGE
                ps = Person.from_bytes(state.read(off, Person.SIZE))
                hero_name = f"{decode_kr(ps.fname)} {decode_kr(ps.lname)}"
                print(f"{i+1:2d}) {memo:<12s} {star}{port_disp:<14s} {hero_name:<26s}")

        print()
        print("11) 게임 기본 설정 변경")
        print(" 0) 프로그램 종료")
        print("\n원하시는 번호를 선택해 주세요 (1-10=슬롯, 11=설정, 0=종료)")
        sel = _ask_int(" => ", default=-1)

        # 0 → 종료
        if sel == 0:
            state.eXit = 1
            return

        # 1..10 슬롯
        if 1 <= sel <= 10:
            if state.save_flg[sel - 1] == 0:
                print("\n데이타가 없는 번호는 지정하실 수 없습니다.")
                print("다른 번호를 선택해 주십시오.")
                _pause()
                continue
            # 슬롯 확정
            state.page = PAGE * (sel - 1)
            init_hori(state)
            conferm_hero(state)
            # 130개 항구 이름 캐시
            base = state.page + port_addr
            for i in range(130):
                port = Port.from_bytes(state.read(base + Port.SIZE * i, Port.SIZE))
                state.port_name[i] = decode_kr(port.name)
            return

        # 11 → 게임 기본 설정 변경
        if sel == 11:
            try:
                from . import game_settings  # type: ignore
                if hasattr(game_settings, "game_settings_menu"):
                    game_settings.game_settings_menu(state)
                else:
                    print("(구현 대기 중)")
                    _pause()
            except ImportError:
                print("(구현 대기 중)")
                _pause()
            continue

        # 그 외 → 메뉴 재표시


# ---------------------------------------------------------------------------
# hero_abil_edit (HORIEDIT.C:38-128)
# ---------------------------------------------------------------------------

def hero_abil_edit(state: EditorState) -> None:
    """주인공 능력치 편집."""
    # 로드
    abil = Abil.from_bytes(state.read(abil_addr[state.c_hero] + state.page, Abil.SIZE))
    money_raw = state.read(money_addr + state.page, 4)
    money = int.from_bytes(money_raw, "little")

    # 친밀도 ±100 변환 (표시용)
    pro = abil.pro - 100
    spa = abil.spa - 100
    osm = abil.osm - 100
    eng = abil.eng - 100
    ita = abil.ita - 100
    ned = abil.ned - 100

    while True:
        _clear_screen()
        print(" 0) 저장하고 빠져나간다")
        print(f" 1) 무역 명성        : {abil.trade}")
        print(f" 2) 해적 명성        : {abil.robber}")
        print(f" 3) 모험 명성        : {abil.adven}")
        print(f" 4) 포르투갈    친밀 : {pro}")
        print(f" 5) 스페인      친밀 : {spa}")
        print(f" 6) 오스만      친밀 : {osm}")
        print(f" 7) 잉글랜드    친밀 : {eng}")
        print(f" 8) 이탈리아    친밀 : {ita}")
        print(f" 9) 네덜란드    친밀 : {ned}")
        peer_table = Ipeer if state.c_hero == 5 else Epeer
        peer_idx = abil.peer if 0 <= abil.peer < 10 else 0
        print(f"10) 작위            : {peer_table[peer_idx]}")
        print(f"11) 돈              : {money}")

        i = _ask_int("\n고치기를 원하는 번호를 입력해 주세요 => ", default=-1)

        if i == 0:
            break
        elif i == 1:
            abil.trade = _ask_int("무역 명성을 바꿉니다 => ", abil.trade) & 0xFFFF
        elif i == 2:
            abil.robber = _ask_int("해적 명성을 바꿉니다 => ", abil.robber) & 0xFFFF
        elif i == 3:
            abil.adven = _ask_int("모험 명성을 바꿉니다 => ", abil.adven) & 0xFFFF
        elif i == 4:
            pro = _ask_int("포르투갈 친밀도를 바꿉니다 => ", pro)
        elif i == 5:
            spa = _ask_int("스페인 친밀도를 바꿉니다 => ", spa)
        elif i == 6:
            osm = _ask_int("오스만 친밀도를 바꿉니다 => ", osm)
        elif i == 7:
            eng = _ask_int("잉글랜드 친밀도를 바꿉니다 => ", eng)
        elif i == 8:
            ita = _ask_int("이탈리아 친밀도를 바꿉니다 => ", ita)
        elif i == 9:
            ned = _ask_int("네덜란드 친밀도를 바꿉니다 => ", ned)
        elif i == 10:
            # 작위 do-while imsi>10
            while True:
                _clear_screen()
                print(" 0) 고치지 않고 빠져나간다")
                table = Ipeer if state.c_hero == 5 else Epeer
                for j in range(10):
                    print(f"{j+1:2d}) {table[j]}")
                imsi = _ask_int("\n원하시는 작위를 입력해 주세요 => ", default=99)
                if 0 <= imsi <= 10:
                    break
            if imsi != 0:
                abil.peer = (imsi - 1) & 0xFF
        elif i == 11:
            money = _ask_int("돈을 바꿉니다 => ", money) & 0xFFFFFFFF
        else:
            # 잘못된 번호: 무시하고 다시 루프
            pass

    # 친밀도 ±100 역변환 후 저장 (& 0xFF wrap)
    abil.pro = (pro + 100) & 0xFF
    abil.spa = (spa + 100) & 0xFF
    abil.osm = (osm + 100) & 0xFF
    abil.eng = (eng + 100) & 0xFF
    abil.ita = (ita + 100) & 0xFF
    abil.ned = (ned + 100) & 0xFF

    state.write(abil_addr[state.c_hero] + state.page, abil.to_bytes())
    state.write(money_addr + state.page, (money & 0xFFFFFFFF).to_bytes(4, "little"))


# ---------------------------------------------------------------------------
# person_edit (HORIEDIT.C:130-320)
# ---------------------------------------------------------------------------

def person_edit(state: EditorState) -> None:
    """일반 인물 편집. 이름 검색 → 매칭 인물 편집."""
    fname = _ask_str("찾고자 하는 사람의 처음 이름을 입력해 주세요\n => ").strip()
    lname = _ask_str("\n찾고자 하는 사람의 마지막 이름을 입력해 주세요\n => ").strip()

    fname_exist = bool(fname)
    lname_exist = bool(lname)
    if not fname_exist and not lname_exist:
        return

    # 입력 문자열을 EUC-KR 13바이트 고정 버퍼로
    fname_target = encode_kr_fixed(fname, 13) if fname_exist else b"\x00" * 13
    lname_target = encode_kr_fixed(lname, 13) if lname_exist else b"\x00" * 13

    # NUL 까지의 EUC-KR 부분 비교용
    def trim_nul(buf: bytes) -> bytes:
        nul = buf.find(b"\x00")
        return buf[:nul] if nul >= 0 else buf

    fname_target_t = trim_nul(fname_target)
    lname_target_t = trim_nul(lname_target)

    fname_flag = not fname_exist
    lname_flag = not lname_exist

    offset = person_addr
    no = 0
    person: Person = Person()

    while True:
        person = Person.from_bytes(state.read(offset + state.page, Person.SIZE))

        if fname_exist:
            if trim_nul(person.fname) == fname_target_t:
                fname_flag = True
        if lname_exist:
            if trim_nul(person.lname) == lname_target_t:
                lname_flag = True

        if fname_flag and lname_flag:
            _clear_screen()
            print(f"인물 번호   : Dec {no:2d}  Hex {no:2x}")
            print(f"처음 이름   : {decode_kr(person.fname)}")
            print(f"마지막 이름 : {decode_kr(person.lname)}")
            print(f"통솔        : {person.command}")
            print(f"항해        : {person.sail}")
            print(f"지식        : {person.know}")
            print(f"직감        : {person.hunch}")
            print(f"공구        : {person.tool}")
            print(f"검술        : {person.sword}")
            print(f"매력        : {person.charm}")
            print(f"행운        : {person.death}")
            print(f"항해 레벨   : {person.l_sail}")
            print(f"전투 레벨   : {person.l_battle}")
            print(f"항해 경험   : {person.exp_sail}")
            print(f"전투 경험   : {person.exp_battle}")
            print(f"능력        : 점술 {person.td} 회계 {person.ac} 구급 {person.gu} "
                  f"지도 {person.mp} 검술 {person.me}")
            if person.pos == 0xFF:
                pname = state.port_name[person.port] if 0 <= person.port < 130 else ""
                print(f"있는곳      : {pname}\n")

            ans = _ask_str("이 데이타가 맞습니까?(y/n) => ").strip().lower()
            c = ans[:1] if ans else ""
            while c not in ("y", "n"):
                ans = _ask_str("(y/n) => ").strip().lower()
                c = ans[:1] if ans else ""
            if c == "n":
                if fname_exist:
                    fname_flag = False
                if lname_exist:
                    lname_flag = False
            else:
                break  # 편집 진행

        offset += Person.SIZE
        if offset > (PERSON_AREA_END):
            print("\n원하시는 데이타를 찾을수가 없습니다.")
            _pause()
            return
        no += 1

    # 편집 루프
    while True:
        _clear_screen()
        print(" 0) 저장하고 빠져나간다")
        print(f" 1) 처음 이름   : {decode_kr(person.fname)}")
        print(f" 2) 마지막 이름 : {decode_kr(person.lname)}")
        print(f" 3) 통솔        : {person.command}")
        print(f" 4) 항해        : {person.sail}")
        print(f" 5) 지식        : {person.know}")
        print(f" 6) 직감        : {person.hunch}")
        print(f" 7) 공구        : {person.tool}")
        print(f" 8) 검술        : {person.sword}")
        print(f" 9) 매력        : {person.charm}")
        print(f"10) 행운        : {person.death}")
        print(f"11) 항해 레벨   : {person.l_sail}")
        print(f"12) 전투 레벨   : {person.l_battle}")
        print(f"13) 항해 경험   : {person.exp_sail}")
        print(f"14) 전투 경험   : {person.exp_battle}")
        print(f"능력            : 15)점술 {person.td} 16)회계 {person.ac} "
              f"17)구급 {person.gu} 18)지도 {person.mp} 19)검술 {person.me}")
        if person.pos == 0xFF:
            pname = state.port_name[person.port] if 0 <= person.port < 130 else ""
            print(f"20) 사는곳(항구): {pname}\n")

        i = _ask_int("고치기를 원하는 데이타의 번호를 넣어 주십시오 => ", default=-1)

        if i == 0:
            break
        elif i == 1:
            s = _ask_str("처음 이름을 바꿉니다.\n=> ").strip()
            person.fname = encode_kr_fixed(s, 13)
        elif i == 2:
            s = _ask_str("마지막 이름을 바꿉니다.\n=> ").strip()
            person.lname = encode_kr_fixed(s, 13)
        elif i == 3:
            person.command = _ask_int("통솔을 바꿉니다. => ", person.command) & 0xFF
        elif i == 4:
            person.sail = _ask_int("항해를 바꿉니다. => ", person.sail) & 0xFF
        elif i == 5:
            person.know = _ask_int("지식을 바꿉니다. => ", person.know) & 0xFF
        elif i == 6:
            person.hunch = _ask_int("직감을 바꿉니다. => ", person.hunch) & 0xFF
        elif i == 7:
            person.tool = _ask_int("공구를 바꿉니다. => ", person.tool) & 0xFF
        elif i == 8:
            person.sword = _ask_int("검술을 바꿉니다. => ", person.sword) & 0xFF
        elif i == 9:
            person.charm = _ask_int("매력을 바꿉니다. => ", person.charm) & 0xFF
        elif i == 10:
            person.death = _ask_int("행운을 바꿉니다. (1-100) => ", person.death) & 0xFF
        elif i == 11:
            person.l_sail = _ask_int("항해 레벨을 바꿉니다. => ", person.l_sail) & 0xFF
        elif i == 12:
            person.l_battle = _ask_int("전투 레벨을 바꿉니다. => ", person.l_battle) & 0xFF
        elif i == 13:
            person.exp_sail = _ask_int("항해 경험치를 바꿉니다. => ", person.exp_sail) & 0xFFFF
        elif i == 14:
            person.exp_battle = _ask_int("전투 경험치를 바꿉니다. => ", person.exp_battle) & 0xFFFF
        elif i == 15:
            v = _ask_int("점술 능력을 바꿉니다. (0-1) => ", person.td)
            person.set_bit("td", v)
        elif i == 16:
            v = _ask_int("회계 능력을 바꿉니다. (0-1) => ", person.ac)
            person.set_bit("ac", v)
        elif i == 17:
            v = _ask_int("구급 능력을 바꿉니다. (0-1) => ", person.gu)
            person.set_bit("gu", v)
        elif i == 18:
            v = _ask_int("지도작성 능력을 바꿉니다. (0-1) => ", person.mp)
            person.set_bit("mp", v)
        elif i == 19:
            v = _ask_int("검술 능력을 바꿉니다. (0-1) => ", person.me)
            person.set_bit("me", v)
        elif i == 20:
            if person.pos == 0xFF:
                while True:
                    _clear_screen()
                    for j in range(130):
                        sep = "\n" if (j % 4 == 3) else " "
                        print(f"{j:3d}) {state.port_name[j]:<14s}", end=sep)
                    if 130 % 4 != 0:
                        print()
                    imsi = _ask_int("\n\n현재 정착하는 곳을 바꿉니다 => ", default=999)
                    if imsi <= 129:
                        break
                person.port = imsi & 0xFF
        else:
            pass  # 잘못된 번호 무시

    # 저장 — offset 은 발견된 인물의 시작 오프셋
    state.write(offset + state.page, person.to_bytes())


# ---------------------------------------------------------------------------
# select_menu (HORIEDIT.C:652-675)
# ---------------------------------------------------------------------------

def select_menu(state: EditorState) -> None:
    """메인 메뉴. 0=처음 메뉴(sel_save)로, 1..5 분기."""
    while True:
        _clear_screen()
        print("0) 처음 메뉴로 돌아가기")
        print("1) 주인공 데이타 에디트")
        print("2) 인물 데이타 에디트")
        print("3) 주인공 선박 에디트")
        print("4) 오리지날 선박 에디트")
        print("5) 다른 세이브 번호 선택\n")

        sel = _ask_int("원하시는 메뉴의 번호를 넣어 주세요(0-5) => ", default=-1)

        if sel == 0:
            return
        elif sel == 1:
            hero_abil_edit(state)
        elif sel == 2:
            person_edit(state)
        elif sel == 3:
            try:
                from . import ship_data  # type: ignore
                if hasattr(ship_data, "hero_ship_edit"):
                    ship_data.hero_ship_edit(state)
                else:
                    print("(B 담당자 구현 대기 중)")
                    _pause()
            except ImportError:
                print("(B 담당자 구현 대기 중)")
                _pause()
        elif sel == 4:
            try:
                from . import ship_data  # type: ignore
                if hasattr(ship_data, "org_ship_edit"):
                    ship_data.org_ship_edit(state)
                else:
                    print("(B 담당자 구현 대기 중)")
                    _pause()
            except ImportError:
                print("(B 담당자 구현 대기 중)")
                _pause()
        elif sel == 5:
            sel_save(state)
        else:
            pass  # 잘못된 번호 무시
