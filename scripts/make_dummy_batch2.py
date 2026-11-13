"""Fabricate the complete document set of a second synthetic unit, U-200 (hot oil heater system), for a
blind test of the cross-document checks. DUMMY DATA - not a real facility.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

One deterministic generator, no randomness, fixed workbook timestamps. It is the single source of truth
for everything under data/u200/:

  * the instrument index workbook (Cover, Instrument Index, Loop Register, Alarm Register)
  * the cause & effect chart, the SRS register, the LOPA register (Scenarios + IPLs)
  * the master alarm database, the DCS / SIS configuration export, the SIL verification
  * the MOC register, the document register (CSV), the curated compensating measures (CSV)
  * the out-of-service register (CSV), unit.json and the sealed answer key

The plant is described once (INSTRUMENTS, ALARMS, SIFS, SCENARIOS, MOCS, ...). Every document is a view of
that description. Where a document deliberately disagrees with the others, the disagreement is a named
field on the record (for example `cfg_limit` beside `setpoint`) and is marked with the answer-key id in a
comment. The answer key is built from the finished tables, never typed twice, so it cannot drift.

    python scripts/make_dummy_batch2.py            # writes data/u200/
    python scripts/make_dummy_batch2.py --out DIR  # writes somewhere else (the test does this)

THE ANSWER KEY IS SEALED. Whoever runs the checks on these documents must not read this file or
data/u200/U200-BATCH2-ANSWER-KEY.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "u200"

UNIT = "U-200"
UNIT_TITLE = "UNIT 200 HOT OIL HEATER"
DUMMY = "(DUMMY DATA - not a real facility)"
STAMP = datetime(2026, 11, 12, 6, 0, 0)          # fixed workbook timestamp
EXPORT_TIME = "2026-11-12 06:00"                 # the configuration export's status line
LOGIC_SOLVER = "SIS-LS-200"
DCS = "DCS-200-C01"
NAVY = "1F3A5F"

# ---- documents ---------------------------------------------------------------------------------------

REV = {"U200-INST-INDEX": "C", "U200-LOOP-REG": "C", "U200-ALM-REG": "C", "U200-CE-CHART": "B", "U200-SRS-001": "C",
       "U200-LOPA-001": "B", "U200-SILV-001": "B", "U200-MADB-001": "B", "U200-CFG-EXPORT": "A", "U200-MOC-REG": "A",
       "U200-DOC-REGISTER": "A"}
F_INDEX = f"U200-INST-INDEX-Rev-{REV['U200-INST-INDEX']}.xlsx"
F_CE = f"U200-CE-CHART-Rev-{REV['U200-CE-CHART']}.xlsx"
F_SRS = f"U200-SRS-001-Rev-{REV['U200-SRS-001']}.xlsx"
F_LOPA = f"U200-LOPA-001-Rev-{REV['U200-LOPA-001']}.xlsx"
F_MADB = f"U200-MADB-001-Rev-{REV['U200-MADB-001']}.xlsx"
F_CFG = f"U200-CFG-EXPORT-Rev-{REV['U200-CFG-EXPORT']}.xlsx"
F_SILV = f"U200-SILV-001-Rev-{REV['U200-SILV-001']}.xlsx"
F_MOC = f"U200-MOC-REG-Rev-{REV['U200-MOC-REG']}.xlsx"
F_DOCREG = "U200-DOC-REGISTER.csv"
F_CURATED = "compensating_measures_U-200.csv"
F_OOS = "out_of_service_U-200.csv"
F_UNIT = "unit.json"
F_KEY = "U200-BATCH2-ANSWER-KEY.json"
F_BLIND = "U200-BLIND-ADJUDICATION.json"         # written later by the scorer, never by this script

# (file, sheet) -> document number, for every sheet that carries a "Document No. X    Rev Y" title row
SHEET_DOCS = {
    (F_INDEX, "Instrument Index"): "U200-INST-INDEX", (F_INDEX, "Loop Register"): "U200-LOOP-REG",
    (F_INDEX, "Alarm Register"): "U200-ALM-REG", (F_CE, "CE-200"): "U200-CE-CHART",
    (F_SRS, "SIF Requirements"): "U200-SRS-001", (F_LOPA, "Scenarios"): "U200-LOPA-001", (F_LOPA, "IPLs"): "U200-LOPA-001",
    (F_MADB, "Alarms"): "U200-MADB-001", (F_CFG, "Points"): "U200-CFG-EXPORT", (F_CFG, "Alarms"): "U200-CFG-EXPORT",
    (F_CFG, "SIS Trips"): "U200-CFG-EXPORT", (F_CFG, "Overrides"): "U200-CFG-EXPORT",
    (F_SILV, "SIF Summary"): "U200-SILV-001", (F_SILV, "Subsystems"): "U200-SILV-001",
    (F_SILV, "Degraded Operation"): "U200-SILV-001", (F_MOC, "Register"): "U200-MOC-REG", (F_DOCREG, None): "U200-DOC-REGISTER",
}

# ---- the plant ---------------------------------------------------------------------------------------
# Instrument: tag, service, type, loop, P&ID, line / equipment, system, range (low, high), units, signal, remarks,
# configuration (block type, I/O channel) or None when the item has no point in the DCS / SIS.

HART = "4-20 mA HART"
SOV = "24 VDC solenoid"
DI = "24 VDC DI"


def _i(tag, service, typ, loop, pid, loc, system, rng, units, signal, remarks, cfg):
    return {"tag": tag, "service": service, "type": typ, "loop": loop, "pid": pid, "loc": loc, "system": system,
            "range": rng, "units": units, "signal": signal, "remarks": remarks, "cfg": cfg}


INSTRUMENTS = [
    _i("FT-2001A", "Hot oil heater inlet flow (SIS) - A", "Flow transmitter (DP)", None, "PID-200-001", "L-201", "SIS", (0, 400), "m3/h", HART, "2oo3 with FT-2001B/C", ("AI", "SIS-AI-01/01")),
    _i("FT-2001B", "Hot oil heater inlet flow (SIS) - B", "Flow transmitter (DP)", None, "PID-200-001", "L-201", "SIS", (0, 400), "m3/h", HART, None, ("AI", "SIS-AI-01/02")),
    _i("FT-2001C", "Hot oil heater inlet flow (SIS) - C", "Flow transmitter (DP)", None, "PID-200-001", "L-201", "SIS", (0, 400), "m3/h", HART, None, ("AI", "SIS-AI-01/03")),
    _i("FT-2002", "Hot oil heater inlet flow control", "Flow transmitter (vortex)", "FIC-2002", "PID-200-001", "L-201", "BPCS", (0, 400), "m3/h", HART, None, ("AI", "DCS-AI-01/01")),
    _i("FV-2002", "Hot oil flow control valve", "Control valve", "FIC-2002", "PID-200-001", "L-201", "BPCS", None, None, "4-20 mA", "Fail open", ("AO", "DCS-AO-01/01")),
    _i("PDT-2003", "Heater coil differential pressure", "Differential pressure transmitter", None, "PID-200-001", "H-201", "BPCS", (0, 10), "bar", HART, None, ("AI", "DCS-AI-01/02")),
    _i("PT-2010A", "Fuel gas burner header pressure (SIS) - A", "Pressure transmitter", None, "PID-200-002", "L-204", "SIS", (0, 4), "barg", HART, "1oo2 with PT-2010B", ("AI", "SIS-AI-01/04")),
    _i("PT-2010B", "Fuel gas burner header pressure (SIS) - B", "Pressure transmitter", None, "PID-200-002", "L-204", "SIS", (0, 4), "barg", HART, None, ("AI", "SIS-AI-01/05")),
    _i("PT-2011", "Fuel gas burner header pressure high (SIS)", "Pressure transmitter", None, "PID-200-002", "L-204", "SIS", (0, 4), "barg", HART, "1oo1", ("AI", "SIS-AI-01/06")),
    _i("PT-2012", "Fuel gas burner header pressure control", "Pressure transmitter", "PIC-2012", "PID-200-002", "L-204", "BPCS", (0, 4), "barg", HART, None, ("AI", "DCS-AI-02/01")),
    _i("PV-2012", "Fuel gas pressure control valve", "Control valve", "PIC-2012", "PID-200-002", "L-204", "BPCS", None, None, "4-20 mA", "Fail close", ("AO", "DCS-AO-01/02")),
    _i("PT-2013", "Fuel gas supply pressure", "Pressure transmitter", None, "PID-200-002", "L-203", "BPCS", (0, 16), "barg", HART, "Re-ranged from 0-10 barg under MOC-2026-031", ("AI", "DCS-AI-02/02")),
    _i("PT-2014", "Fuel gas burner header pressure (monitoring)", "Pressure transmitter", None, "PID-200-002", "L-204", "BPCS", (0, 4), "barg", HART, "Separate tapping from PT-2012", ("AI", "DCS-AI-02/03")),
    _i("PI-2015", "Fuel gas burner header pressure gauge", "Pressure gauge", None, "PID-200-002", "L-204", "LOCAL", (0, 4), "barg", None, "Local indication", None),
    _i("TT-2020A", "Hot oil heater outlet temperature (SIS) - A", "Temperature transmitter", None, "PID-200-001", "L-202", "SIS", (0, 450), "degC", HART, "2oo3 with TT-2020B/C", ("AI", "SIS-AI-02/01")),
    _i("TT-2020B", "Hot oil heater outlet temperature (SIS) - B", "Temperature transmitter", None, "PID-200-001", "L-202", "SIS", (0, 450), "degC", HART, None, ("AI", "SIS-AI-02/02")),
    _i("TT-2020C", "Hot oil heater outlet temperature (SIS) - C", "Temperature transmitter", None, "PID-200-001", "L-202", "SIS", (0, 450), "degC", HART, None, ("AI", "SIS-AI-02/03")),
    _i("TT-2021", "Hot oil heater outlet temperature control", "Temperature transmitter", "TIC-2021", "PID-200-001", "L-202", "BPCS", (0, 450), "degC", HART, "Cascade master to PIC-2012", ("AI", "DCS-AI-01/03")),
    _i("TT-2022", "Heater tube skin temperature", "Temperature transmitter", None, "PID-200-001", "H-201", "BPCS", (0, 700), "degC", HART, None, ("AI", "DCS-AI-01/04")),
    _i("TT-2023", "Stack flue gas temperature", "Temperature transmitter", None, "PID-200-001", "H-201", "BPCS", (0, 800), "degC", HART, None, ("AI", "DCS-AI-01/05")),
    _i("AT-2024", "Flue gas oxygen", "Oxygen analyser (zirconia)", None, "PID-200-001", "H-201", "BPCS", (0, 10), "%", HART, None, ("AI", "DCS-AI-01/06")),
    _i("PT-2025", "Firebox draught pressure", "Pressure transmitter", None, "PID-200-001", "H-201", "BPCS", (-25, 25), "mmWG", HART, None, ("AI", "DCS-AI-01/07")),
    _i("LT-2030A", "Fuel gas KO drum level (SIS) - A", "Level transmitter (GWR)", None, "PID-200-002", "V-201", "SIS", (0, 1200), "mm", HART, "1oo2 with LT-2030B", ("AI", "SIS-AI-02/04")),
    _i("LT-2030B", "Fuel gas KO drum level (SIS) - B", "Level transmitter (GWR)", None, "PID-200-002", "V-201", "SIS", (0, 1200), "mm", HART, None, ("AI", "SIS-AI-02/05")),
    _i("LT-2031", "Fuel gas KO drum level control", "Level transmitter (DP)", "LIC-2031", "PID-200-002", "V-201", "BPCS", (0, 1200), "mm", HART, None, ("AI", "DCS-AI-02/04")),
    _i("LV-2031", "Fuel gas KO drum drain level valve", "Control valve", "LIC-2031", "PID-200-002", "L-206", "BPCS", None, None, "4-20 mA", "Fail close", ("AO", "DCS-AO-01/03")),
    _i("LG-2032", "Fuel gas KO drum level gauge", "Magnetic level gauge", None, "PID-200-002", "V-201", "LOCAL", (0, 1200), "mm", None, "Local indication", None),
    _i("LT-2040", "Hot oil expansion drum level", "Level transmitter (DP)", None, "PID-200-001", "V-202", "BPCS", (0, 3000), "mm", HART, "DCS block scaled 0-100 % of the 0-3000 mm span", ("AI", "DCS-AI-01/08")),
    _i("PT-2041", "Hot oil expansion drum pressure", "Pressure transmitter", None, "PID-200-001", "V-202", "BPCS", (0, 10), "barg", HART, None, ("AI", "DCS-AI-02/05")),
    _i("XV-2001", "Fuel gas main ESD valve (upstream block)", "ESD ball valve", None, "PID-200-002", "L-204", "SIS", None, None, SOV, "Fail close", ("DO", "SIS-DO-01/01")),
    _i("XV-2002", "Fuel gas main ESD valve (downstream block)", "ESD ball valve", None, "PID-200-002", "L-204", "SIS", None, None, SOV, "Fail close", ("DO", "SIS-DO-01/02")),
    _i("XV-2004", "Fuel gas KO drum inlet ESD valve", "ESD ball valve", None, "PID-200-002", "L-203", "SIS", None, None, SOV, "Fail close", ("DO", "SIS-DO-01/03")),
    _i("ZSC-2001", "XV-2001 closed limit switch", "Limit switch", None, "PID-200-002", "L-204", "SIS", None, None, DI, None, ("DI", "SIS-DI-01/01")),
    _i("ZSC-2002", "XV-2002 closed limit switch", "Limit switch", None, "PID-200-002", "L-204", "SIS", None, None, DI, None, ("DI", "SIS-DI-01/02")),
    _i("HS-2001", "Heater emergency shutdown push-button", "Push-button", None, "PID-200-001", "H-201", "SIS", None, None, DI, "Control room panel", ("DI", "SIS-DI-01/03")),
    _i("HV-2001", "Fuel gas manual isolation valve", "Manual ball valve", None, "PID-200-002", "L-204", "LOCAL", None, None, None, "Upstream of XV-2001", None),
    _i("PSV-2050", "Hot oil coil outlet relief valve", "Relief valve", None, "PID-200-001", "L-202", "LOCAL", None, None, None, "Thermal relief", None),
]
INST = {i["tag"]: i for i in INSTRUMENTS}

# Loops: loop no., service, sensor, final element, protected equipment
LOOPS = [
    ("FIC-2002", "Hot oil heater inlet flow control", "FT-2002", "FV-2002", "H-201"),
    ("PIC-2012", "Fuel gas burner header pressure control", "PT-2012", "PV-2012", "H-201"),
    ("TIC-2021", "Hot oil heater outlet temperature control (cascade to PIC-2012)", "TT-2021", None, "H-201"),
    ("LIC-2031", "Fuel gas KO drum level control", "LT-2031", "LV-2031", "V-201"),
]

# How the configuration differs from the index, point by point.
CFG_RANGE = {
    "PT-2010B": (0, 6, "barg"),            # B2-10: index says 0-4 barg
    "LT-2040": (0, 100, "%"),              # clean control: the DCS block is scaled in % of the 0-3000 mm span
}
CFG_HOME = {
    "PT-2011": ("DCS", DCS, "DCS-AI-02/07"),   # B2-20: the index says SIS; the trip input is a DCS point
}
CFG_ONLY_POINTS = [
    # B2-11: configured, in no other document
    ("TT-2026", "DCS", DCS, "AI", "DCS-AI-02/06", 0, 100, "degC", "Combustion air temperature", None),
]

# ---- alarms -------------------------------------------------------------------------------------------


def _a(tag, source, desc, kind, sp, units, prio, cls, cause, conseq, action, ttr, deadband, on_delay, protects, **kw):
    a = {"tag": tag, "source": source, "desc": desc, "kind": kind, "sp": sp, "units": units, "prio": prio, "cls": cls,
         "cause": cause, "conseq": conseq, "action": action, "ttr": ttr, "deadband": deadband, "on_delay": on_delay,
         "protects": protects, "ipl": "No", "lopa": None, "outcome": "Keep", "status": "Implemented",
         "in_register": True, "in_cfg": True}
    a.update(kw)
    return a


ALARMS = [
    _a("FAL-2002", "FT-2002", "Hot oil heater inlet flow low", "low", 160, "m3/h", "High", "Safety",
       "Circulation pump trip; FV-2002 closing", "SIF-200-01 demand; tube overheating if the trip fails",
       "Start the standby pump; open FV-2002 in manual; reduce firing",
       "15 min",                                   # B2-19: credited as an IPL against a 90 s process safety time
       "5 m3/h", "5 s", "H-201", ipl="Yes", lopa="S-200-01"),
    _a("PAL-2014", "PT-2014", "Fuel gas burner header pressure low", "low", 0.6, "barg", "High", "Safety",
       "PV-2012 closing; loss of fuel gas supply", "Burner flame-out; SIF-200-02 demand",
       "Check PIC-2012 and the supply pressure; prepare for a heater trip", "5 min", "0.05 barg", "2 s", "H-201",
       cfg_limit=0.3),                             # B2-14: configured below the 0.35 barg trip
    _a("PAH-2012", "PT-2012", "Fuel gas burner header pressure high (control)", "high", 2.2, "barg", "Medium", "Operational",
       "PIC-2012 / PV-2012 opening", "Approach to the SIF-200-03 trip; flame lift-off",
       "Take PIC-2012 to manual and reduce the output", "10 min", "0.05 barg", "5 s", "H-201"),
    _a("TAH-2021", "TT-2021", "Hot oil heater outlet temperature high", "high", 330, "degC", "High", "Safety",
       "Over-firing; low hot oil flow", "Approach to the SIF-200-04 trip; hot oil degradation",
       "Reduce firing; check the hot oil flow", "10 min", "2 degC", "10 s", "H-201",
       ipl="Yes", lopa="S-200-04",                 # B2-17: the LOPA credits TAH-2022, not this alarm
       cfg_source="TT-2020A"),                     # B2-21: configured on a SIF-200-04 initiator
    _a("TAL-2021", "TT-2021", "Hot oil heater outlet temperature low", "low", 250, "degC", "Low", "Operational",
       "Burner trip; low firing", "Loss of heat to the users", "None defined - informational only", "30 min", "2 degC", "30 s",
       "H-201", outcome="Remove - no operator action", status="Removed", in_register=False),   # B2-22: still configured
    _a("TAH-2022", "TT-2022", "Heater tube skin temperature high", "high", 520, "degC", "Medium", "Operational",
       "Flame impingement; coking; over-firing", "Tube damage; coil rupture", "Reduce firing; inspect the flame pattern",
       "10 min", "5 degC", "10 s", "H-201"),       # B2-17: credited in S-200-04, but ipl stays "No" here
    _a("TAH-2023", "TT-2023", "Stack flue gas temperature high", "high", 450, "degC", "Low", "Operational",
       "Fouled convection section; excess firing", "Loss of efficiency; stack damage",
       "Reduce firing; schedule convection section cleaning", "30 min", "5 degC", "30 s", "H-201"),
    _a("AAL-2024", "AT-2024", "Flue gas oxygen low", "low", 1.5, "%", "High", "Safety",
       "Insufficient combustion air; stack damper fault", "Incomplete combustion; unburnt fuel in the firebox",
       "Reduce firing; open the stack damper", "5 min", "0.2 %", "10 s", "H-201",
       cfg_prio="Medium"),                         # B2-16
    _a("PAH-2025", "PT-2025", "Firebox pressure high (loss of draught)", "high", 2, "mmWG", "Medium", "Operational",
       "Stack damper closing; tube leak", "Flame roll-out at the burners", "Open the stack damper; reduce firing",
       "10 min", "0.5 mmWG", "5 s", "H-201"),
    _a("LAH-2031", "LT-2031", "Fuel gas KO drum level high", "high", 720, "mm", "High", "Safety",
       "LIC-2031 / LV-2031 fails closed; condensate slug", "Liquid carry-over to the burners; SIF-200-05 demand",
       "Open the LV-2031 bypass; drain the drum", "10 min", "20 mm", "10 s", "V-201",
       cfg_enabled="No"),                          # B2-07
    _a("LAL-2031", "LT-2031", "Fuel gas KO drum level low", "low", 180, "mm", "Low", "Operational",
       "LV-2031 stuck open", "Gas blow-by to the closed drain", "Close LV-2031 in manual", "20 min", "20 mm", "10 s", "V-201"),
    _a("LAL-2040", "LT-2040", "Hot oil expansion drum level low", "low", 600, "mm", "Medium", "Operational",
       "Hot oil leak; low inventory", "Loss of circulation pump suction head", "Check for leaks; make up hot oil",
       "20 min", "60 mm", "10 s", "V-202",
       cfg_limit=20, cfg_units="%", cfg_deadband="2 %"),      # clean control: 600 mm of 3000 mm = 20 %
    _a("LAH-2040", "LT-2040", "Hot oil expansion drum level high", "high", 2400, "mm", "Low", "Operational",
       "Thermal expansion on start-up; water ingress", "Overfill of the expansion drum", "Drain to hot oil storage",
       "30 min", "60 mm", "10 s", "V-202",
       cfg_limit=80, cfg_units="%", cfg_deadband="2 %"),      # clean control: 2400 mm of 3000 mm = 80 %
    _a("PAH-2041", "PT-2041", "Hot oil expansion drum pressure high", "high", 5.5, "barg", "Medium", "Operational",
       "Blanket gas regulator fault", "Approach to the relief valve set pressure",
       "Check the blanket gas regulator; vent to flare", "15 min", "0.1 barg", "5 s", "V-202",
       cfg_limit=6),                               # B2-15: MOC-2026-039 closed, DCS never changed
    _a("PDAH-2003", "PDT-2003", "Heater coil differential pressure high", "high", 6, "bar", "Low", "Operational",
       "Coking of the heater coil", "Reduced hot oil flow; higher film temperature",
       "Plan decoking; check the margin to FAL-2002", "60 min", "0.2 bar", "30 s", "H-201",
       in_cfg=False),                              # B2-12: "Implemented" but never configured
    _a("PAL-2013", "PT-2013", "Fuel gas supply pressure low", "low", 2.5, "barg", "Low", "Operational",
       "Upstream supply disturbance", "Approach to PAL-2014 and burner flame-out", "Contact the fuel gas supply unit",
       "15 min", "0.1 barg", "10 s", "H-201"),
]
ALARM = {a["tag"]: a for a in ALARMS}
RATIONALISED = "2026-04-22"
TEAM = "Alarm management engineer, operations rep, process engineer (dummy)"
# Clean control: the SIS announces its own trip. That is a trip notification, not an alarm, so it is in the
# configuration only and rightly absent from the alarm register and the master alarm database.
TRIP_NOTIFY = ("FALL-2001", "FT-2001A", "SIS", "TRIP NOTIFY", 120, "m3/h", "High", None, "0 s", "Yes")

# ---- safety instrumented functions --------------------------------------------------------------------

LAMBDA = {"FT": 6e-7, "PT": 5e-7, "TT": 8e-7, "LT": 1e-6, "XV": 4e-6}     # dangerous undetected, per hour (dummy)
BETA_S, BETA_FE = 0.05, 0.1
PFD_LS = 5e-5
H_PER_MONTH = 730

SIFS = [
    {"id": "SIF-200-01", "desc": "Hot oil low flow - heater tube protection",
     "func": "On hot oil heater inlet flow low-low, close XV-2001 and XV-2002 to stop firing",
     "hazard": "Tube overheating and rupture with the burners firing; firebox fire",
     "cause_desc": "Hot oil heater inlet flow low-low", "sil": 2, "rrf": 200, "pfd_target": 0.005,
     "pst": "90 s", "resp": "15 s", "sp": 120, "sp_units": "m3/h", "direction": "Low",
     "sensors": ["FT-2001A", "FT-2001B", "FT-2001C"], "voting": "2oo3", "fes": ["XV-2001", "XV-2002"], "fe_voting": "1oo2",
     "pti_s": 12, "pti_fe": 24, "comp": "FAL-2002", "max_bypass": 8, "protects": "H-201",
     "deg_s": ("One of FT-2001A/B/C", "1oo2"), "deg_fe": ("XV-2001 or XV-2002", "1oo1"),
     "silv_rrf_target": 120, "silv_source_rev": "B"},        # B2-04: calculation still on the superseded SRS target
    {"id": "SIF-200-02", "desc": "Fuel gas low pressure - flame-out protection",
     "func": "On fuel gas burner header pressure low-low, close XV-2001 and XV-2002",
     "hazard": "Burner flame-out, unburnt gas in the firebox, explosion on re-ignition",
     "cause_desc": "Fuel gas burner header pressure low-low", "sil": 1, "rrf": 50, "pfd_target": 0.02,
     "pst": "30 s", "resp": "5 s", "sp": 0.35, "sp_units": "barg", "direction": "Low",
     "srs_sp": "350 mbarg",                                  # clean control: same value, different unit
     "sensors": ["PT-2010A", "PT-2010B"], "voting": "1oo2", "fes": ["XV-2001", "XV-2002"], "fe_voting": "1oo2",
     "pti_s": 12, "pti_fe": 24, "comp": "PAL-2014", "max_bypass": 8, "protects": "H-201",
     "deg_s": ("PT-2010A or PT-2010B", "1oo1"), "deg_fe": ("XV-2001 or XV-2002", "1oo1"),
     "ce_voting": "2oo2", "cfg_voting": "2oo2"},             # B2-02
    {"id": "SIF-200-03", "desc": "Fuel gas high pressure - flame lift-off protection",
     "func": "On fuel gas burner header pressure high-high, close XV-2001 and XV-2002",
     "hazard": "Flame lift-off and flame-out; unburnt gas in the firebox",
     "cause_desc": "Fuel gas burner header pressure high-high", "sil": 1, "rrf": 10, "pfd_target": 0.1,
     "pst": "60 s", "resp": "10 s", "sp": 2.8, "sp_units": "barg", "direction": "High",
     "sensors": ["PT-2011"], "voting": "1oo1", "fes": ["XV-2001", "XV-2002"], "fe_voting": "1oo2",
     "pti_s": 12, "pti_fe": 24, "max_bypass": 2, "protects": "H-201",
     "bypass": "Not permitted unless PAH-2014 is confirmed active and an operator is stationed at PI-2015; max 2 h",   # B2-13
     "deg_s": ("PT-2011", None), "deg_fe": ("XV-2001 or XV-2002", "1oo1"),
     "built_fes": ["XV-2001"]},                              # B2-03: C&E and configuration close one valve only
    {"id": "SIF-200-04", "desc": "Hot oil high outlet temperature - film temperature protection",
     "func": "On hot oil heater outlet temperature high-high, close XV-2001 and XV-2002",
     "hazard": "Hot oil film temperature exceeded; coking and tube rupture",
     "cause_desc": "Hot oil heater outlet temperature high-high", "sil": 1, "rrf": 30, "pfd_target": 0.033,
     "pst": "20 min", "resp": "30 s", "sp": 345, "sp_units": "degC", "direction": "High",
     "sensors": ["TT-2020A", "TT-2020B", "TT-2020C"], "voting": "2oo3", "fes": ["XV-2001", "XV-2002"], "fe_voting": "1oo2",
     "pti_s": 12, "pti_fe": 24, "comp": "TAH-2021", "max_bypass": 8, "protects": "H-201",
     "deg_s": ("One of TT-2020A/B/C", "1oo2"), "deg_fe": ("XV-2001 or XV-2002", "1oo1"),
     "cfg_sp": 355,                                          # B2-01
     "cfg_mos_max": 24},                                     # B2-09
    {"id": "SIF-200-05", "desc": "Fuel gas KO drum high level - liquid carry-over protection",
     "func": "On fuel gas KO drum level high-high, close XV-2004",
     "hazard": "Condensate carry-over to the burners; flame-out or fireball at the burner front",
     "cause_desc": "Fuel gas KO drum level high-high", "sil": 1, "rrf": 50, "pfd_target": 0.02,
     "pst": "10 min", "resp": "30 s", "sp": 900, "sp_units": "mm", "direction": "High",
     "sensors": ["LT-2030A", "LT-2030B"], "voting": "1oo2", "fes": ["XV-2004"], "fe_voting": "1oo1",
     "pti_s": 12, "pti_fe": 12,                              # B2-05: MOC-2026-034 moved the plant to 24 months
     "comp": "LAH-2031", "max_bypass": 4, "protects": "V-201",
     "deg_s": ("LT-2030A or LT-2030B", "1oo1"), "deg_fe": ("XV-2004", None)},
]
SIF = {s["id"]: s for s in SIFS}
LOST = "None - function lost"

# Maintenance override switches as configured: switch -> (active, active since)
MOS_ACTIVE = {
    "MOS-2001B": "2026-11-12 02:10",       # clean control: recorded as OOS-200-0010
    "MOS-2030A": "2026-11-08 09:15",       # B2-06: no out-of-service entry
}

# ---- LOPA ---------------------------------------------------------------------------------------------

SCENARIOS = [
    {"id": "S-200-01", "node": "H-201", "ie": "Loss of hot oil circulation (pump trip, standby fails to start) with the burners firing",
     "freq": 0.2, "conseq": "Tube overheating and rupture; firebox fire", "sev": "Cat 4", "tol": 1e-05,
     "mods": "Probability of ignition and personnel present 0.1", "sif": "SIF-200-01", "notes": "FAL-2002 credited; the SIF is sized for the residual",
     "ipls": [("Alarm + operator response", "FAL-2002", "Low flow alarm, operator starts the standby pump or reduces firing", 0.1),
              ("SIF", "SIF-200-01", "Low-low flow trip", 0.005)]},
    {"id": "S-200-02", "node": "H-201", "ie": "Fuel gas supply interruption or PIC-2012 / PV-2012 fails closed",
     "freq": 0.05, "conseq": "Burner flame-out; firebox explosion on re-ignition", "sev": "Cat 3", "tol": 0.0001,
     "mods": "Probability of explosive re-ignition 0.1", "sif": "SIF-200-02", "notes": None,
     "ipls": [("SIF", "SIF-200-02", "Low-low fuel gas pressure trip", 0.02)]},
    {"id": "S-200-03", "node": "H-201", "ie": "PIC-2012 / PV-2012 fails open",
     "freq": 0.1, "conseq": "Flame lift-off and flame-out; unburnt gas in the firebox", "sev": "Cat 3", "tol": 0.0001,
     "mods": "Probability of ignition 0.1", "sif": "SIF-200-03", "notes": "Alarm on PT-2014 is independent of the PIC-2012 loop",
     "ipls": [("Alarm + operator response", "PAH-2014", "High pressure alarm on PT-2014, operator closes HV-2001", 0.1),   # B2-13
              ("SIF", "SIF-200-03", "High-high fuel gas pressure trip", 0.1)]},
    {"id": "S-200-04", "node": "H-201", "ie": "TIC-2021 fails high; over-firing",
     "freq": 0.1, "conseq": "Hot oil film temperature exceeded; coking and tube rupture", "sev": "Cat 3", "tol": 0.0001,
     "mods": "Fraction of time at high firing 0.3", "sif": "SIF-200-04", "notes": "TAH-2021 shares TT-2021 with the initiating loop and is not credited",
     "ipls": [("Alarm + operator response", "TAH-2022", "Tube skin temperature alarm, operator reduces firing", 0.1),      # B2-17, B2-18
              ("SIF", "SIF-200-04", "High-high outlet temperature trip", 0.033)]},
    {"id": "S-200-05", "node": "V-201", "ie": "LIC-2031 / LV-2031 fails closed; condensate accumulates",
     "freq": 0.1, "conseq": "Condensate carry-over to the burners; fireball at the burner front", "sev": "Cat 2", "tol": 0.001,
     "mods": "Probability condensate is present 0.5", "sif": "SIF-200-05", "notes": None,
     # clean control: listed, deliberately not credited (no PFD)
     "ipls": [("Alarm + operator response", "LAH-2031", "High level alarm - shares LT-2031 with the initiating loop, not credited", None),
              ("SIF", "SIF-200-05", "High-high level trip", 0.02)]},
]

# ---- curated compensating measures --------------------------------------------------------------------

CURATOR = "JH (dummy)"
CURATED = [
    ("SIF-200-01", "FT-2002.FAL", "1", "independent_bpcs", "Valid while FT-2002 is in service and FAL-2002 is not shelved or suppressed.",
     "SIF-200-01 trips at 120 m3/h on FT-2001A/B/C. FT-2002 is the BPCS vortex meter on the same line, a separate transmitter on a separate system; FAL-2002 at 160 m3/h annunciates before the trip point.",
     "approved", CURATOR, "2026-10-02"),
    ("SIF-200-02", "PT-2014.PAL", "1", "independent_bpcs", "Valid while PT-2014 is in service and PAL-2014 is not shelved.",
     "SIF-200-02 trips at 0.35 barg on PT-2010A/B. PT-2014 is the BPCS monitoring transmitter on the burner header with its own tapping; PAL-2014 is rationalised at 0.6 barg, above the trip point.",
     "approved", CURATOR, "2026-10-02"),
    ("SIF-200-03", "", "", "gap", "",
     "SIF-200-03 trips at 2.8 barg on PT-2011 (1oo1). The only high pressure alarm, PAH-2012, shares PT-2012 with the PIC-2012 loop whose failure is the demand, so it is not a compensating measure. An independent PAH on PT-2014 is proposed under MOC-2026-041 and does not exist yet.",
     "gap", "", ""),
    ("SIF-200-04", "TT-2021.TAH", "1", "independent_bpcs", "Valid while TT-2021 is in service and TAH-2021 is not shelved.",
     "SIF-200-04 trips at 345 degC on TT-2020A/B/C. TAH-2021 at 330 degC is taken from the BPCS control transmitter TT-2021, independent of the SIS transmitters.",
     "approved", CURATOR, "2026-10-02"),
    ("SIF-200-04", "TT-2022.TAH", "2", "independent_bpcs", "Valid while TT-2022 is in service and TAH-2022 is not shelved.",
     "Tube skin temperature responds to the same over-firing; a second, slower indication behind TAH-2021.",
     "approved", CURATOR, "2026-10-02"),
    ("SIF-200-05", "LT-2031.LAH", "1", "independent_bpcs", "Valid while LT-2031 is in service and LAH-2031 is enabled and not shelved.",
     "SIF-200-05 trips at 900 mm on LT-2030A/B. LT-2031 is the BPCS DP transmitter on the same drum; LAH-2031 at 720 mm annunciates before the trip point.",
     "approved", CURATOR, "2026-10-09"),
]

# ---- management of change -----------------------------------------------------------------------------
# MOC no., title, change type, status, raised, approved, implemented, closed, tags, to revise, revised, originator, notes

MOCS = [
    # clean control: closed out properly; index and configuration both show 0-16 barg
    ("MOC-2026-031", "Re-range PT-2013 fuel gas supply pressure from 0-10 to 0-16 barg (new supply header rating)", "Instrument re-range",
     "Closed", "2026-06-09", "2026-06-16", "2026-06-30", "2026-07-07", "PT-2013; PAL-2013", "U200-INST-INDEX", "U200-INST-INDEX",
     "Instrument Engineer (dummy)", "Index re-issued; DCS point re-scaled on 2026-06-30"),
    # B2-05
    ("MOC-2026-034", "Extend the SIF-200-05 proof test interval from 12 to 24 months to align with the heater turnaround", "Proof test interval change",
     "Closed", "2026-07-14", "2026-07-28", "2026-08-04", "2026-08-11", "SIF-200-05; LT-2030A; LT-2030B; XV-2004",
     "U200-SRS-001; U200-SILV-001; U200-PTP-001", "U200-PTP-001", "Maintenance Planner (dummy)", "Maintenance plan changed to 24 months on 2026-08-04"),
    # B2-07
    ("MOC-2026-037", "Temporary: disable LAH-2031 while the LT-2031 impulse lines are re-routed", "Temporary alarm disable",
     "Closed", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-14", "LAH-2031; LT-2031", None, None,
     "Maintenance Planner (dummy)", "Alarm to be re-enabled when LT-2031 is back in service (returned 2026-10-13)"),
    # B2-15
    ("MOC-2026-039", "Lower the PAH-2041 expansion drum pressure alarm limit from 6.0 to 5.5 barg (new blanket gas regulator setting)", "Alarm setting change",
     "Closed", "2026-08-18", "2026-08-25", "2026-09-01", "2026-09-08", "PAH-2041; PT-2041", "U200-MADB-001; U200-ALM-REG", "U200-MADB-001; U200-ALM-REG",
     "Alarm Management Engineer (dummy)", None),
    # B2-13
    ("MOC-2026-041", "Add PAH-2014 at 2.4 barg on PT-2014, independent of PIC-2012 (LOPA revalidation action for S-200-03)", "New alarm",
     "Approved - awaiting implementation", "2026-09-15", "2026-10-01", None, None, "PAH-2014; PT-2014; SIF-200-03", "U200-MADB-001; U200-ALM-REG", None,
     "Functional Safety Engineer (dummy)", "Closes the gap recorded in the compensating measures register"),
    # clean control: cancelled, nothing changed anywhere
    ("MOC-2026-043", "Remove LAL-2031 fuel gas KO drum low level alarm (proposed as a nuisance alarm)", "Alarm removal",
     "Cancelled", "2026-09-22", None, None, "2026-10-06", "LAL-2031; LT-2031", "U200-MADB-001; U200-ALM-REG", None,
     "Operations Supervisor (dummy)", "Cancelled at the rationalisation review: the alarm guards against gas blow-by and is retained"),
    # clean control: temporary bypass, recorded and closed (OOS-200-0007)
    ("MOC-2026-044", "Temporary: bypass PT-2010A for transmitter replacement", "Temporary bypass",
     "Closed", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-28", "PT-2010A; MOS-2010A; SIF-200-02", None, None,
     "Maintenance Planner (dummy)", "Bypass 09:00-12:40 on 2026-10-28 (3.7 h); see out-of-service entry OOS-200-0007"),
    # clean control: still in review, nothing changed anywhere
    ("MOC-2026-046", "Increase the TAH-2023 on-delay from 30 s to 60 s (chattering during burner changes)", "Alarm setting change",
     "In review", "2026-11-03", None, None, None, "TAH-2023; TT-2023", "U200-MADB-001", None,
     "Alarm Management Engineer (dummy)", None),
]

# ---- out-of-service register --------------------------------------------------------------------------

OOS_HEADER = ["id", "element", "kind", "status", "start", "expiry", "authorised_by", "requester", "reason",
              "compensating_measures_confirmed", "notes"]
OOS = [
    # clean control: closed, matches MOC-2026-044 and the inactive MOS-2010A
    ("OOS-200-0007", "PT-2010A", "mos", "closed", "2026-10-28 09:00", "2026-10-28 13:00", "Shift Supervisor (dummy)", "Maintenance Planner (dummy)",
     "Transmitter replacement (MOC-2026-044)", "y", "Restored 12:40; MOS-2010A confirmed off"),
    # B2-24: still active on paper, more than ten days past expiry; MOS-2020C is off
    ("OOS-200-0008", "TT-2020C", "mos", "active", "2026-11-01 08:00", "2026-11-01 16:00", "Shift Supervisor (dummy)", "Instrument Technician (dummy)",
     "Thermowell inspection", "y", ""),
    # B2-18: an alarm the LOPA credits
    ("OOS-200-0009", "TT-2022.TAH", "shelve", "active", "2026-11-09 14:00", "2026-11-16 14:00", "Shift Supervisor (dummy)", "Panel Operator (dummy)",
     "Skin thermocouple reading erratic; nuisance alarm", "n", "Awaiting thermocouple replacement"),
    # clean control: active, recorded, inside the 8 h the SRS allows
    ("OOS-200-0010", "FT-2001B", "mos", "active", "2026-11-12 02:10", "2026-11-12 10:10", "Shift Supervisor (dummy)", "Instrument Technician (dummy)",
     "Impulse line blockage - flushing", "y", "FAL-2002 confirmed active before the override was set"),
    # B2-06: nothing here for LT-2030A / MOS-2030A
]

# ---- document register --------------------------------------------------------------------------------
# document no., title, type, rev, covers

SIF_IDS = [s["id"] for s in SIFS]
DOCREG = [
    ("U200-SRS-001", "Safety Requirements Specification - Unit 200", "SRS", REV["U200-SRS-001"], "; ".join(SIF_IDS + [LOGIC_SOLVER])),
    ("U200-LOPA-001", "LOPA Report - Unit 200", "LOPA", REV["U200-LOPA-001"], "; ".join(SIF_IDS + ["H-201", "V-201"])),
    ("U200-SILV-001", "SIL Verification Calculations - Unit 200", "SIL verification", REV["U200-SILV-001"], "; ".join(SIF_IDS)),
    ("U200-CE-CHART", "Cause & Effect Chart - Unit 200", "C&E", REV["U200-CE-CHART"], "; ".join(SIF_IDS)),
    ("U200-INST-INDEX", "Instrument Index - Unit 200", "Instrument index", REV["U200-INST-INDEX"], UNIT),
    ("U200-LOOP-REG", "Loop Register - Unit 200 (sheet of the instrument index workbook)", "Instrument index", REV["U200-LOOP-REG"], UNIT),
    ("U200-ALM-REG", "Alarm Register - Unit 200 (sheet of the instrument index workbook)", "Instrument index", REV["U200-ALM-REG"], UNIT),
    ("U200-ALM-PHIL", "Alarm Philosophy and Rationalisation - Unit 200", "Alarm philosophy", "A", UNIT),
    ("U200-OP-PROC-010", "Operating Procedure - Hot Oil Heater Start-up and Shutdown", "Operating procedure", "D", "H-201; XV-2001; XV-2002; HV-2001; HS-2001"),
    ("U200-OP-PROC-020", "SIS Bypass Management Procedure", "SIS bypass procedure", "B",
     "; ".join(SIF_IDS[:4])),                                 # B2-23: SIF-200-05 is not covered
    ("U200-PTP-001", "SIS Proof Test Procedures - Unit 200", "Proof test procedure", "C", "; ".join(SIF_IDS)),
    ("U200-LOOP-2001", "Loop Drawings FT-2001A/B/C", "Loop drawing", "A", "FT-2001A; FT-2001B; FT-2001C"),
    ("U200-SIS-IO-001", "SIS I/O Allocation and Application Logic - SIS-LS-200", "SIS logic", "B", LOGIC_SOLVER),
    ("U200-MADB-001", "Master Alarm Database - Unit 200", "MADB", REV["U200-MADB-001"],
     "; ".join(a["tag"] for a in ALARMS if a["status"] != "Removed")),
    ("U200-CFG-EXPORT", "DCS / SIS Configuration Export - Unit 200", "Configuration export", REV["U200-CFG-EXPORT"], f"{DCS}; {LOGIC_SOLVER}"),
    ("U200-MOC-REG", "Management of Change Register - Unit 200", "MOC register", REV["U200-MOC-REG"], UNIT),
    ("U200-DOC-REGISTER", "Document Register - Unit 200", "Document register", REV["U200-DOC-REGISTER"], UNIT),
    # The index names these two drawings; no P&ID PDF is part of this set, so the register is their only record.
    ("PID-200-001", "P&ID - Hot Oil Heater H-201 and Hot Oil Circuit", "P&ID", "D",
     "; ".join(["H-201", "V-202"] + [i["tag"] for i in INSTRUMENTS if i["pid"] == "PID-200-001"])),
    ("PID-200-002", "P&ID - Fuel Gas System", "P&ID", "C",
     "; ".join(["V-201"] + [i["tag"] for i in INSTRUMENTS if i["pid"] == "PID-200-002"])),
]


# ======================================================================================================
# Tables
# ======================================================================================================

@dataclass
class Table:
    file: str
    sheet: str | None            # None for a CSV
    pre: list                    # rows above the header
    header: list
    rows: list
    sub: list = field(default_factory=list)      # rows between the header and the data (the C&E action row)
    style: str = "plain"                         # "index": navy header, frozen panes
    width: int | None = 22

    def find(self, row, **where) -> list:
        """Data rows whose first cell is `row` (and whose named columns hold the given values)."""
        out = []
        for r in self.rows:
            if r[0] != row:
                continue
            if all(r[self.header.index(c)] == v for c, v in where.items()):
                out.append(r)
        return out


def _titles(title: str, doc: str, status: str) -> list:
    return [[title], [f"Document No. {doc}    Rev {REV[doc]}    Status: {status}    {DUMMY}"], []]


def _rng(lo_hi) -> str | None:
    if lo_hi is None:
        return None
    lo, hi = lo_hi
    return f"{lo} to {hi}" if lo < 0 else f"{lo}-{hi}"


def _months(n: int) -> str:
    return f"{n} months"


def _sig(x: float, n: int = 3) -> float:
    return float(f"{x:.{n - 1}e}")


def _pfd(voting: str, lam: float, beta: float, months: int) -> float:
    """Simplified low-demand equations (dummy): enough to make the SIL verification self-consistent."""
    lt = lam * months * H_PER_MONTH
    if voting == "1oo1":
        return lt / 2
    if voting == "2oo2":
        return lt
    if voting == "1oo2":
        return lt ** 2 / 3 + beta * lt / 2
    if voting == "2oo3":
        return lt ** 2 + beta * lt / 2
    raise ValueError(voting)


def _sil(pfd: float) -> int:
    return 3 if pfd < 1e-3 else 2 if pfd < 1e-2 else 1 if pfd < 1e-1 else 0


def _kind(tag: str) -> str:
    return tag.split("-")[0]


def silv_numbers(s: dict, sensor_voting: str | None = None, fe_voting: str | None = None,
                 pti_s: int | None = None, pti_fe: int | None = None) -> dict:
    """PFD of one SIF as the SIL verification calculates it (or with one subsystem degraded / re-timed)."""
    sv, fv = sensor_voting or s["voting"], fe_voting or s["fe_voting"]
    ps = _sig(_pfd(sv, LAMBDA[_kind(s["sensors"][0])], BETA_S if sv not in ("1oo1", "2oo2") else 0, pti_s or s["pti_s"]))
    pf = _sig(_pfd(fv, LAMBDA["XV"], BETA_FE if fv not in ("1oo1", "2oo2") else 0, pti_fe or s["pti_fe"]))
    total = _sig(ps + PFD_LS + pf)
    return {"sensors": ps, "fe": pf, "total": total, "rrf": int(round(1 / total)), "sil": _sil(total)}


def build_tables() -> dict:
    t: dict[tuple, Table] = {}

    def add(table: Table) -> None:
        t[(table.file, table.sheet)] = table

    # ---- instrument index workbook ----
    add(Table(F_INDEX, "Cover", [], ["UNIT 200 - HOT OIL HEATER"], [
        [], ["INSTRUMENT INDEX"], [], ["Document No.", "U200-INST-INDEX"], ["Revision", REV["U200-INST-INDEX"]],
        ["Status", "As Built"], ["Sheets", "Instrument Index, Loop Register, Alarm Register"],
        ["Note", "DUMMY DATA generated for a blind test of the cross-document checks. Not a real facility."]],
        style="cover", width=None))
    add(Table(F_INDEX, "Instrument Index", _titles("INSTRUMENT INDEX - UNIT 200", "U200-INST-INDEX", "As Built"),
              ["Tag No.", "Service Description", "Instrument Type", "Loop No.", "Area / Unit", "P&ID No.", "Line / Equipment No.",
               "System", "Range", "Units", "Signal", "Remarks"],
              [[i["tag"], i["service"], i["type"], i["loop"], UNIT, i["pid"], i["loc"], i["system"], _rng(i["range"]), i["units"],
                i["signal"], i["remarks"]] for i in INSTRUMENTS], style="index", width=None))
    add(Table(F_INDEX, "Loop Register", _titles("LOOP REGISTER - UNIT 200", "U200-LOOP-REG", "As Built"),
              ["Loop No.", "Service Description", "Sensor", "Final Element", "Protected Equipment", "System"],
              [[lp, svc, sen, fe, eq, "BPCS"] for lp, svc, sen, fe, eq in LOOPS], style="index", width=None))
    add(Table(F_INDEX, "Alarm Register", _titles("ALARM REGISTER - UNIT 200", "U200-ALM-REG", "As Built"),
              ["Alarm Tag", "Source Tag", "Setpoint", "Priority", "System", "Protected Equipment", "Alarm Description"],
              [[a["tag"], a["source"], f"{a['sp']} {a['units']}", a["prio"], "BPCS", a["protects"], a["desc"]]
               for a in ALARMS if a["in_register"]], style="index", width=None))

    # ---- cause & effect chart (matrix form) ----
    effects = ["XV-2001", "XV-2002", "XV-2004"]
    ce_rows = []
    for s in SIFS:
        closes = s.get("built_fes", s["fes"])
        for k, cause in enumerate(s["sensors"]):
            first = k == 0
            ce_rows.append([s["id"] if first else None, s["desc"] if first else None, str(s["sil"]) if first else None,
                            LOGIC_SOLVER if first else None, cause, s["cause_desc"], s.get("ce_voting", s["voting"]),
                            f"{s['sp']} {s['sp_units']}", s["protects"] if first else None, None]
                           + ["X" if e in closes else None for e in effects])
    add(Table(F_CE, "CE-200",
              [["CAUSE & EFFECT CHART - " + UNIT_TITLE],
               [f"Document No. U200-CE-CHART    Rev {REV['U200-CE-CHART']}    Status: As Built    {DUMMY}"],
               ["Legend: X = cause initiates effect. Voting per cause group. Effect action shown under each effect tag."], []],
              ["SIF No.", "SIF Description", "SIL", "Logic Solver", "Cause Tag", "Cause Description", "Voting", "Setpoint",
               "Protected Equipment", None] + effects,
              ce_rows, sub=[["EFFECTS ->"] + [None] * 9 + ["Close"] * len(effects)], style="ce", width=None))

    # ---- SRS ----
    def pti_text(s):
        return _months(s["pti_s"]) if s["pti_s"] == s["pti_fe"] else \
            f"Sensors {_months(s['pti_s'])}, final elements {_months(s['pti_fe'])}"

    def bypass_text(s):
        return s.get("bypass") or f"One channel at a time, with {s['comp']} confirmed active; max {s['max_bypass']} h"

    add(Table(F_SRS, "SIF Requirements", _titles("SAFETY REQUIREMENTS SPECIFICATION - " + UNIT_TITLE, "U200-SRS-001", "As Built"),
              ["SIF No.", "Functional Description", "Hazard / Consequence", "SIL Target", "RRF Target", "PFDavg Target", "Demand Mode",
               "Safe State", "Process Safety Time", "SIF Response Time", "Trip Setpoint", "Sensor Architecture",
               "Final Element Architecture", "Proof Test Interval", "Bypass Conditions", "Manual Shutdown", "Reset", "Logic Solver",
               "Protected Equipment"],
              [[s["id"], s["func"], s["hazard"], s["sil"], s["rrf"], s["pfd_target"], "Low demand",
                ", ".join(f"{fe} closed" for fe in s["fes"]), s["pst"], s["resp"], s.get("srs_sp") or f"{s['sp']} {s['sp_units']}",
                f"{s['voting']} {_kind(s['sensors'][0])}", f"{s['fe_voting']} ({' or '.join(s['fes'])})", pti_text(s), bypass_text(s),
                "HS-2001 on panel", "Manual, after the cause has cleared", LOGIC_SOLVER, s["protects"]] for s in SIFS]))

    # ---- LOPA ----
    add(Table(F_LOPA, "Scenarios", _titles("LAYER OF PROTECTION ANALYSIS - " + UNIT_TITLE, "U200-LOPA-001", "Revalidated"),
              ["Scenario No.", "Node / Equipment", "Initiating Event", "IE Frequency (/yr)", "Consequence", "Severity",
               "Tolerable Frequency (/yr)", "Conditional Modifiers", "Required SIF", "Required RRF", "Required SIL", "Notes"],
              [[c["id"], c["node"], c["ie"], c["freq"], c["conseq"], c["sev"], c["tol"], c["mods"], c["sif"], SIF[c["sif"]]["rrf"],
                SIF[c["sif"]]["sil"], c["notes"]] for c in SCENARIOS], width=24))
    add(Table(F_LOPA, "IPLs", _titles("LOPA - INDEPENDENT PROTECTION LAYERS CREDITED", "U200-LOPA-001", "Revalidated"),
              ["Scenario No.", "IPL Type", "Tag", "Description", "PFD Credited"],
              [[c["id"], typ, tag, desc, pfd] for c in SCENARIOS for typ, tag, desc, pfd in c["ipls"]], width=24))

    # ---- master alarm database ----
    add(Table(F_MADB, "Alarms", _titles("MASTER ALARM DATABASE - UNIT 200", "U200-MADB-001", "Rationalised"),
              ["Alarm Tag", "Source Tag", "Description", "Alarm Type", "Setpoint", "Units", "Priority", "Alarm Class", "Cause",
               "Consequence of No Action", "Operator Action", "Time to Respond", "Deadband", "On-delay", "Off-delay", "IPL Credit",
               "LOPA Ref", "Rationalisation Outcome", "Implementation Status", "Rationalised", "Team"],
              [[a["tag"], a["source"], a["desc"], f"Absolute {a['kind']}", a["sp"], a["units"], a["prio"], a["cls"], a["cause"],
                a["conseq"], a["action"], a["ttr"], a["deadband"], a["on_delay"], "0 s", a["ipl"], a["lopa"], a["outcome"],
                a["status"], RATIONALISED, TEAM] for a in ALARMS]))

    # ---- configuration export ----
    cfg_status = f"Configuration export {EXPORT_TIME} from DCS-200 and {LOGIC_SOLVER}"

    def cfg_titles(what):
        return _titles(f"DCS / SIS CONFIGURATION EXPORT - UNIT 200 - {what}", "U200-CFG-EXPORT", cfg_status)

    points = []
    for i in INSTRUMENTS:
        if i["cfg"] is None:
            continue
        block, io = i["cfg"]
        system, controller = ("SIS", LOGIC_SOLVER) if i["system"] == "SIS" else ("DCS", DCS)
        if i["tag"] in CFG_HOME:
            system, controller, io = CFG_HOME[i["tag"]]
        lo, hi, units = (*i["range"], i["units"]) if i["range"] else (None, None, None)
        if i["tag"] in CFG_RANGE:
            lo, hi, units = CFG_RANGE[i["tag"]]
        points.append([i["tag"], system, controller, block, io, lo, hi, units, i["service"], i["loop"]])
    points += [list(p) for p in CFG_ONLY_POINTS]
    points += [[lp, "DCS", DCS, "PID", None, None, None, None, svc, lp] for lp, svc, *_ in LOOPS]
    add(Table(F_CFG, "Points", cfg_titles("POINTS"),
              ["Point Tag", "System", "Controller", "Block Type", "I/O Channel", "Range Low", "Range High", "Units", "Description", "Loop"],
              points))
    add(Table(F_CFG, "Alarms", cfg_titles("ALARMS"),
              ["Alarm Tag", "Source Tag", "System", "Alarm Type", "Limit", "Units", "Priority", "Deadband", "On-delay", "Enabled"],
              [[a["tag"], a.get("cfg_source", a["source"]), "DCS", "HI" if a["kind"] == "high" else "LO", a.get("cfg_limit", a["sp"]),
                a.get("cfg_units", a["units"]), a.get("cfg_prio", a["prio"]), a.get("cfg_deadband", a["deadband"]), a["on_delay"],
                a.get("cfg_enabled", "Yes")] for a in ALARMS if a["in_cfg"]] + [list(TRIP_NOTIFY)]))
    add(Table(F_CFG, "SIS Trips", cfg_titles("SIS TRIPS"),
              ["SIF No.", "Logic Solver", "Initiators", "Voting", "Trip Setpoint", "Units", "Direction", "Final Elements", "Action",
               "Trip Enabled"],
              [[s["id"], LOGIC_SOLVER, ", ".join(s["sensors"]), s.get("cfg_voting", s["voting"]), s.get("cfg_sp", s["sp"]),
                s["sp_units"], s["direction"], ", ".join(s.get("built_fes", s["fes"])),
                ", ".join(f"{fe} close" for fe in s.get("built_fes", s["fes"])), "Yes"] for s in SIFS]))
    overrides = []
    for s in SIFS:
        for sensor in s["sensors"]:
            mos = "MOS-" + sensor.split("-")[1]
            since = MOS_ACTIVE.get(mos)
            overrides.append([mos, s["id"], sensor, s["deg_s"][1] or LOST, s.get("cfg_mos_max", s["max_bypass"]), "Alarm only",
                              "Medium", "Yes" if since else "No", since])
    add(Table(F_CFG, "Overrides", cfg_titles("MAINTENANCE OVERRIDES"),
              ["Override Tag", "SIF No.", "Element", "Degraded Voting", "Max Duration (h)", "Timeout Action",
               "Override Alarm Priority", "Active", "Active Since"], overrides))

    # ---- SIL verification ----
    summary, subsystems, degraded = [], [], []
    note = "Degraded voting assumed in the logic solver while one channel is overridden"
    for s in SIFS:
        n = silv_numbers(s)
        src_rev = s.get("silv_source_rev", REV["U200-SRS-001"])
        summary.append([s["id"], s["sil"], f"U200-SRS-001 Rev {src_rev}", s.get("silv_rrf_target", s["rrf"]), ", ".join(s["sensors"]),
                        s["voting"], LOGIC_SOLVER, ", ".join(s["fes"]), s["fe_voting"], n["sensors"], PFD_LS, n["fe"], n["total"],
                        n["rrf"], n["sil"], _months(s["pti_s"]), _months(s["pti_fe"]), "Meets target"])
        subsystems.append([s["id"], "Sensors", ", ".join(s["sensors"]), s["voting"], LAMBDA[_kind(s["sensors"][0])],
                           BETA_S if len(s["sensors"]) > 1 else 0, s["pti_s"] * H_PER_MONTH, n["sensors"], "Generic data (dummy)"])
        subsystems.append([s["id"], "Final elements", ", ".join(s["fes"]), s["fe_voting"], LAMBDA["XV"],
                           BETA_FE if len(s["fes"]) > 1 else 0, s["pti_fe"] * H_PER_MONTH, n["fe"], "Generic data (dummy)"])
        subsystems.append([s["id"], "Logic solver", LOGIC_SOLVER, "1oo1D", None, None, None, PFD_LS, "Vendor certificate (dummy)"])
        for (element, deg), normal, which in ((s["deg_s"], s["voting"], "sensor_voting"), (s["deg_fe"], s["fe_voting"], "fe_voting")):
            if deg is None:
                degraded.append([s["id"], element, normal, LOST, None, None, f"{s['max_bypass']} h",
                                 "No protection while bypassed. Compensating measures per the SRS bypass conditions."])
            else:
                d = silv_numbers(s, **{which: deg})
                degraded.append([s["id"], element, normal, deg, d["total"], d["sil"], f"{s['max_bypass']} h", note])
    add(Table(F_SILV, "SIF Summary", _titles("SIL VERIFICATION - " + UNIT_TITLE, "U200-SILV-001", "As Built"),
              ["SIF No.", "SIL Target", "Target Source", "RRF Target", "Sensor Tags", "Sensor Voting", "Logic Solver",
               "Final Element Tags", "Final Element Voting", "PFD Sensors", "PFD Logic Solver", "PFD Final Elements", "PFDavg",
               "RRF Achieved", "SIL Achieved", "Proof Test Interval - Sensors", "Proof Test Interval - Final Elements", "Result"], summary))
    add(Table(F_SILV, "Subsystems", _titles("SIL VERIFICATION - SUBSYSTEM DATA", "U200-SILV-001", "As Built"),
              ["SIF No.", "Subsystem", "Tags", "Voting", "Lambda DU (/h)", "Beta", "Proof Test Interval (h)", "PFDavg", "Data Source"],
              subsystems))
    add(Table(F_SILV, "Degraded Operation", _titles("SIL VERIFICATION - ONE ELEMENT BYPASSED", "U200-SILV-001", "As Built"),
              ["SIF No.", "Element Bypassed", "Normal Voting", "Degraded Voting Assumed", "PFDavg Degraded", "SIL Degraded",
               "SRS Max Bypass", "Note"], degraded))

    # ---- MOC register ----
    add(Table(F_MOC, "Register", _titles("MANAGEMENT OF CHANGE REGISTER - UNIT 200", "U200-MOC-REG", "Live register"),
              ["MOC No.", "Title", "Change Type", "Status", "Raised", "Approved", "Implemented", "Closed", "Tags Affected",
               "Documents to Revise", "Documents Revised", "Originator", "Notes"], [list(m) for m in MOCS]))

    # ---- CSV registers ----
    add(Table(F_DOCREG, None,
              [["DOCUMENT REGISTER - UNIT 200"],
               [f"Document No. U200-DOC-REGISTER    Rev {REV['U200-DOC-REGISTER']}    Status: Current    {DUMMY}"], []],
              ["Document No.", "Title", "Type", "Rev", "Covers"], [list(d) for d in DOCREG]))
    add(Table(F_CURATED, None, [], ["sif_id", "alarm_id", "rank", "basis", "conditions", "rationale", "status", "curated_by", "date"],
              [list(c) for c in CURATED]))
    add(Table(F_OOS, None, [], OOS_HEADER, [list(o) for o in OOS]))
    return t


# ======================================================================================================
# Answer key (built from the tables above)
# ======================================================================================================

class Key:
    def __init__(self, tables: dict):
        self.t = tables
        self.items: list[dict] = []

    def ev(self, file, sheet, row, column, **where) -> dict:
        """One evidence cell, read from the finished table. `where` only picks the row; it is not stored."""
        table = self.t[(file, sheet)]
        hits = table.find(row, **where)
        if not hits:
            raise KeyError(f"{file}:{sheet}: no row {row!r} {where or ''}")
        values = {json.dumps(r[table.header.index(column)]) for r in hits}
        if len(values) != 1:
            raise KeyError(f"{file}:{sheet}:{row}:{column}: ambiguous, add a where= ({values})")
        return {"file": file, "sheet": sheet, "row": row, "column": column, "value": hits[0][table.header.index(column)]}

    def absent(self, file, sheet, row, column=None) -> dict:
        table = self.t[(file, sheet)]
        j = table.header.index(column) if column else 0
        if any(r[j] == row for r in table.rows):
            raise KeyError(f"{file}:{sheet}: {row!r} is present, cannot be listed as absent")
        out = {"file": file, "sheet": sheet, "row": row}
        if column:
            out["column"] = column
        return out

    def add(self, category, severity, tags, documents, finding, evidence, absent=()) -> None:
        self.items.append({"id": f"B2-{len(self.items) + 1:02d}", "category": category, "severity": severity, "tags": tags,
                           "documents": documents, "finding": finding, "evidence": list(evidence), "absent": list(absent)})


def build_key(t: dict) -> dict:
    k = Key(t)
    ev, absent = k.ev, k.absent
    SRS, CE, LOPA, MADB, CFG, SILV, MOC = "U200-SRS-001", "U200-CE-CHART", "U200-LOPA-001", "U200-MADB-001", "U200-CFG-EXPORT", "U200-SILV-001", "U200-MOC-REG"
    # the two CSV registers carry no document number: the curated one goes by the name its loader gives it, the
    # out-of-service register by its file name
    IDX, ALM, REG, CUR, OOSD = "U200-INST-INDEX", "U200-ALM-REG", "U200-DOC-REGISTER", "COMPENSATING-MEASURES-U-200", "out_of_service_U-200"
    s1, s2, s3, s4, s5 = SIFS
    as_built_03 = silv_numbers(s3, fe_voting="1oo1")
    at_24_05 = silv_numbers(s5, pti_s=24, pti_fe=24)
    got_01 = silv_numbers(s1)["rrf"]
    # The findings below state these relations; fail here rather than seal a key that is not true.
    assert s1["silv_rrf_target"] < got_01 < s1["rrf"], "B2-04 needs target(SILV) < achieved < target(SRS, LOPA)"
    assert at_24_05["rrf"] < s5["rrf"] <= silv_numbers(s5)["rrf"], "B2-05 needs the 24-month case to miss the target"
    assert ALARM["PAL-2014"]["cfg_limit"] < s2["sp"] < ALARM["PAL-2014"]["sp"], "B2-14 needs the limit beyond the trip"
    assert as_built_03["rrf"] < 10 * s3["rrf"], "B2-13 / B2-03 interaction needs the as-built function short of 10x"

    # B2-01
    k.add("trip setpoint", "high", ["SIF-200-04", "TT-2020A", "TT-2020B", "TT-2020C"], [SRS, CE, CFG],
          "The SRS and the cause & effect chart set the SIF-200-04 hot oil outlet temperature trip at 345 degC; the SIS as exported "
          "trips at 355 degC. No MOC covers the change, so the running trip sits 10 degC closer to the film-temperature limit than "
          "the design basis says.",
          [ev(F_SRS, "SIF Requirements", "SIF-200-04", "Trip Setpoint"), ev(F_CE, "CE-200", "SIF-200-04", "Setpoint"),
           ev(F_CFG, "SIS Trips", "SIF-200-04", "Trip Setpoint")])
    # B2-02
    k.add("sensor voting", "high", ["SIF-200-02", "PT-2010A", "PT-2010B"], [SRS, SILV, CE, CFG],
          "The SRS requires 1oo2 voting on the fuel gas low pressure transmitters and the SIL verification is calculated for 1oo2, "
          "but the cause & effect chart and the configured logic are 2oo2. Either transmitter failing dangerously now defeats the "
          "trip, which the calculation does not reflect.",
          [ev(F_SRS, "SIF Requirements", "SIF-200-02", "Sensor Architecture"), ev(F_SILV, "SIF Summary", "SIF-200-02", "Sensor Voting"),
           ev(F_CE, "CE-200", "SIF-200-02", "Voting"), ev(F_CFG, "SIS Trips", "SIF-200-02", "Voting")])
    # B2-03
    k.add("final element architecture", "high", ["SIF-200-03", "XV-2001", "XV-2002"], [SRS, SILV, CE, CFG],
          "The SRS and the SIL verification give SIF-200-03 two final elements voted 1oo2 (XV-2001 or XV-2002). The cause & effect "
          "chart marks only XV-2001 for this function and the configured trip drives only XV-2001, so the function as built is "
          f"1oo1 on the final element (about RRF {as_built_03['rrf']} on the calculation's own data, against {silv_numbers(s3)['rrf']} claimed).",
          [ev(F_SRS, "SIF Requirements", "SIF-200-03", "Final Element Architecture"),
           ev(F_SILV, "SIF Summary", "SIF-200-03", "Final Element Tags"), ev(F_SILV, "SIF Summary", "SIF-200-03", "Final Element Voting"),
           ev(F_CE, "CE-200", "SIF-200-03", "XV-2001"), ev(F_CE, "CE-200", "SIF-200-03", "XV-2002"),
           ev(F_CFG, "SIS Trips", "SIF-200-03", "Final Elements")])
    # B2-04
    k.add("SIL verification basis", "high", ["SIF-200-01"], [LOPA, SRS, SILV, REG],
          "The LOPA requires a risk reduction factor of 200 from SIF-200-01 and the current SRS (Rev C) carries that target. The SIL "
          f"verification for this function still cites SRS Rev B and a target of 120, achieves {got_01} and reports 'Meets target'. "
          "The SIL band matches, so the shortfall against the current requirement is hidden.",
          [ev(F_LOPA, "Scenarios", "S-200-01", "Required RRF"), ev(F_SRS, "SIF Requirements", "SIF-200-01", "RRF Target"),
           ev(F_SILV, "SIF Summary", "SIF-200-01", "Target Source"), ev(F_SILV, "SIF Summary", "SIF-200-01", "RRF Target"),
           ev(F_SILV, "SIF Summary", "SIF-200-01", "RRF Achieved"), ev(F_SILV, "SIF Summary", "SIF-200-01", "Result"),
           ev(F_DOCREG, None, "U200-SRS-001", "Rev")])
    # B2-05
    k.add("proof test interval", "medium", ["SIF-200-05", "LT-2030A", "LT-2030B", "XV-2004"], [MOC, SRS, SILV],
          "MOC-2026-034 is closed and moved the SIF-200-05 proof test interval from 12 to 24 months, but of the three documents it "
          "lists only the proof test procedure was revised: the SRS and the SIL verification still say 12 months. On the "
          f"calculation's own data the function gives about RRF {at_24_05['rrf']} at 24 months, below its target of {s5['rrf']}.",
          [ev(F_MOC, "Register", "MOC-2026-034", "Title"), ev(F_MOC, "Register", "MOC-2026-034", "Status"),
           ev(F_MOC, "Register", "MOC-2026-034", "Documents to Revise"), ev(F_MOC, "Register", "MOC-2026-034", "Documents Revised"),
           ev(F_SRS, "SIF Requirements", "SIF-200-05", "Proof Test Interval"),
           ev(F_SILV, "SIF Summary", "SIF-200-05", "Proof Test Interval - Sensors"),
           ev(F_SILV, "SIF Summary", "SIF-200-05", "Proof Test Interval - Final Elements"),
           ev(F_SILV, "SIF Summary", "SIF-200-05", "RRF Target")])
    # B2-06
    k.add("unrecorded override", "high", ["LT-2030A", "MOS-2030A", "SIF-200-05"], [CFG, OOSD, SRS],
          "The SIS export shows maintenance override MOS-2030A on LT-2030A active since 2026-11-08 09:15, almost four days before "
          "the export, yet the out-of-service register has no entry for it. The SRS allows a bypass on this function for 4 h at most.",
          [ev(F_CFG, "Overrides", "MOS-2030A", "Element"), ev(F_CFG, "Overrides", "MOS-2030A", "Active"),
           ev(F_CFG, "Overrides", "MOS-2030A", "Active Since"), ev(F_CFG, "Overrides", "MOS-2030A", "Max Duration (h)"),
           ev(F_SRS, "SIF Requirements", "SIF-200-05", "Bypass Conditions")],
          [absent(F_OOS, None, "LT-2030A", "element"), absent(F_OOS, None, "MOS-2030A", "element")])
    # B2-07
    k.add("alarm left disabled", "medium", ["LAH-2031", "LT-2031"], [CFG, MADB, MOC],
          "LAH-2031 is disabled in the DCS export although the master alarm database records it as a High priority safety alarm, "
          "implemented. The temporary change that disabled it (MOC-2026-037) was closed on 2026-10-14 without the alarm being "
          "re-enabled.",
          [ev(F_CFG, "Alarms", "LAH-2031", "Enabled"), ev(F_MADB, "Alarms", "LAH-2031", "Implementation Status"),
           ev(F_MADB, "Alarms", "LAH-2031", "Priority"), ev(F_MOC, "Register", "MOC-2026-037", "Status"),
           ev(F_MOC, "Register", "MOC-2026-037", "Closed")])
    # B2-08
    k.add("interaction: bypass without its compensating measure", "high", ["SIF-200-05", "LT-2030A", "MOS-2030A", "LAH-2031"],
          [CFG, SRS, CUR, MADB],
          "Read together, B2-06 and B2-07 leave SIF-200-05 running 1oo1 on LT-2030B with no working compensating measure: the SRS "
          "permits the bypass only with LAH-2031 confirmed active, and LAH-2031 is the one approved compensating alarm in the "
          "curated register, but that alarm is disabled.",
          [ev(F_CFG, "Overrides", "MOS-2030A", "Active"), ev(F_CFG, "Overrides", "MOS-2030A", "Degraded Voting"),
           ev(F_SRS, "SIF Requirements", "SIF-200-05", "Bypass Conditions"),
           ev(F_CURATED, None, "SIF-200-05", "alarm_id"), ev(F_CURATED, None, "SIF-200-05", "status"),
           ev(F_CFG, "Alarms", "LAH-2031", "Enabled"), ev(F_MADB, "Alarms", "LAH-2031", "Implementation Status")])
    # B2-09
    k.add("override time limit", "medium", ["SIF-200-04", "MOS-2020A", "MOS-2020B", "MOS-2020C"], [SRS, SILV, CFG],
          "The SRS limits a bypass of a SIF-200-04 temperature channel to 8 h and the SIL verification's degraded case assumes that "
          "limit; the three override switches are configured with a 24 h maximum, alarm only on time-out.",
          [ev(F_SRS, "SIF Requirements", "SIF-200-04", "Bypass Conditions"),
           ev(F_SILV, "Degraded Operation", "SIF-200-04", "SRS Max Bypass", **{"Element Bypassed": "One of TT-2020A/B/C"}),
           ev(F_CFG, "Overrides", "MOS-2020A", "Max Duration (h)"), ev(F_CFG, "Overrides", "MOS-2020B", "Max Duration (h)"),
           ev(F_CFG, "Overrides", "MOS-2020C", "Max Duration (h)")])
    # B2-10
    k.add("instrument range", "medium", ["PT-2010B", "SIF-200-02"], [IDX, CFG],
          "PT-2010B is 0-4 barg in the instrument index, like its partner PT-2010A, but the SIS point is scaled 0-6 barg. If the "
          "transmitter is calibrated as the index says, channel B reads 50 % high and the two channels of SIF-200-02 disagree.",
          [ev(F_INDEX, "Instrument Index", "PT-2010B", "Range"), ev(F_INDEX, "Instrument Index", "PT-2010B", "Units"),
           ev(F_CFG, "Points", "PT-2010B", "Range Low"), ev(F_CFG, "Points", "PT-2010B", "Range High"),
           ev(F_CFG, "Points", "PT-2010A", "Range High")])
    # B2-11
    k.add("tag in one document only", "low", ["TT-2026"], [CFG, IDX],
          "TT-2026 (combustion air temperature) is a configured DCS point that appears in no other document: not in the instrument "
          "index, not in any MOC.",
          [ev(F_CFG, "Points", "TT-2026", "Description"), ev(F_CFG, "Points", "TT-2026", "I/O Channel")],
          [absent(F_INDEX, "Instrument Index", "TT-2026")])
    # B2-12
    k.add("alarm not configured", "medium", ["PDAH-2003", "PDT-2003"], [MADB, ALM, CFG],
          "PDAH-2003 is rationalised and marked 'Implemented' in the master alarm database and listed in the alarm register, but "
          "the DCS export has no such alarm on PDT-2003. The operator will never see it.",
          [ev(F_MADB, "Alarms", "PDAH-2003", "Implementation Status"), ev(F_INDEX, "Alarm Register", "PDAH-2003", "Setpoint"),
           ev(F_CFG, "Points", "PDT-2003", "Block Type")],
          [absent(F_CFG, "Alarms", "PDAH-2003")])
    # B2-13
    k.add("credited alarm does not exist", "high", ["PAH-2014", "PT-2014", "SIF-200-03", "S-200-03"], [LOPA, SRS, MADB, ALM, CFG, MOC, CUR],
          "LOPA scenario S-200-03 credits alarm PAH-2014 with a PFD of 0.1 and the SRS makes PAH-2014 the condition for bypassing "
          "SIF-200-03, but the alarm does not exist: it is in neither alarm list nor the DCS, and the MOC to add it is only "
          "approved. Without it the scenario needs ten times the risk reduction from SIF-200-03 (see also B2-03).",
          [ev(F_LOPA, "IPLs", "S-200-03", "Tag", **{"IPL Type": "Alarm + operator response"}),
           ev(F_LOPA, "IPLs", "S-200-03", "PFD Credited", Tag="PAH-2014"), ev(F_LOPA, "Scenarios", "S-200-03", "Required RRF"),
           ev(F_SRS, "SIF Requirements", "SIF-200-03", "Bypass Conditions"), ev(F_MOC, "Register", "MOC-2026-041", "Status"),
           ev(F_CURATED, None, "SIF-200-03", "basis")],
          [absent(F_MADB, "Alarms", "PAH-2014"), absent(F_INDEX, "Alarm Register", "PAH-2014"), absent(F_CFG, "Alarms", "PAH-2014")])
    # B2-14
    k.add("alarm limit beyond the trip", "high", ["PAL-2014", "PT-2014", "SIF-200-02"], [MADB, ALM, CFG, CUR],
          "PAL-2014 is rationalised at 0.6 barg but configured at 0.3 barg, which is below the 0.35 barg low-low trip of SIF-200-02. "
          "The alarm the curated register approves as the compensating measure for that function cannot come in before the trip point.",
          [ev(F_MADB, "Alarms", "PAL-2014", "Setpoint"), ev(F_MADB, "Alarms", "PAL-2014", "Units"),
           ev(F_INDEX, "Alarm Register", "PAL-2014", "Setpoint"), ev(F_CFG, "Alarms", "PAL-2014", "Limit"),
           ev(F_CFG, "SIS Trips", "SIF-200-02", "Trip Setpoint"), ev(F_CFG, "SIS Trips", "SIF-200-02", "Direction"),
           ev(F_CURATED, None, "SIF-200-02", "alarm_id")])
    # B2-15
    k.add("change closed but not implemented", "medium", ["PAH-2041", "PT-2041"], [MOC, MADB, ALM, CFG],
          "MOC-2026-039 lowered the PAH-2041 limit from 6.0 to 5.5 barg and is closed with an implementation date; the master alarm "
          "database and the alarm register were revised to 5.5 barg, but the DCS still alarms at 6 barg.",
          [ev(F_MOC, "Register", "MOC-2026-039", "Status"), ev(F_MOC, "Register", "MOC-2026-039", "Implemented"),
           ev(F_MADB, "Alarms", "PAH-2041", "Setpoint"), ev(F_INDEX, "Alarm Register", "PAH-2041", "Setpoint"),
           ev(F_CFG, "Alarms", "PAH-2041", "Limit")])
    # B2-16
    k.add("alarm priority", "low", ["AAL-2024", "AT-2024"], [MADB, ALM, CFG],
          "AAL-2024 (flue gas oxygen low) is High priority in the master alarm database and the alarm register and Medium in the DCS.",
          [ev(F_MADB, "Alarms", "AAL-2024", "Priority"), ev(F_INDEX, "Alarm Register", "AAL-2024", "Priority"),
           ev(F_CFG, "Alarms", "AAL-2024", "Priority")])
    # B2-17
    k.add("IPL credit recorded against the wrong alarm", "medium", ["TAH-2022", "TAH-2021", "S-200-04"], [LOPA, MADB],
          "LOPA scenario S-200-04 credits the tube skin alarm TAH-2022 (and says TAH-2021 is not credited), but the master alarm "
          "database records the IPL credit for S-200-04 against TAH-2021 and treats TAH-2022 as a Medium priority operational alarm "
          "with no credit. The alarm the risk assessment relies on is not managed as a safeguard.",
          [ev(F_LOPA, "IPLs", "S-200-04", "Tag", **{"IPL Type": "Alarm + operator response"}),
           ev(F_LOPA, "IPLs", "S-200-04", "PFD Credited", Tag="TAH-2022"), ev(F_LOPA, "Scenarios", "S-200-04", "Notes"),
           ev(F_MADB, "Alarms", "TAH-2022", "IPL Credit"), ev(F_MADB, "Alarms", "TAH-2022", "Alarm Class"),
           ev(F_MADB, "Alarms", "TAH-2022", "Priority"), ev(F_MADB, "Alarms", "TAH-2021", "IPL Credit"),
           ev(F_MADB, "Alarms", "TAH-2021", "LOPA Ref")])
    # B2-18
    k.add("interaction: credited alarm shelved", "high", ["TAH-2022", "TT-2022", "S-200-04", "SIF-200-04"], [OOSD, LOPA, CUR],
          "TAH-2022 has been shelved since 2026-11-09 on a seven-day entry (OOS-200-0009, compensating measures not confirmed). It is the "
          "alarm LOPA scenario S-200-04 credits and a curated compensating measure for SIF-200-04, so the scenario is one layer "
          "short while it is shelved; B2-17 explains how the shelving could be authorised without anyone noticing.",
          [ev(F_OOS, None, "OOS-200-0009", "element"), ev(F_OOS, None, "OOS-200-0009", "kind"), ev(F_OOS, None, "OOS-200-0009", "status"),
           ev(F_OOS, None, "OOS-200-0009", "expiry"), ev(F_OOS, None, "OOS-200-0009", "compensating_measures_confirmed"),
           ev(F_LOPA, "IPLs", "S-200-04", "PFD Credited", Tag="TAH-2022"),
           ev(F_CURATED, None, "SIF-200-04", "alarm_id", rank="2")])
    # B2-19
    k.add("operator response time", "medium", ["FAL-2002", "FT-2002", "S-200-01", "SIF-200-01"], [MADB, SRS, LOPA],
          "The LOPA credits operator response to FAL-2002 with a PFD of 0.1 in scenario S-200-01. The master alarm database allows "
          "the operator 15 min to respond; the SRS gives the process safety time for the same loss-of-flow event as 90 s. The credit "
          "rests on a response the hazard does not leave time for.",
          [ev(F_MADB, "Alarms", "FAL-2002", "Time to Respond"), ev(F_MADB, "Alarms", "FAL-2002", "IPL Credit"),
           ev(F_SRS, "SIF Requirements", "SIF-200-01", "Process Safety Time"),
           ev(F_LOPA, "IPLs", "S-200-01", "PFD Credited", Tag="FAL-2002")])
    # B2-20
    k.add("SIF initiator on the control system", "high", ["PT-2011", "SIF-200-03"], [IDX, CFG, SRS],
          "PT-2011, the single initiator of SIF-200-03, is a SIS instrument in the index, but the export shows it as an analogue "
          "input of DCS controller DCS-200-C01 while the SIS trip still names it as its initiator. The trip signal passes through the "
          "control system whose failure is the demand.",
          [ev(F_INDEX, "Instrument Index", "PT-2011", "System"), ev(F_CFG, "Points", "PT-2011", "System"),
           ev(F_CFG, "Points", "PT-2011", "Controller"), ev(F_CFG, "Points", "PT-2011", "I/O Channel"),
           ev(F_CFG, "SIS Trips", "SIF-200-03", "Initiators"), ev(F_SRS, "SIF Requirements", "SIF-200-03", "Sensor Architecture")])
    # B2-21
    k.add("alarm source not independent of the SIF", "medium", ["TAH-2021", "TT-2021", "TT-2020A", "SIF-200-04"], [MADB, ALM, CFG, CUR, CE],
          "TAH-2021 is rationalised on the BPCS transmitter TT-2021 and the curated register approves it as an independent "
          "compensating measure for SIF-200-04 on that basis. In the DCS the alarm is configured on TT-2020A, one of the function's "
          "own initiators, so it is lost with the channel it is meant to back up.",
          [ev(F_MADB, "Alarms", "TAH-2021", "Source Tag"), ev(F_INDEX, "Alarm Register", "TAH-2021", "Source Tag"),
           ev(F_CFG, "Alarms", "TAH-2021", "Source Tag"), ev(F_CURATED, None, "SIF-200-04", "basis", alarm_id="TT-2021.TAH"),
           ev(F_CE, "CE-200", "SIF-200-04", "Cause Tag"), ev(F_SRS, "SIF Requirements", "SIF-200-04", "Bypass Conditions")])
    # B2-22
    k.add("removed alarm still configured", "low", ["TAL-2021", "TT-2021"], [MADB, ALM, CFG],
          "Rationalisation removed TAL-2021 (no operator action): the master alarm database records it as 'Removed' and the alarm "
          "register no longer lists it, but it is still configured and enabled in the DCS.",
          [ev(F_MADB, "Alarms", "TAL-2021", "Rationalisation Outcome"), ev(F_MADB, "Alarms", "TAL-2021", "Implementation Status"),
           ev(F_CFG, "Alarms", "TAL-2021", "Enabled")],
          [absent(F_INDEX, "Alarm Register", "TAL-2021")])
    # B2-23
    k.add("procedure coverage", "low", ["SIF-200-05", "U200-OP-PROC-020"], [REG, SRS, CE],
          "The document register shows the SIS bypass management procedure covering SIF-200-01 to SIF-200-04 only. SIF-200-05 is in "
          "the SRS and the cause & effect chart with its own bypass conditions, and has an override active (B2-06), but no bypass "
          "procedure covers it.",
          [ev(F_DOCREG, None, "U200-OP-PROC-020", "Covers"), ev(F_DOCREG, None, "U200-PTP-001", "Covers"),
           ev(F_SRS, "SIF Requirements", "SIF-200-05", "Bypass Conditions"), ev(F_CE, "CE-200", "SIF-200-05", "Cause Tag")])
    # B2-24
    k.add("stale out-of-service entry", "low", ["TT-2020C", "MOS-2020C", "SIF-200-04"], [OOSD, CFG],
          "The out-of-service register still shows a maintenance override on TT-2020C as active, more than ten days past its expiry, while "
          "the SIS export shows MOS-2020C off. The register no longer says what is actually out of service.",
          [ev(F_OOS, None, "OOS-200-0008", "element"), ev(F_OOS, None, "OOS-200-0008", "status"),
           ev(F_OOS, None, "OOS-200-0008", "expiry"), ev(F_CFG, "Overrides", "MOS-2020C", "Active")])

    controls = [
        {"description": "SIF-200-02 trip setpoint is written '350 mbarg' in the SRS and '0.35 barg' in the cause & effect chart and "
                        "the SIS export: the same value in different units.",
         "tags": ["SIF-200-02", "PT-2010A", "PT-2010B"]},
        {"description": "LT-2040 is ranged 0-3000 mm in the index and its DCS block is scaled 0-100 %; LAL-2040 (600 mm = 20 %) and "
                        "LAH-2040 (2400 mm = 80 %), with a 60 mm = 2 % deadband, are the same settings in both. Likewise PT-2025 is "
                        "'-25 to 25' mmWG in the index and -25 / 25 in the export.",
         "tags": ["LT-2040", "LAL-2040", "LAH-2040", "PT-2025"]},
        {"description": "Two bypasses are properly recorded. MOS-2001B on FT-2001B is active since 2026-11-12 02:10 and has a matching "
                        "active out-of-service entry (OOS-200-0010) inside the 8 h the SRS allows, with its compensating alarm FAL-2002 "
                        "enabled. The PT-2010A bypass of 2026-10-28 is closed in the register (OOS-200-0007), closed as MOC-2026-044, and "
                        "MOS-2010A is off.",
         "tags": ["FT-2001B", "MOS-2001B", "SIF-200-01", "PT-2010A", "MOS-2010A", "SIF-200-02"]},
        {"description": "LAH-2031 is listed in LOPA scenario S-200-05 with no PFD: deliberately not credited, because it shares LT-2031 "
                        "with the initiating control loop. The master alarm database agrees (IPL Credit 'No').",
         "tags": ["LAH-2031", "S-200-05"]},
        {"description": "MOC-2026-031 (re-range PT-2013 to 0-16 barg) is closed out properly: the index and the DCS point both show "
                        "0-16 barg and the one document to revise was revised.",
         "tags": ["PT-2013", "MOC-2026-031"]},
        {"description": "MOC-2026-043 (remove LAL-2031) was cancelled and MOC-2026-046 (TAH-2023 on-delay to 60 s) is still in review: "
                        "LAL-2031 is rightly still in every alarm list, and TAH-2023 rightly still has a 30 s on-delay everywhere.",
         "tags": ["LAL-2031", "MOC-2026-043", "TAH-2023", "MOC-2026-046"]},
        {"description": "FALL-2001 is configured in the SIS as a trip notification of SIF-200-01 and is in neither the master alarm "
                        "database nor the alarm register. That is correct: a trip is not an alarm.",
         "tags": ["FALL-2001", "FT-2001A", "SIF-200-01"]},
        {"description": "For SIF-200-01 to SIF-200-04 the SRS states the proof test interval in one cell ('Sensors 12 months, final "
                        "elements 24 months') where the SIL verification has two columns (12 months / 24 months); the SRS writes "
                        "architectures as '2oo3 FT' or '1oo2 (XV-2001 or XV-2002)' where other documents write '2oo3' or list the tags. "
                        "Same facts, different wording.",
         "tags": ["SIF-200-01", "SIF-200-02", "SIF-200-03", "SIF-200-04", "XV-2001", "XV-2002"]},
    ]
    return {
        "_note": "SEALED answer key for the U-200 blind test. DUMMY DATA - not a real facility. Generated by "
                 "scripts/make_dummy_batch2.py from the same tables as the documents. Evidence: 'row' is the value in the first "
                 "column of a data row of that sheet; where a sheet repeats a first-column value, the evidence holds if any such "
                 "row has 'value' under 'column'. 'sheet' is null for a CSV. Absent: no data row has 'row' in the first column, "
                 "or in the named 'column' when one is given (an extension of the agreed shape, needed for the out-of-service "
                 "register, whose first column is an entry id). Not to be read by whoever runs the checks.",
        "unit": UNIT,
        "items": k.items,
        "clean_controls": controls,
    }


# ======================================================================================================
# Writers
# ======================================================================================================

def _write_workbook(path: Path, tables: list[Table]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for table in tables:
        ws = wb.create_sheet(table.sheet)
        if table.style == "cover":
            for r in [table.header] + table.rows:
                ws.append(r)
            ws["A1"].font = Font(bold=True, size=14)
            ws["A3"].font = Font(bold=True, size=13)
            ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 16, 70
            continue
        for r in table.pre:
            ws.append(r)
        ws["A1"].font = Font(bold=True, size=13)
        ws.append(table.header)
        head = ws.max_row
        for c in ws[head]:
            if c.value is None:
                continue
            if table.style == "index":
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor=NAVY)
            else:
                c.font = Font(bold=True)
        for r in table.sub + table.rows:
            ws.append(r)
        if table.style in ("index", "ce"):
            ws.freeze_panes = f"A{head + len(table.sub) + 1}"
        for j, col in enumerate(ws.iter_cols(min_row=head), start=1):
            letter = col[0].column_letter
            if table.width:
                ws.column_dimensions[letter].width = table.width
            else:
                longest = max((len(str(c.value)) for c in col if c.value is not None), default=8)
                ws.column_dimensions[letter].width = max(12, min(longest + 2, 45))
    wb.properties.creator = "Bowden Simulators (dummy data)"
    wb.properties.created = STAMP
    wb.properties.modified = STAMP
    wb.save(path)
    _fix_timestamps(path)


def _fix_timestamps(path: Path) -> None:
    """openpyxl stamps 'modified' and every zip entry with the time of saving. Put the fixed stamp back, so two
    runs of this script write the same workbook."""
    iso = STAMP.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    with zipfile.ZipFile(path) as z:
        entries = [(info.filename, z.read(info.filename)) for info in z.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            if name == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)", rb"\g<1>" + iso + rb"\g<2>", data)
            info = zipfile.ZipInfo(name, date_time=STAMP.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


def _write_csv(path: Path, table: Table) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in table.pre + [table.header] + table.rows:
            w.writerow(["" if v is None else v for v in r])


def unit_json() -> dict:
    return {"unit": UNIT,
            "files": {"index": F_INDEX, "ce": F_CE, "srs": F_SRS, "lopa": F_LOPA, "curated": F_CURATED, "madb": F_MADB,
                      "config": F_CFG, "silv": F_SILV, "moc": F_MOC, "docreg": F_DOCREG, "topology": None, "pdf": None},
            "oos": F_OOS, "blind": F_BLIND}


def build(out: Path = OUT) -> list[Path]:
    """Write the whole U-200 set into `out`. Returns the files written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tables = build_tables()
    written = []
    files: dict[str, list[Table]] = {}
    for (file, _), table in tables.items():
        files.setdefault(file, []).append(table)
    for file, sheets in files.items():
        if file.endswith(".xlsx"):
            _write_workbook(out / file, sheets)
        else:
            _write_csv(out / file, sheets[0])
        written.append(out / file)
    for name, payload in ((F_UNIT, unit_json()), (F_KEY, build_key(tables))):
        (out / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
        written.append(out / name)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write the U-200 dummy document set (DUMMY DATA - not a real facility).")
    ap.add_argument("--out", type=Path, default=OUT)
    for p in build(ap.parse_args().out):
        print(p)
