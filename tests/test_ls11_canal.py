"""LS11 압축기 + 운하 패치 단위 시험 (analysis_P).

실행:  python -m unittest discover -s tests -v

합성 데이터 시험은 항상 돈다. `originalgame/` (저작권상 레포 제외) 의 실제 파일을 쓰는
시험은 파일이 없으면 건너뛴다.
"""
import os
import random
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from horiedit_py.data import canal, ls11, worldmap  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "originalgame")
ORIG = os.path.join(ROOT, "dh2_init", "WORLDMAP.LZW")
CAFE = os.path.join(ROOT, "koukai2", "worldmap.lzw")


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _synthetic_part(file_index: int, rng: random.Random) -> bytes:
    """1350 맵 표 + 임의 데이터. 운하 오프셋이 기대 맵 번호에 속하게 표를 맞춘 합성 대륙 파일."""
    size = 0x4400
    body = bytearray(rng.randrange(256) for _ in range(size - worldmap.DATA_BASE))
    # {맵 번호: (시작 오프셋, 길이)} — 실제 파일의 값과 같게
    if file_index == 0:
        pivots = {525: (0x3E54, 80)}
    elif file_index == 2:
        pivots = {736: (0x3F65, 35), 766: (0x40CF, 53)}
    else:
        pivots = {}
    # 표: 단조 증가. 피벗 맵은 지정 위치에서 시작, 나머지는 사이를 균등 분할
    offs = [0] * worldmap.NUM_MAPS
    cur = 0
    for i in range(worldmap.NUM_MAPS):
        step = 1
        if i in pivots:
            cur = pivots[i][0] - worldmap.DATA_BASE
            step = pivots[i][1]
        offs[i] = cur
        cur += step
    part = bytearray(struct.pack("<%dH" % worldmap.NUM_MAPS, *offs)) + body
    return bytes(part)


def _synthetic_parts(closed=True, seed=1):
    rng = random.Random(seed)
    parts = [bytearray(_synthetic_part(i, rng)) for i in range(3)]
    for c in canal.CANALS.values():
        for e in c.edits:
            parts[e.file][e.offset] = e.before if closed else e.after
    for e in canal.CAFE_EXTRA_EDITS:
        parts[e.file][e.offset] = e.before
    return [bytes(p) for p in parts]


class Ls11CodecTest(unittest.TestCase):
    def _roundtrip(self, parts, **kw):
        blob = ls11.encode_pack(parts, **kw)
        self.assertEqual(ls11.decode_pack(blob), list(parts))
        return blob

    def test_roundtrip_random_and_repetitive(self):
        rng = random.Random(7)
        parts = [
            bytes(rng.randrange(256) for _ in range(3000)),
            bytes([0]) * 5000,                      # 겹치는 LZ 복사
            (b"abcabcabcX" * 400),
            bytes(rng.choice(b"\x00\x0f\xff") for _ in range(4000)),
        ]
        self._roundtrip(parts)
        self._roundtrip(parts, window=0)            # 리터럴만

    def test_roundtrip_tiny(self):
        self._roundtrip([b"A"])
        self._roundtrip([b"AB", b"", ][:1])
        self._roundtrip([bytes(range(256))])

    def test_header_layout(self):
        blob = ls11.encode_pack([b"hello world hello wor"])
        self.assertEqual(blob[:4], b"LS11")
        self.assertEqual(blob[4:16], b"\x00" * 12)
        comp, exp, start = struct.unpack_from(">III", blob, 0x110)
        self.assertEqual((exp, start), (21, 0x110 + 12 + 4))
        self.assertEqual(start + comp, len(blob))
        self.assertEqual(struct.unpack_from(">I", blob, 0x11C)[0], 0)

    def test_lz_actually_compresses(self):
        data = b"\x00" * 10000
        with_lz = ls11.encode_pack([data])
        no_lz = ls11.encode_pack([data], window=0)
        self.assertLess(len(with_lz), len(no_lz))
        self.assertTrue(ls11.uses_lz(with_lz))
        self.assertFalse(ls11.uses_lz(no_lz))

    def test_custom_dictionary_kept(self):
        d = bytes(reversed(range(256)))
        blob = ls11.encode_pack([b"xyz" * 50], dictionary=d)
        self.assertEqual(blob[0x10:0x110], d)
        self.assertEqual(ls11.decode_pack(blob), [b"xyz" * 50])

    def test_bad_input_rejected(self):
        with self.assertRaises(ls11.Ls11Error):
            ls11.decode_pack(b"NOPE" + b"\x00" * 400)
        blob = ls11.encode_pack([b"abcdefg" * 20])
        with self.assertRaises(ls11.Ls11Error):
            ls11.decode_pack(blob[:-5])             # 데이터 잘림
        with self.assertRaises(ls11.Ls11Error):
            ls11.encode_pack([b"a"], dictionary=b"\x00" * 256)

    @unittest.skipUnless(os.path.exists(ORIG), "원본 WORLDMAP.LZW 없음")
    def test_original_byte_identical(self):
        raw = _read(ORIG)
        dic, _ = ls11.parse_header(raw)
        parts = ls11.decode_pack(raw)
        self.assertEqual([len(p) for p in parts], [25394, 21973, 23907])
        self.assertEqual(ls11.encode_pack(parts, dictionary=dic), raw)

    @unittest.skipUnless(os.path.exists(CAFE), "koukai2/worldmap.lzw 없음")
    def test_cafe_patch_byte_identical_literal_only(self):
        raw = _read(CAFE)
        parts = ls11.decode_pack(raw)
        self.assertEqual(ls11.encode_pack(parts, window=0), raw)


class CanalSyntheticTest(unittest.TestCase):
    def test_state_closed_open_unknown(self):
        closed = _synthetic_parts(True)
        self.assertEqual(canal.canal_states(closed), {"suez": canal.CLOSED, "panama": canal.CLOSED})
        opened = _synthetic_parts(False)
        self.assertEqual(canal.canal_states(opened), {"suez": canal.OPEN, "panama": canal.OPEN})

    def test_open_then_restore_roundtrip(self):
        closed = _synthetic_parts(True)
        for key in ("suez", "panama"):
            op = canal.set_canal(closed, key, canal.OPEN)
            self.assertEqual(canal.canal_state(op, key), canal.OPEN)
            back = canal.set_canal(op, key, canal.CLOSED)
            self.assertEqual(back, closed)

    def test_independent(self):
        closed = _synthetic_parts(True)
        op = canal.set_canal(closed, "suez", canal.OPEN)
        self.assertEqual(canal.canal_state(op, "suez"), canal.OPEN)
        self.assertEqual(canal.canal_state(op, "panama"), canal.CLOSED)
        self.assertEqual(op[2], closed[2])          # 파나마 파일은 그대로
        op2 = canal.set_canal(op, "panama", canal.OPEN)
        self.assertEqual(op2[0], op[0])             # 수에즈 파일은 그대로
        # 순서 무관
        other = canal.set_canal(canal.set_canal(closed, "panama", canal.OPEN), "suez", canal.OPEN)
        self.assertEqual(other, op2)

    def test_only_canal_bytes_change(self):
        closed = _synthetic_parts(True)
        op = canal.set_canal(closed, "suez", canal.OPEN)
        changed = {(i, j) for i in range(3) for j in range(len(closed[i])) if closed[i][j] != op[i][j]}
        self.assertEqual(changed, {(e.file, e.offset) for e in canal.SUEZ.edits})

    def test_restore_leaves_other_edits_alone(self):
        # 카페 패치처럼: 운하 둘 개통 + 제주·울릉·독도 변경
        parts = [bytearray(p) for p in _synthetic_parts(False)]
        for e in canal.CAFE_EXTRA_EDITS:
            parts[e.file][e.offset] = e.after
        parts = [bytes(p) for p in parts]
        r = canal.set_canal(parts, "suez", canal.CLOSED)
        self.assertEqual(canal.canal_state(r, "suez"), canal.CLOSED)
        self.assertEqual(canal.canal_state(r, "panama"), canal.OPEN)
        for e in canal.CAFE_EXTRA_EDITS:
            self.assertEqual(r[e.file][e.offset], e.after)

    def test_partial_is_unknown_and_refused(self):
        for key, victim in (("suez", canal.SUEZ.edits[3]), ("panama", canal.PANAMA.edits[0])):
            parts = [bytearray(p) for p in _synthetic_parts(True)]
            parts[victim.file][victim.offset] = victim.after   # 한 바이트만 후
            parts = [bytes(p) for p in parts]
            self.assertEqual(canal.canal_state(parts, key), canal.UNKNOWN)
            for mode in (canal.OPEN, canal.CLOSED):
                with self.assertRaises(canal.CanalError):
                    canal.set_canal(parts, key, mode)

    def test_foreign_value_is_unknown(self):
        parts = [bytearray(p) for p in _synthetic_parts(True)]
        e = canal.SUEZ.edits[2]
        parts[e.file][e.offset] = 0x55                          # 전도 후도 아닌 값
        self.assertEqual(canal.canal_state([bytes(p) for p in parts], "suez"), canal.UNKNOWN)

    def test_wrong_map_layout_is_unknown(self):
        # 바이트는 맞아도 오프셋 표가 다른 판(그 오프셋이 다른 맵 소속)이면 UNKNOWN
        parts = [bytearray(p) for p in _synthetic_parts(True)]
        parts[0][0:2700] = struct.pack("<1350H", *range(1350))
        self.assertEqual(canal.canal_state([bytes(p) for p in parts], "suez"), canal.UNKNOWN)

    def test_input_not_mutated_and_bad_args(self):
        closed = _synthetic_parts(True)
        snap = list(closed)
        canal.set_canal(closed, "suez", canal.OPEN)
        self.assertEqual(closed, snap)
        with self.assertRaises(canal.CanalError):
            canal.set_canal(closed, "suez", "bogus")
        with self.assertRaises(canal.CanalError):
            canal.set_canal(closed, "nowhere", canal.OPEN)

    def test_short_parts_unknown(self):
        self.assertEqual(canal.canal_state([b"", b"", b""], "suez"), canal.UNKNOWN)


class CanalFileTest(unittest.TestCase):
    def test_apply_to_file_with_backup(self):
        closed = _synthetic_parts(True)
        blob = ls11.encode_pack(closed)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "WORLDMAP.LZW")
            with open(path, "wb") as f:
                f.write(blob)
            self.assertEqual(canal.file_canal_states(path)["suez"], canal.CLOSED)
            self.assertEqual(canal.apply_canal_to_file(path, "suez", canal.OPEN), canal.OPEN)
            self.assertTrue(os.path.exists(path + canal.BACKUP_SUFFIX))
            self.assertEqual(_read(path + canal.BACKUP_SUFFIX), blob)
            st = canal.file_canal_states(path)
            self.assertEqual(st, {"suez": canal.OPEN, "panama": canal.CLOSED})
            # 두 번째 전환에서도 백업은 최초 원본 그대로
            canal.apply_canal_to_file(path, "panama", canal.OPEN)
            self.assertEqual(_read(path + canal.BACKUP_SUFFIX), blob)
            # 복원하면 해제본이 원래와 동일
            canal.apply_canal_to_file(path, "suez", canal.CLOSED)
            canal.apply_canal_to_file(path, "panama", canal.CLOSED)
            _d, parts = canal.read_worldmap(path)
            self.assertEqual(parts, closed)
            self.assertFalse(os.path.exists(path + ".canal-tmp"))

    def test_apply_refuses_unknown_and_leaves_file(self):
        parts = [bytearray(p) for p in _synthetic_parts(True)]
        v = canal.SUEZ.edits[3]
        parts[v.file][v.offset] = v.after
        blob = ls11.encode_pack([bytes(p) for p in parts])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "WORLDMAP.LZW")
            with open(path, "wb") as f:
                f.write(blob)
            with self.assertRaises(canal.CanalError):
                canal.apply_canal_to_file(path, "suez", canal.OPEN)
            self.assertEqual(_read(path), blob)
            self.assertFalse(os.path.exists(path + canal.BACKUP_SUFFIX))

    def test_noop_when_already_in_state(self):
        blob = ls11.encode_pack(_synthetic_parts(True))
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "WORLDMAP.LZW")
            with open(path, "wb") as f:
                f.write(blob)
            self.assertEqual(canal.apply_canal_to_file(path, "suez", canal.CLOSED), canal.CLOSED)
            self.assertEqual(_read(path), blob)
            self.assertFalse(os.path.exists(path + canal.BACKUP_SUFFIX))


@unittest.skipUnless(os.path.exists(ORIG) and os.path.exists(CAFE), "원본/패치본 파일 없음")
class CanalRealFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o = ls11.decode_pack(_read(ORIG))
        cls.k = ls11.decode_pack(_read(CAFE))

    def test_before_values_match_article_in_original(self):
        for c in canal.CANALS.values():
            for e in c.edits:
                self.assertEqual(self.o[e.file][e.offset], e.before, (c.key, hex(e.offset)))
        self.assertEqual(canal.canal_states(self.o), {"suez": canal.CLOSED, "panama": canal.CLOSED})

    def test_cafe_patch_is_open_for_both(self):
        self.assertEqual(canal.canal_states(self.k), {"suez": canal.OPEN, "panama": canal.OPEN})

    def test_diff_is_exactly_article_edits(self):
        diff = {(i, j): (self.o[i][j], self.k[i][j])
                for i in range(3) for j in range(len(self.o[i])) if self.o[i][j] != self.k[i][j]}
        exp = {(e.file, e.offset): (e.before, e.after)
               for e in canal.SUEZ.edits + canal.PANAMA.edits + canal.CAFE_EXTRA_EDITS}
        self.assertEqual(diff, exp)

    def test_open_original_equals_cafe_in_canal_maps(self):
        p = canal.set_canal(canal.set_canal(self.o, "suez", canal.OPEN), "panama", canal.OPEN)
        for f, idx in ((0, 525), (2, 736), (2, 766)):
            s, e = worldmap.map_range(p[f], idx)
            self.assertEqual(p[f][s:e], self.k[f][s:e])

    def test_scenario_original_open_restore(self):
        op = canal.set_canal(self.o, "suez", canal.OPEN)
        self.assertEqual(canal.canal_state(op, "suez"), canal.OPEN)
        self.assertEqual(canal.set_canal(op, "suez", canal.CLOSED), self.o)

    def test_cafe_restore_suez_keeps_jeju(self):
        r = canal.set_canal(self.k, "suez", canal.CLOSED)
        self.assertEqual(canal.canal_state(r, "suez"), canal.CLOSED)
        self.assertEqual(canal.canal_state(r, "panama"), canal.OPEN)
        for e in canal.CAFE_EXTRA_EDITS:
            self.assertEqual(r[e.file][e.offset], e.after)
        diff = {(i, j) for i in range(3) for j in range(len(self.k[i])) if self.k[i][j] != r[i][j]}
        self.assertEqual(diff, {(e.file, e.offset) for e in canal.SUEZ.edits})

    def test_real_file_roundtrip_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "WORLDMAP.LZW")
            raw = _read(ORIG)
            with open(path, "wb") as f:
                f.write(raw)
            canal.apply_canal_to_file(path, "suez", canal.OPEN)
            canal.apply_canal_to_file(path, "suez", canal.CLOSED)
            self.assertEqual(_read(path), raw)   # 원본 사전·LZ 규칙이라 바이트까지 동일
            self.assertEqual(_read(path + canal.BACKUP_SUFFIX), raw)

    def test_map_structure_all_blocks(self):
        for part in self.o + self.k:
            for i in range(worldmap.NUM_MAPS):
                worldmap.parse_map(part, i)   # 길이 규칙 위반이면 예외


if __name__ == "__main__":
    unittest.main()
