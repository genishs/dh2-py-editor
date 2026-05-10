# 선박/함대 편집 — horiedit 의 hero_ship_edit, org_ship_edit 재구현.
# A 담당 common.py 의 EditorState 와 상수/구조체를 사용한다.

from horiedit_py.common import (
    EditorState,
    weapon_name,
    form_name,
    ship4_addr,
    s_addr,
    Ship4,
    Ship5,
    decode_kr,
    encode_kr_fixed,
)


def _read_int(prompt: str) -> int:
    """정수 한 줄 입력. 빈 입력/형식 오류 시 0 반환."""
    while True:
        try:
            s = input(prompt)
        except EOFError:
            return 0
        s = s.strip()
        if s == "":
            return 0
        try:
            return int(s)
        except ValueError:
            print("숫자를 입력해 주세요.")


def _read_line(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def hero_ship_edit(state: EditorState) -> None:
    if state.ship_num == 0:
        print("보유하고 있는 배가 한 척도 없습니다.")
        input("계속하려면 Enter 를 누르세요...")
        return

    while True:
        print()
        print("0) 빠져나간다")
        for i in range(state.ship_num):
            print(f"{i + 1}) 제 {i + 1}함선을 고친다")

        while True:
            sel = _read_int("고치기를 원하는 함선을 골라주세요 => ")
            if 0 <= sel <= state.ship_num:
                break
        if sel == 0:
            return
        sel -= 1

        state.load(sel)
        state.load4(state.ship3.ship_select)

        i = 1
        while i != 0:
            while True:
                ship1 = state.ship1
                ship2 = state.ship2
                ship3 = state.ship3
                ship4 = state.ship4

                print()
                print(" 0) 저장하고 나간다")
                print(f" 1) 현재 승무원      : {ship1.ccrew}")
                print(f" 2) 현재 선체        : {ship1.chull}")
                print(f" 3) 최대 선체        : {ship1.lhull}")
                print(f" 4) 현재 회전력      : {ship1.crudder}")
                print(f" 5) 현재 돛          : {ship1.csail}")
                print(f" 6) 현재 무기수      : {ship1.cnowea}")
                print(f" 7) 현재 컨디션      : {ship2.condition}")
                print(f"    카르고           : {ship3.cargo}")
                print(f" 8) 최대 적재 승무원 : {ship3.f_crew}")
                print(f" 9) 최대 적재 무기수 : {ship3.f_weap}")
                wi = ship1.cselwea - 0x10
                wname = weapon_name[wi] if 0 <= wi < len(weapon_name) else "?"
                print(f"10) 현재 무기        : {wname}")
                fi = ship2.ship_form
                fname = form_name[fi] if 0 <= fi < len(form_name) else "?"
                print(f"11) 현재 진형        : {fname}")
                ssel = ship3.ship_select
                sname = state.ship_name[ssel] if 0 <= ssel < 25 else "?"
                print(f"12) 현재 함선        : {sname}")
                print(f"13) 함선 이름        : {decode_kr(ship3.ship_name)}")
                print()
                i = _read_int("고치기를 원하는 데이터의 번호를 넣어 주세요 => ")
                if 0 <= i <= 13:
                    break

            ship1 = state.ship1
            ship2 = state.ship2
            ship3 = state.ship3
            ship4 = state.ship4

            if i == 1:
                print("이 메뉴의 수치는 8) 최대 적재 승무원의 수치를 초과할 수 없습니다.")
                imsi = _read_int("현재 승무원을 고칩니다. => ")
                ship1.ccrew = imsi & 0xFFFF
                if ship1.ccrew > ship3.f_crew:
                    ship1.ccrew = ship3.f_crew
            elif i == 2:
                print("이 메뉴의 수치는 3) 최대 선체의 수치를 초과할 수 없습니다.")
                imsi = _read_int("현재 선체를 고칩니다. => ")
                ship1.chull = imsi & 0xFF
                if ship1.chull > ship1.lhull:
                    ship1.chull = ship1.lhull
            elif i == 3:
                imsi = _read_int("최대 선체를 고칩니다. => ")
                ship1.lhull = imsi & 0xFF
                if ship1.chull > ship1.lhull:
                    ship1.chull = ship1.lhull
            elif i == 4:
                ssel = ship3.ship_select
                sname = state.ship_name[ssel] if 0 <= ssel < 25 else "?"
                print(f"이 메뉴의 수치는 {sname} 의 최고 회전력 수치를 초과할 수 없습니다.")
                imsi = _read_int("현재 회전력을 고칩니다. => ")
                ship1.crudder = imsi & 0xFF
                if ship1.crudder > ship4.lrudder:
                    ship1.crudder = ship4.lrudder
            elif i == 5:
                ssel = ship3.ship_select
                sname = state.ship_name[ssel] if 0 <= ssel < 25 else "?"
                print(f"이 메뉴의 수치는 {sname} 의 최고 돛 수치를 초과할 수 없습니다.")
                imsi = _read_int("현재 돛을 고칩니다. => ")
                ship1.csail = imsi & 0xFF
                if ship1.csail > ship4.lsail:
                    ship1.csail = ship4.lsail
            elif i == 6:
                print("이것은 10) 현재 무기에서 선택한 무기수만 영향을 받습니다.")
                print("또한 9) 최대 적재 무기수를 초과할 수 없습니다.")
                imsi = _read_int("현재 무기수를 고칩니다. => ")
                ship1.cnowea = imsi & 0xFF
                if ship1.cnowea > ship3.f_weap:
                    ship1.cnowea = ship3.f_weap
                if ship1.cselwea == 0x10:
                    ship1.cnowea = 0
            elif i == 7:
                imsi = _read_int("현재 컨디션을 고칩니다. => ")
                ship2.condition = imsi & 0xFF
            elif i == 8:
                ssel = ship3.ship_select
                sname = state.ship_name[ssel] if 0 <= ssel < 25 else "?"
                print(f"이 메뉴의 수치는 {sname} 의 최고 승무원 수치를 초과할 수 없습니다.")
                imsi = _read_int("최대 적재 승무원을 고칩니다. => ")
                ship3.f_crew = imsi & 0xFFFF
                if ship3.f_crew > (ship4.lcrew * 10):
                    ship3.f_crew = (ship4.lcrew * 10) & 0xFFFF
                if ship1.ccrew > ship3.f_crew:
                    ship1.ccrew = ship3.f_crew
            elif i == 9:
                ssel = ship3.ship_select
                sname = state.ship_name[ssel] if 0 <= ssel < 25 else "?"
                print(f"이 메뉴의 수치는 {sname} 의 최대 무기수를 초과할 수 없습니다.")
                imsi = _read_int("최대 적재 무기수를 고칩니다. => ")
                ship3.f_weap = imsi & 0xFF
                if ship3.f_weap > ship4.lnowea:
                    ship3.f_weap = ship4.lnowea
                if ship1.cnowea > ship3.f_weap:
                    ship1.cnowea = ship3.f_weap
            elif i == 10:
                while True:
                    print()
                    print("0) 고치지 않고 빠져나간다")
                    for j in range(8):
                        print(f"{j + 1}) {weapon_name[j]}")
                    print()
                    imsi = _read_int("현재 무기를 고칩니다. => ")
                    if imsi == 0:
                        break
                    imsi += 16
                    if imsi <= (8 + 16):
                        ship1.cselwea = (imsi - 1) & 0xFF
                    if ship1.cselwea == 0x10:
                        ship1.cnowea = 0
                    if imsi <= (8 + 16):
                        break
            elif i == 11:
                while True:
                    print()
                    print("0) 고치지 않고 빠져나간다")
                    for j in range(11):
                        print(f"{j + 1}) {form_name[j]}")
                    print()
                    imsi = _read_int("현재 진형을 고칩니다. => ")
                    if imsi == 0:
                        break
                    if imsi <= 11:
                        ship2.ship_form = (imsi - 1) & 0xFF
                        break
            elif i == 12:
                while True:
                    print()
                    print(" 0) 고치지 않고 빠져나간다")
                    for j in range(13):
                        if j == 0:
                            print(f"{j + 1:2d}) {state.ship_name[j]:<30s} {j + 2:2d}) {state.ship_name[j + 1]:<30s}")
                        elif j < 12:
                            left = state.ship_name[j * 2]
                            right = state.ship_name[j * 2 + 1]
                            print(f"{j * 2 + 1:2d}) {left:<30s} {j * 2 + 2:2d}) {right:<30s}")
                        else:  # j == 12
                            print(f"{j * 2 + 1:2d}) {state.ship_name[j * 2]:<30s}")
                    print()
                    imsi = _read_int("현재 함선을 고칩니다. => ")
                    if imsi == 0:
                        break
                    if imsi <= 25:
                        ship3.ship_select = (imsi - 1) & 0xFF
                        break
                state.load4(ship3.ship_select)
                state.load5(ship3.ship_select)
                ship4 = state.ship4
                ship5 = state.ship5
                bitmask1 = ship5.bform & 0xF0
                bitmask2 = ship3.bform & 0x0F
                ship3.bform = (bitmask1 | bitmask2) & 0xFF
                if ship1.crudder > ship4.lrudder:
                    ship1.crudder = ship4.lrudder
                if ship1.csail > ship4.lsail:
                    ship1.csail = ship4.lsail
                if ship1.cnowea > ship4.lnowea:
                    ship1.cnowea = ship4.lnowea
                if ship3.f_crew > (ship4.lcrew * 10):
                    ship3.f_crew = (ship4.lcrew * 10) & 0xFFFF
                if ship1.ccrew > ship3.f_crew:
                    ship1.ccrew = ship3.f_crew
                ship3.cargo = (ship4.capacity - ship3.f_weap - ship3.f_crew) & 0xFFFF
            elif i == 13:
                new_name = _read_line("함선의 이름을 고칩니다. => ")
                ship3.ship_name = encode_kr_fixed(new_name, 14)

            # 매 루프 끝의 cargo 재계산
            ship3.cargo = (ship4.capacity - ship3.f_weap - ship3.f_crew) & 0xFFFF

        state.store()


def org_ship_edit(state: EditorState) -> None:
    while True:
        print()
        while True:
            print(" 0) 나간다")
            for j in range(13):
                if j == 0:
                    print(f"{j + 1:2d}) {state.ship_name[j]:<30s} {j + 2:2d}) {state.ship_name[j + 1]:<30s}")
                elif j < 12:
                    left = state.ship_name[j * 2]
                    right = state.ship_name[j * 2 + 1]
                    print(f"{j * 2 + 1:2d}) {left:<30s} {j * 2 + 2:2d}) {right:<30s}")
                else:  # j == 12
                    print(f"{j * 2 + 1:2d}) {state.ship_name[j * 2]:<30s}")
            print()
            sel = _read_int("어느 배를 에디트 하시겠습니까? => ")
            if 0 <= sel <= 25:
                break
        if sel == 0:
            return
        sel -= 1

        # Ship4 + Ship5 를 page 결합 오프셋에서 read.
        offset4 = state.page + ship4_addr + Ship4.SIZE * sel
        state.fp.seek(offset4)
        ship4 = Ship4.from_bytes(state.fp.read(Ship4.SIZE))
        state.ship4 = ship4

        offset5 = s_addr + state.page + Ship5.SIZE * sel
        state.fp.seek(offset5)
        ship5 = Ship5.from_bytes(state.fp.read(Ship5.SIZE))
        state.ship5 = ship5

        while True:
            while True:
                print()
                print("0) 저장하고 나간다")
                print(f"1) 최대 회전력 : {ship4.lrudder}")
                print(f"2) 최대 돛     : {ship4.lsail}")
                print(f"3) 최대 승무원 : {ship4.lcrew * 10}")
                print(f"4) 필요 승무원 : {ship4.dcrew}")
                print(f"5) 최대 적재량 : {ship4.capacity}")
                print(f"6) 최대 무기수 : {ship4.lnowea}")
                print(f"7) 배이름      : {decode_kr(ship5.name)}")
                print()
                i = _read_int("고치기를 원하시는 데이터의 번호를 넣어 주세요 => ")
                if 0 <= i <= 7:
                    break
            if i == 0:
                break

            if i == 1:
                imsi = _read_int("최대 회전력을 고칩니다. => ")
                ship4.lrudder = imsi & 0xFF
                for k in range(state.ship_num):
                    state.load(k)
                    if state.ship3.ship_select == sel:
                        if state.ship1.crudder > ship4.lrudder:
                            state.ship1.crudder = ship4.lrudder
                            state.store()
            elif i == 2:
                imsi = _read_int("최대 돛을 고칩니다. => ")
                ship4.lsail = imsi & 0xFF
                for k in range(state.ship_num):
                    state.load(k)
                    if state.ship3.ship_select == sel:
                        if state.ship1.csail > ship4.lsail:
                            state.ship1.csail = ship4.lsail
                            state.store()
            elif i == 3:
                imsi = _read_int("최대 승무원을 고칩니다. => ")
                ship4.lcrew = (imsi // 10) & 0xFF
                for k in range(state.ship_num):
                    state.load(k)
                    if state.ship3.ship_select == sel:
                        if state.ship3.f_crew > (ship4.lcrew * 10):
                            state.ship3.f_crew = (ship4.lcrew * 10) & 0xFFFF
                            if state.ship1.ccrew > state.ship3.f_crew:
                                state.ship1.ccrew = state.ship3.f_crew
                            state.ship3.cargo = (
                                ship4.capacity - state.ship3.f_weap - state.ship3.f_crew
                            ) & 0xFFFF
                            state.store()
            elif i == 4:
                imsi = _read_int("필요 승무원을 고칩니다. => ")
                ship4.dcrew = imsi & 0xFF
            elif i == 5:
                imsi = _read_int("최대 적재량을 고칩니다. => ")
                ship4.capacity = imsi & 0xFFFF
                for k in range(state.ship_num):
                    state.load(k)
                    if state.ship3.ship_select == sel:
                        state.ship3.cargo = (
                            ship4.capacity - state.ship3.f_weap - state.ship3.f_crew
                        ) & 0xFFFF
                        state.store()
            elif i == 6:
                imsi = _read_int("최대 무기수를 고칩니다. => ")
                ship4.lnowea = imsi & 0xFF
                for k in range(state.ship_num):
                    state.load(k)
                    if state.ship3.ship_select == sel:
                        if state.ship3.f_weap > ship4.lnowea:
                            state.ship3.f_weap = ship4.lnowea
                            if state.ship1.cnowea > state.ship3.f_weap:
                                state.ship1.cnowea = state.ship3.f_weap
                            state.ship3.cargo = (
                                ship4.capacity - state.ship3.f_weap - state.ship3.f_crew
                            ) & 0xFFFF
                            state.store()
            elif i == 7:
                new_name = _read_line("배의 이름을 고칩니다. => ")
                ship5.name = encode_kr_fixed(new_name, 18)
                state.fp.seek(s_addr + state.page + Ship5.SIZE * sel)
                state.fp.write(ship5.to_bytes())
                state.fp.flush()
                state.ship_name[sel] = decode_kr(ship5.name)

        # 0 입력 시 Ship4 만 fwrite (Ship5 는 case 7 에서 처리됨).
        state.fp.seek(offset4)
        state.fp.write(ship4.to_bytes())
        state.fp.flush()
