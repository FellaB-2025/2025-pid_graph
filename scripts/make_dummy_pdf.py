"""Generate the SYNTHETIC per-unit P&ID PDFs for the dummy unit U-100.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

No real Aconex file is available on this machine. Each PDF imitates the shape of one - a
transmittal cover page followed by one page per drawing, each with a title block in the
bottom-right corner - so the title-block reader, the revision map, the re-issue diff and the
pipeline wiring can be tested. Replace with the real file and re-run; the reader's region and
regexes may need adjusting to the project's title-block layout (a one-time calibration).

Since v1.3 the drawing pages are no longer empty: they carry simple ISA-style P&IDs so that
vision extraction (PIDKG_UPGRADE.md, Phase 3) has something to read. The sheets are drawn
from the dummy instrument index, the pid_audit topology export and the C&E:

  * every row of data/pid_audit_U100_topology.csv is drawn, in that order, on that sheet;
  * the planted discrepancies are kept: TT-1003 (index only) is NOT drawn, FT-1006 (not in
    the index) IS drawn on PID-100-002, XV-1002 is drawn on PID-100-001 although the index
    says PID-100-002, and PT-1001D (C&E only) is not drawn;
  * added for the v1.3 work, and in no register: a few UNTAGGED in-line fittings, the DCS
    controllers of the three loops, the drawn signal lines, line sizes and services, and two
    unnumbered utility lines on PID-100-003. All of it is dummy data.

Nothing is drawn or written inside the title-block region other than the title block itself,
so the title-block pass and the v1.2 graph are unchanged.

    python scripts/make_dummy_pdf.py            -> data/U100-PIDS-TX-0042.pdf  (first issue)
    python scripts/make_dummy_pdf.py --reissue  -> data/U100-PIDS-TX-0057.pdf  (PID-100-001 revised C -> D)
    python scripts/make_dummy_pdf.py --all      -> both, plus data/U100-PIDS-DRAWN-CONTENT.json

The JSON file lists what each sheet shows (drawn_content()). It is the answer key for the
drawings, for use when a topology gold set is built; it is not read by any loader.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
FIRST = [("PID-100-001", "C", "FEED GAS INLET - INLET KO DRUM V-1002"),
         ("PID-100-002", "B", "FEED GAS INLET - PRESSURE CONTROL AND EXPORT"),
         ("PID-100-003", "A", "FEED GAS INLET - UTILITY CONNECTIONS")]
REISSUE = [("PID-100-001", "D", "FEED GAS INLET - INLET KO DRUM V-1002"),
           ("PID-100-002", "B", "FEED GAS INLET - PRESSURE CONTROL AND EXPORT"),
           ("PID-100-003", "A", "FEED GAS INLET - UTILITY CONNECTIONS")]

W, H = 1191, 842            # A3 landscape in points
BLACK, WHITE = (0, 0, 0), (1, 1, 1)
PIPE, THIN = 1.8, 0.7       # process line / symbol and impulse line widths
R = 17                      # instrument bubble radius
FONT = "helv"


class Sheet:
    """Draws one drawing body and records what it drew. With page=None it only records."""

    def __init__(self, page=None):
        self.page = page
        self.content = {"equipment": [], "components": [], "instruments": [], "lines": [], "signals": [],
                        "off_page_connectors": [], "boundaries": [], "notes": []}
        self._n = {"V": 0, "L": 0, "OPC": 0, "B": 0}
        self._tops: dict[str, tuple] = {}       # valve id -> top of its actuator, where a signal lands

    # ---- low-level drawing (no-ops when only recording) -------------------
    def _id(self, prefix: str) -> str:
        self._n[prefix] += 1
        return f"{prefix}{self._n[prefix]}"

    def _poly(self, pts, width=THIN, dashes=None, fill=None, close=False):
        if self.page is None:
            return
        sh = self.page.new_shape()
        sh.draw_polyline([pymupdf.Point(*p) for p in pts])
        sh.finish(width=width, color=BLACK, fill=fill, dashes=dashes, closePath=close)
        sh.commit()

    def _circle(self, x, y, r, fill=WHITE, width=THIN):
        if self.page is None:
            return
        sh = self.page.new_shape()
        sh.draw_circle(pymupdf.Point(x, y), r)
        sh.finish(width=width, color=BLACK, fill=fill)
        sh.commit()

    def _text(self, x, y, s, size=7.5, align="c"):
        """Text with its baseline at y; align 'c' centres on x, 'l' starts at x, 'r' ends at x."""
        if self.page is None:
            return
        w = pymupdf.get_text_length(s, fontname=FONT, fontsize=size)
        x0 = x - w / 2 if align == "c" else (x - w if align == "r" else x)
        self.page.insert_text((x0, y), s, fontsize=size, fontname=FONT)

    def _arrow(self, x, y, direction):
        dx, dy = {"r": (1, 0), "l": (-1, 0), "u": (0, -1), "d": (0, 1)}[direction]
        tip = (x + 6 * dx, y + 6 * dy)
        a = (x - 3 * dx - 3.5 * dy, y - 3 * dy - 3.5 * dx)
        b = (x - 3 * dx + 3.5 * dy, y - 3 * dy + 3.5 * dx)
        self._poly([tip, a, b], fill=BLACK, close=True)

    # ---- process lines -----------------------------------------------------
    def pipe(self, pts, arrows=()):
        """A process line as drawn; arrows = [(x, y, 'r'|'l'|'u'|'d'), ...]."""
        self._poly(pts, width=PIPE)
        for x, y, d in arrows:
            self._arrow(x, y, d)

    def line(self, line_no, size, service, frm, to, order, label_at, path=None):
        """Record one line. order = ids along the flow, taps included; path = the in-line ones only."""
        x, y = label_at
        label = "  ".join(s for s in (line_no, size, service) if s)
        self._text(x, y, label, size=7, align="l")
        self.content["lines"].append({"id": self._id("L"), "line_no": line_no, "size": size, "service": service,
                                      "from": frm, "to": to, "order": list(order),
                                      "path": list(path if path is not None else order), "flow_direction": "shown"})

    # ---- equipment, boundaries, off-page connectors -------------------------
    def vessel(self, tag, name, x0, y0, x1, y1, label_at):
        if self.page is not None:
            h = 22
            sh = self.page.new_shape()
            sh.draw_rect(pymupdf.Rect(x0, y0 + h, x1, y1 - h))
            sh.finish(width=1.2, color=BLACK, fill=WHITE)
            sh.draw_bezier(pymupdf.Point(x0, y0 + h), pymupdf.Point(x0, y0 - h * 0.3), pymupdf.Point(x1, y0 - h * 0.3), pymupdf.Point(x1, y0 + h))
            sh.draw_bezier(pymupdf.Point(x0, y1 - h), pymupdf.Point(x0, y1 + h * 0.3), pymupdf.Point(x1, y1 + h * 0.3), pymupdf.Point(x1, y1 - h))
            sh.finish(width=1.2, color=BLACK, fill=WHITE)
            sh.commit()
        self._text(label_at[0], label_at[1], tag, size=9, align="l")
        self._text(label_at[0], label_at[1] + 11, name, size=7, align="l")
        self.content["equipment"].append({"id": tag, "tag": tag, "kind": "pressure_vessel", "name": name, "text": [tag]})

    def flag(self, x, y, lines, points, *, kind, direction, tag=None, name="", other_drawing="", other_item="", line_no=""):
        """A flag on the end of a line at (x, y) on its flat side. points = 'r' or 'l' (where the tip is)."""
        length, half = 86, 13
        s = 1 if points == "r" else -1
        if direction == "in":      # flow arrives: the tip touches the line
            body = [(x, y), (x + s * 12, y - half), (x + s * length, y - half), (x + s * length, y + half), (x + s * 12, y + half)]
            cx = x + s * (length + 8) / 2
        else:                      # flow leaves: the tip points away from the line
            body = [(x, y - half), (x + s * (length - 12), y - half), (x + s * length, y), (x + s * (length - 12), y + half), (x, y + half)]
            cx = x + s * (length - 8) / 2
        self._poly(body, width=1.0, fill=WHITE, close=True)
        for i, t in enumerate(lines):
            self._text(cx, y - 2 + i * 8.5 - (len(lines) - 1) * 4.25 + 2.5, t, size=6.5)
        words = [w for t in lines for w in t.split()]
        if kind == "boundary":
            ident = tag or self._id("B")
            self.content["boundaries"].append({"id": ident, "tag": tag, "name": name or " ".join(lines),
                                               "direction": "source" if direction == "in" else "sink", "text": words})
        else:
            ident = self._id("OPC")
            self.content["off_page_connectors"].append({"id": ident, "direction": direction, "other_drawing": other_drawing,
                                                        "other_item": other_item, "line_no": line_no, "name": " / ".join(lines), "text": words})
        return ident

    # ---- in-line components (all on horizontal runs) ------------------------
    def valve(self, x, y, kind, *, tag=None, actuator=None, fail=None, normal=None, label="below"):
        """Bow-tie at (x, y) on a horizontal line. Returns the id used in line order."""
        a, b = 10, 7
        left, right = [(x - a, y - b), (x - a, y + b), (x, y)], [(x + a, y - b), (x + a, y + b), (x, y)]
        self._poly(left, fill=BLACK if kind == "check_valve" else WHITE, close=True, width=1.0)
        self._poly(right, fill=WHITE, close=True, width=1.0)
        if kind == "ball_valve":
            self._circle(x, y, 3.5, width=1.0)
        top = y
        if actuator:
            self._poly([(x, y), (x, y - 17)], width=1.0)
            if actuator == "diaphragm":            # dome: modulating control valve
                if self.page is not None:
                    sh = self.page.new_shape()
                    sh.draw_bezier(pymupdf.Point(x - 11, y - 17), pymupdf.Point(x - 11, y - 31), pymupdf.Point(x + 11, y - 31), pymupdf.Point(x + 11, y - 17))
                    sh.draw_line(pymupdf.Point(x - 11, y - 17), pymupdf.Point(x + 11, y - 17))
                    sh.finish(width=1.0, color=BLACK, fill=WHITE)
                    sh.commit()
                top = y - 28
            else:                                   # box marked S: solenoid-operated on/off valve
                self._poly([(x - 8, y - 33), (x + 8, y - 33), (x + 8, y - 17), (x - 8, y - 17)], fill=WHITE, close=True, width=1.0)
                self._text(x, y - 22.5, "S", size=7)
                top = y - 33
        ly = y + b + 10 if label == "below" else top - 5
        text = []
        if tag:
            self._text(x, ly, tag, size=7.5)
            text.append(tag)
        extra = fail or normal
        if extra:
            self._text(x, ly + 9 if label == "below" else ly - 9, extra, size=6.5)
        ident = tag or self._id("V")
        rec = {"id": ident, "tag": tag, "kind": kind, "text": text}
        if actuator:
            rec["actuator"] = "pneumatic" if actuator == "diaphragm" else "solenoid"
        if fail:
            rec["fail_position"] = fail
        if normal:
            rec["normal_position"] = normal
        self.content["components"].append(rec)
        self._tops[ident] = (x, top)
        return ident

    def reducer(self, x, y, narrow="r"):
        s = 1 if narrow == "r" else -1
        self._poly([(x - s * 8, y - 7), (x - s * 8, y + 7), (x + s * 8, y + 3), (x + s * 8, y - 3)], fill=WHITE, close=True, width=1.0)
        ident = self._id("V")
        self.content["components"].append({"id": ident, "tag": None, "kind": "reducer", "text": []})
        return ident

    def strainer(self, x, y):
        """Y-type strainer: a short body on the line with an angled basket leg."""
        self._poly([(x - 9, y - 5), (x + 9, y - 5), (x + 9, y + 5), (x - 9, y + 5)], fill=WHITE, close=True, width=1.0)
        self._poly([(x - 3, y + 5), (x + 7, y + 17), (x + 12, y + 13), (x + 3, y + 5)], fill=WHITE, close=True, width=1.0)
        self._poly([(x - 1, y + 7), (x + 8, y + 15)], width=THIN, dashes="[1.5 1.5] 0")
        ident = self._id("V")
        self.content["components"].append({"id": ident, "tag": None, "kind": "strainer", "text": []})
        return ident

    # ---- instruments ---------------------------------------------------------
    def bubble(self, x, y, func, num, *, location="field", measures=None, tap=None, inline=False):
        """ISA bubble. tap = (x, y) on the process to draw the thin connection to. Returns the tag."""
        tag = f"{func}-{num}"
        if tap:
            self._poly([tap, (x, y)], width=THIN)
        if location == "dcs":
            self._poly([(x - R, y - R), (x + R, y - R), (x + R, y + R), (x - R, y + R)], fill=WHITE, close=True, width=1.0)
        self._circle(x, y, R, width=1.0)
        if location == "dcs":
            self._poly([(x - R, y), (x + R, y)], width=THIN)
            self._text(x, y - 4, func, size=7.5)
            self._text(x, y + 10, num, size=7.5)
        else:
            self._text(x, y - 2, func, size=7.5)
            self._text(x, y + 8, num, size=7.5)
        rec = {"id": tag, "tag": tag, "function": func, "location": location, "text": [func, num]}
        if inline:
            rec["inline"] = True
        if measures:
            rec["measures"] = measures
        self.content["instruments"].append(rec)
        return tag

    def interlock(self, x, y, label):
        """Interlock diamond; the notes say which SIF it stands for."""
        d = 14
        self._poly([(x, y - d), (x + d, y), (x, y + d), (x - d, y)], fill=WHITE, close=True, width=1.0)
        self._text(x, y + 2.5, label, size=7)

    def signal_line(self, pts):
        self._poly(pts, width=THIN, dashes="[4 3] 0")

    def signal(self, frm, to, purpose, typ="electrical", via=""):
        rec = {"from": frm, "to": to, "type": typ, "purpose": purpose}
        if via:
            rec["via_interlock"] = via
        self.content["signals"].append(rec)

    def top(self, ident):
        """Where a signal lands on a valve: the top of its actuator."""
        return self._tops[ident]

    def notes(self, x, y, lines):
        self._text(x, y, "NOTES", size=8, align="l")
        for i, t in enumerate(lines, start=1):
            self._text(x, y + 11 * i, t, size=7, align="l")
        self.content["notes"] = list(lines)


# ---- the three sheets -------------------------------------------------------------
def draw_pid_100_001(s: Sheet) -> None:
    """Inlet KO drum V-1002: feed inlet L-101, liquid outlet L-103, blowdown L-104, gas out L-102, take-off L-105."""
    y = 330
    # L-101 feed gas inlet, left to right into the drum
    s.pipe([(146, y), (760, y)], arrows=[(205, y, "r"), (700, y, "r")])
    bl100 = s.flag(146, y, ["FEED GAS", "FROM BL-100"], "l", kind="boundary", direction="in", tag="BL-100", name="FEED GAS FROM BL-100")
    hv = s.valve(250, y, "ball_valve", tag="HV-1001")
    xv1 = s.valve(320, y, "on_off_valve", tag="XV-1001", actuator="solenoid", fail="FC")
    pts = [s.bubble(x, 255, "PT", n, tap=(x, y), measures={"line": "L-101"}) for x, n in ((390, "1001A"), (450, "1001B"), (510, "1001C"))]
    pi = s.bubble(575, 255, "PI", "1001", tap=(575, y), measures={"line": "L-101"})
    ft = s.bubble(650, y, "FT", "1004", inline=True)
    s.vessel("V-1002", "INLET KO DRUM", 760, 235, 860, 475, label_at=(700, 500))
    s.line("L-101", '12"', "FEED GAS", bl100, "V-1002", [hv, xv1, *pts, pi, ft], (160, y + 34), path=[hv, xv1, ft])
    fic = s.bubble(650, 215, "FIC", "1004", location="dcs")
    s.signal_line([(650, y - R), (650, 215 + R)])
    s.signal(ft, fic, "measurement")

    # level instruments on the drum
    lg = s.bubble(940, 265, "LG", "1002", tap=(860, 265), measures={"item": "V-1002"})
    lta = s.bubble(940, 320, "LT", "1002A", tap=(860, 320), measures={"item": "V-1002"})
    ltb = s.bubble(940, 375, "LT", "1002B", tap=(860, 375), measures={"item": "V-1002"})
    lt6 = s.bubble(940, 440, "LT", "1006", tap=(860, 440), measures={"item": "V-1002"})
    lic = s.bubble(1030, 440, "LIC", "1006", location="dcs")
    s.signal_line([(940 + R, 440), (1030 - R, 440)])
    s.signal(lt6, lic, "measurement")

    # L-104 blowdown from the top of the drum, to the flare header (right to left)
    s.pipe([(780, 240), (780, 95), (596, 95)], arrows=[(780, 160, "u"), (690, 95, "l")])
    lo = s.valve(735, 95, "gate_valve", normal="LO")
    bdv = s.valve(650, 95, "on_off_valve", tag="BDV-1001", actuator="solenoid", fail="FO")
    flare = s.flag(596, 95, ["BLOWDOWN TO", "FLARE-HDR"], "l", kind="boundary", direction="out", tag="FLARE-HDR", name="BLOWDOWN TO FLARE HEADER")
    s.line("L-104", '6"', "BLOWDOWN", "V-1002", flare, [lo, bdv], (684, 136))

    # L-105 small take-off and L-102 gas outlet, both leaving for PID-100-002
    s.pipe([(815, 236), (815, 118), (1055, 118)], arrows=[(940, 118, "r")])
    opc5 = s.flag(1055, 118, ["TO PID-100-002", "L-105"], "r", kind="opc", direction="out", other_drawing="PID-100-002", line_no="L-105")
    s.line("L-105", '2"', "FUEL GAS", "V-1002", opc5, [], (870, 112))
    s.pipe([(845, 241), (845, 170), (1055, 170)], arrows=[(940, 170, "r")])
    opc2 = s.flag(1055, 170, ["TO PID-100-002", "L-102"], "r", kind="opc", direction="out", other_drawing="PID-100-002", line_no="L-102")
    s.line("L-102", '10"', "FEED GAS", "V-1002", opc2, [], (870, 164))

    # L-103 liquid outlet from the bottom of the drum (left to right)
    yb = 560
    s.pipe([(810, 475), (810, yb), (1060, yb)], arrows=[(810, 520, "d"), (1045, yb, "r")])
    lv = s.valve(880, yb, "control_valve", tag="LV-1006", actuator="diaphragm", fail="FC")
    xv2 = s.valve(950, yb, "on_off_valve", tag="XV-1002", actuator="solenoid", fail="FC")
    chk = s.valve(1015, yb, "check_valve")
    bl103 = s.flag(1060, yb, ["LIQUID TO", "BL-103"], "r", kind="boundary", direction="out", tag="BL-103", name="LIQUID TO BL-103")
    s.line("L-103", '3"', "LIQUID", "V-1002", bl103, [lv, xv2, chk], (822, yb + 44))
    # level control: LIC-1006 -> LV-1006
    lvx, lvy = s.top(lv)
    s.signal_line([(1030, 440 + R), (1030, 492), (lvx, 492), (lvx, lvy)])
    s.signal(lic, lv, "control")

    # I-1 = SIF-100-01: PT-1001A/B/C -> close XV-1001, open BDV-1001
    s.interlock(450, 170, "I-1")
    for x in (390, 450, 510):
        s.signal_line([(x, 255 - R), (x, 205)])
    s.signal_line([(390, 205), (510, 205)])
    s.signal_line([(450, 205), (450, 184)])
    x1, y1 = s.top(xv1)
    s.signal_line([(436, 170), (x1, 170), (x1, y1)])
    bx, by = s.top(bdv)
    s.signal_line([(450, 156), (450, 40), (bx, 40), (bx, by)])
    for p in pts:
        s.signal(p, xv1, "trip", via="I-1")
        s.signal(p, bdv, "trip", via="I-1")

    # I-2 = SIF-100-02: LT-1002A/B -> close XV-1001 (reference diamond at the valve), close XV-1002
    s.interlock(1085, 347, "I-2")
    s.signal_line([(940 + R, 320), (1085, 320), (1085, 333)])
    s.signal_line([(940 + R, 375), (1085, 375), (1085, 361)])
    x2, y2 = s.top(xv2)
    s.signal_line([(1099, 347), (1135, 347), (1135, 508), (x2, 508), (x2, y2)])
    s.interlock(262, 275, "I-2")
    s.signal_line([(276, 275), (x1 - 8, 275), (x1 - 8, y1 + 8)])
    for p in (lta, ltb):
        s.signal(p, xv1, "trip", via="I-2")
        s.signal(p, xv2, "trip", via="I-2")

    s.notes(60, 610, ["1. I-1 = SIF-100-01: PT-1001A/B/C HIGH-HIGH (2oo3) CLOSES XV-1001 AND OPENS BDV-1001.",
                      "2. I-2 = SIF-100-02: LT-1002A/B HIGH-HIGH (2oo3) CLOSES XV-1001 AND XV-1002.",
                      "3. LO = LOCKED OPEN.  FC / FO = FAIL CLOSED / FAIL OPEN.",
                      "4. DASHED LINES ARE ELECTRICAL SIGNALS.  SQUARED BUBBLES ARE DCS FUNCTIONS.",
                      "5. DUMMY DATA - NOT A REAL FACILITY."])
    _ = lg


def draw_pid_100_002(s: Sheet) -> None:
    """Pressure control and export: L-102 through PV-1005 to BL-200; L-105 take-off with FT-1006."""
    y = 330
    s.pipe([(146, y), (900, y)], arrows=[(215, y, "r"), (840, y, "r")])
    opc2 = s.flag(146, y, ["FROM PID-100-001", "V-1002  L-102"], "l", kind="opc", direction="in", other_drawing="PID-100-001",
                  other_item="V-1002", line_no="L-102")
    pt = s.bubble(290, 255, "PT", "1005", tap=(290, y), measures={"line": "L-102"})
    g1 = s.valve(400, y, "gate_valve")
    r1 = s.reducer(470, y, narrow="r")
    pv = s.valve(540, y, "control_valve", tag="PV-1005", actuator="diaphragm", fail="FO")
    r2 = s.reducer(610, y, narrow="l")
    g2 = s.valve(680, y, "gate_valve")
    bl200 = s.flag(900, y, ["FEED GAS TO", "BL-200"], "r", kind="boundary", direction="out", tag="BL-200", name="FEED GAS TO BL-200")
    s.line("L-102", '10"', "FEED GAS", opc2, bl200, [pt, g1, r1, pv, r2, g2], (160, y + 34), path=[g1, r1, pv, r2, g2])
    pic = s.bubble(420, 175, "PIC", "1005", location="dcs")
    s.signal_line([(290, 255 - R), (290, 175), (420 - R, 175)])
    s.signal(pt, pic, "measurement")
    px, py = s.top(pv)
    s.signal_line([(420 + R, 175), (px, 175), (px, py)])
    s.signal(pic, pv, "control")

    y5 = 520
    s.pipe([(146, y5), (560, y5)], arrows=[(215, y5, "r"), (500, y5, "r")])
    opc5 = s.flag(146, y5, ["FROM PID-100-001", "V-1002  L-105"], "l", kind="opc", direction="in", other_drawing="PID-100-001",
                  other_item="V-1002", line_no="L-105")
    ft = s.bubble(340, y5, "FT", "1006", inline=True)
    fut = s.flag(560, y5, ["FUTURE", "FUEL GAS"], "r", kind="boundary", direction="out", name="FUTURE FUEL GAS")
    s.line("L-105", '2"', "FUEL GAS", opc5, fut, [ft], (160, y5 + 34))

    s.notes(60, 610, ["1. FC / FO = FAIL CLOSED / FAIL OPEN.",
                      "2. DASHED LINES ARE ELECTRICAL SIGNALS.  SQUARED BUBBLES ARE DCS FUNCTIONS.",
                      "3. DUMMY DATA - NOT A REAL FACILITY."])


def draw_pid_100_003(s: Sheet) -> None:
    """Utility connections: two unnumbered utility lines, nothing tagged."""
    y = 300
    s.pipe([(196, y), (700, y)], arrows=[(260, y, "r"), (640, y, "r")])
    a = s.flag(196, y, ["INSTRUMENT AIR", "HEADER"], "l", kind="boundary", direction="in", name="INSTRUMENT AIR HEADER")
    v1 = s.valve(360, y, "gate_valve")
    st = s.strainer(460, y)
    b = s.flag(700, y, ["INSTRUMENT AIR", "USERS"], "r", kind="boundary", direction="out", name="INSTRUMENT AIR USERS")
    s.line("", '1"', "INSTRUMENT AIR", a, b, [v1, st], (210, y + 34))

    y = 460
    s.pipe([(196, y), (700, y)], arrows=[(260, y, "r"), (640, y, "r")])
    c = s.flag(196, y, ["NITROGEN", "HEADER"], "l", kind="boundary", direction="in", name="NITROGEN HEADER")
    v2 = s.valve(360, y, "gate_valve")
    ck = s.valve(460, y, "check_valve")
    d = s.flag(700, y, ["NITROGEN", "UTILITY STATION"], "r", kind="boundary", direction="out", name="NITROGEN UTILITY STATION")
    s.line("", '1"', "NITROGEN", c, d, [v2, ck], (210, y + 34))

    s.notes(60, 610, ["1. UTILITY LINES ARE NOT NUMBERED ON THIS SHEET.",
                      "2. DUMMY DATA - NOT A REAL FACILITY."])


DRAWERS = {"PID-100-001": draw_pid_100_001, "PID-100-002": draw_pid_100_002, "PID-100-003": draw_pid_100_003}


def drawn_content() -> dict:
    """What each sheet shows, without drawing anything. Same for every issue of the set."""
    sheets = {}
    for doc_no, fn in DRAWERS.items():
        s = Sheet(None)
        fn(s)
        sheets[doc_no] = s.content
    return {"note": "DUMMY DATA. Answer key for the synthetic U-100 P&IDs drawn by scripts/make_dummy_pdf.py. "
                    "Not read by any loader. 'order' lists the items along a line in flow order, taps included; "
                    "'path' lists the in-line ones only.",
            "unit": "U-100", "sheets": sheets}


def build(out: Path, drawings: list[tuple], transmittal: str) -> Path:
    doc = pymupdf.open()
    cover = doc.new_page(width=W, height=H)
    cover.insert_text((60, 80), "DOCUMENT TRANSMITTAL (DUMMY DATA - not a real facility)", fontsize=18)
    cover.insert_text((60, 120), f"Transmittal No. {transmittal}    Unit 100 - Feed Gas Inlet    P&ID set", fontsize=12)
    y = 170
    for d, r, t in drawings:
        cover.insert_text((60, y), f"{d}   Rev {r}   {t}", fontsize=11)
        y += 20
    for d, r, t in drawings:
        page = doc.new_page(width=W, height=H)
        page.draw_rect(pymupdf.Rect(30, 30, W - 30, H - 30), width=1.5)
        DRAWERS[d](Sheet(page))
        # Title block, bottom right
        x0, y0 = W - 30 - 420, H - 30 - 120
        page.draw_rect(pymupdf.Rect(x0, y0, W - 30, H - 30), width=1.5)
        page.insert_text((x0 + 10, y0 + 22), "DUMMY LNG PROJECT - UNIT 100 FEED GAS INLET", fontsize=9)
        page.insert_text((x0 + 10, y0 + 42), f"TITLE: {t}", fontsize=9)
        page.insert_text((x0 + 10, y0 + 66), f"DRAWING NO. {d}", fontsize=11)
        page.insert_text((x0 + 250, y0 + 66), f"REV. {r}", fontsize=11)
        page.insert_text((x0 + 10, y0 + 90), "SHEET 1 OF 1", fontsize=9)
        page.insert_text((x0 + 250, y0 + 90), "SCALE: NTS", fontsize=9)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    doc.close()
    return out


def write_manifest(out: Path) -> Path:
    out.write_text(json.dumps(drawn_content(), indent=1) + "\n", encoding="utf-8", newline="\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reissue", action="store_true")
    ap.add_argument("--all", action="store_true", help="both issues and the drawn-content JSON")
    a = ap.parse_args()
    data = ROOT / "data"
    if a.all or not a.reissue:
        print(build(data / "U100-PIDS-TX-0042.pdf", FIRST, "TX-0042"))
    if a.all or a.reissue:
        print(build(data / "U100-PIDS-TX-0057.pdf", REISSUE, "TX-0057"))
    if a.all:
        print(write_manifest(data / "U100-PIDS-DRAWN-CONTENT.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
