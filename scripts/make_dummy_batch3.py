"""Batch 3 dummy documents: unit U-300, an export gas compressor, for a blind test of the checks.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Writes everything into data/u300/: instrument index (with loop and alarm registers), cause & effect
chart, SRS, LOPA, SIL verification, master alarm database, DCS / SIS configuration export, MOC
register, document register, compensating measures register, out-of-service register, a P&ID
topology extraction, unit.json and the sealed answer key U300-BATCH3-ANSWER-KEY.json.

ALL DATA IS SYNTHETIC. U-300 is not a real facility; no real project, vendor document or person
is represented.

How it is built: section 1 is one consistent design ("the truth"). Every document is generated from
it, so documents agree unless section 2 (PLANTED) says otherwise. Each planted discrepancy is one
explicit override, named by its answer-key id. The answer key is written last and reads its evidence
cells back from the files, so the cell references cannot drift from the content.

Deterministic: no randomness and no clock. Run:  .venv\\Scripts\\python scripts\\make_dummy_batch3.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "u300"
UNIT = "U-300"
DUMMY = "(DUMMY DATA - not a real facility)"
EXPORT_TIME = "2026-11-12 06:00"
LS, DCS = "SIS-LS-300", "DCS-300-C01"

F_INDEX = "U300-INST-INDEX-Rev-D.xlsx"
F_CE = "U300-CE-CHART-Rev-C.xlsx"
F_SRS = "U300-SRS-001-Rev-C.xlsx"
F_LOPA = "U300-LOPA-001-Rev-B.xlsx"
F_SILV = "U300-SILV-001-Rev-B.xlsx"
F_MADB = "U300-MADB-001-Rev-B.xlsx"
F_CFG = "U300-CFG-EXPORT-Rev-A.xlsx"
F_MOC = "U300-MOC-REG-Rev-A.xlsx"
F_DOCREG = "U300-DOC-REGISTER.csv"
F_CUR = "compensating_measures_U-300.csv"
F_OOS = "out_of_service_U-300.csv"
F_TOPO = "pid_audit_U300_topology.csv"
F_KEY = "U300-BATCH3-ANSWER-KEY.json"

# =====================================================================================
# 1. THE DESIGN (consistent)
# =====================================================================================

HART = "4-20 mA HART"
SOL = "24 VDC solenoid"
# tag, service, type, loop, P&ID, line / equipment, system, range, units, signal, remarks
INSTRUMENTS = [
    ("HV-3001", "Compressor suction manual isolation valve", "Manual ball valve", "", "PID-300-001", "L-301", "LOCAL", "", "", "", "Upstream of XV-3001"),
    ("XV-3001", "Compressor suction ESD valve", "ESD ball valve", "", "PID-300-001", "L-301", "SIS", "", "", SOL, "Fail close"),
    ("ZSC-3001", "XV-3001 closed limit switch", "Limit switch", "", "PID-300-001", "L-301", "SIS", "", "", "24 VDC DI", ""),
    ("LT-3002A", "Suction scrubber level (SIS) - A", "Level transmitter (GWR)", "", "PID-300-001", "V-301", "SIS", "0-2000", "mm", HART, "2oo3 with LT-3002B/C"),
    ("LT-3002B", "Suction scrubber level (SIS) - B", "Level transmitter (GWR)", "", "PID-300-001", "V-301", "SIS", "0-2000", "mm", HART, ""),
    ("LT-3002C", "Suction scrubber level (SIS) - C", "Level transmitter (GWR)", "", "PID-300-001", "V-301", "SIS", "0-2000", "mm", HART, ""),
    ("LT-3003", "Suction scrubber level control", "Level transmitter (DP)", "LIC-3003", "PID-300-001", "V-301", "BPCS", "0-2000", "mm", HART, ""),
    ("LV-3003", "Suction scrubber drain level valve", "Control valve", "LIC-3003", "PID-300-001", "L-306", "BPCS", "", "", "4-20 mA", "Fail close"),
    ("LG-3004", "Suction scrubber level gauge", "Magnetic level gauge", "", "PID-300-001", "V-301", "LOCAL", "0-2000", "mm", "", "Local indication"),
    ("LT-3005", "Suction scrubber level low-low (SIS)", "Level transmitter (GWR)", "", "PID-300-001", "V-301", "SIS", "0-2000", "mm", HART, "1oo1"),
    ("XV-3003", "Suction scrubber drain ESD valve", "ESD ball valve", "", "PID-300-001", "L-306", "SIS", "", "", SOL, "Fail close"),
    ("PV-3006", "Compressor suction pressure control valve", "Control valve", "PIC-3006", "PID-300-001", "L-302", "BPCS", "", "", "4-20 mA", "Fail open"),
    ("PT-3006", "Compressor suction pressure control", "Pressure transmitter", "PIC-3006", "PID-300-001", "L-302", "BPCS", "0-40", "barg", HART, ""),
    ("PT-3007A", "Compressor suction pressure (SIS) - A", "Pressure transmitter", "", "PID-300-001", "L-302", "SIS", "0-40", "barg", HART, "1oo2 with PT-3007B"),
    ("PT-3007B", "Compressor suction pressure (SIS) - B", "Pressure transmitter", "", "PID-300-001", "L-302", "SIS", "0-40", "barg", HART, ""),
    ("TT-3008", "Compressor suction temperature", "Temperature transmitter", "", "PID-300-001", "L-302", "BPCS", "0-100", "degC", HART, ""),
    ("FT-3009", "Compressor suction flow (anti-surge)", "Flow transmitter (DP)", "FIC-3010", "PID-300-001", "L-302", "BPCS", "0-20000", "m3/h", HART, ""),
    ("PT-3011", "Compressor discharge pressure (anti-surge)", "Pressure transmitter", "FIC-3010", "PID-300-002", "L-303", "BPCS", "0-120", "barg", HART, "Re-ranged from 0-100 barg under MOC-2026-050"),
    ("PT-3012A", "Compressor discharge pressure (SIS) - A", "Pressure transmitter", "", "PID-300-002", "L-303", "SIS", "0-120", "barg", HART, "2oo3 with PT-3012B/C"),
    ("PT-3012B", "Compressor discharge pressure (SIS) - B", "Pressure transmitter", "", "PID-300-002", "L-303", "SIS", "0-120", "barg", HART, ""),
    ("PT-3012C", "Compressor discharge pressure (SIS) - C", "Pressure transmitter", "", "PID-300-002", "L-303", "SIS", "0-120", "barg", HART, ""),
    ("TT-3014A", "Compressor discharge temperature (SIS) - A", "Temperature transmitter", "", "PID-300-002", "L-303", "SIS", "0-250", "degC", HART, "1oo2 with TT-3014B"),
    ("TT-3014B", "Compressor discharge temperature (SIS) - B", "Temperature transmitter", "", "PID-300-002", "L-303", "SIS", "0-250", "degC", HART, ""),
    ("TT-3015", "Compressor discharge temperature", "Temperature transmitter", "", "PID-300-002", "L-303", "BPCS", "0-250", "degC", HART, ""),
    ("PSV-3050", "Compressor discharge relief valve", "Relief valve", "", "PID-300-002", "L-303", "LOCAL", "", "", "", "Set pressure 90 barg; sized for blocked discharge"),
    ("TT-3016", "Aftercooler outlet temperature control", "Temperature transmitter", "TIC-3016", "PID-300-002", "E-301", "BPCS", "0-150", "degC", HART, "Acts on the E-301 fan speed"),
    ("PT-3013", "Export gas pressure (monitoring)", "Pressure transmitter", "", "PID-300-002", "L-304", "BPCS", "0-120", "barg", HART, "Separate tapping from PT-3011"),
    ("XV-3002", "Compressor discharge ESD valve", "ESD ball valve", "", "PID-300-002", "L-304", "SIS", "", "", SOL, "Fail close"),
    ("ZSC-3002", "XV-3002 closed limit switch", "Limit switch", "", "PID-300-002", "L-304", "SIS", "", "", "24 VDC DI", ""),
    ("FV-3010", "Anti-surge recycle valve", "Control valve", "FIC-3010", "PID-300-002", "L-305", "BPCS", "", "", "4-20 mA", "Fail open"),
    ("VT-3017A", "Compressor shaft vibration - drive end", "Proximity probe", "", "PID-300-002", "K-301", "BPCS", "0-125", "um", "4-20 mA", "Via the machine monitor"),
    ("VT-3017B", "Compressor shaft vibration - non-drive end", "Proximity probe", "", "PID-300-002", "K-301", "BPCS", "0-125", "um", "4-20 mA", "Via the machine monitor"),
    ("ST-3019", "Compressor speed", "Speed transmitter", "", "PID-300-002", "K-301", "BPCS", "0-15000", "rpm", "4-20 mA", ""),
    ("HS-3001", "Compressor emergency shutdown push-button", "Push-button", "", "PID-300-002", "K-301", "SIS", "", "", "24 VDC DI", "Control room panel"),
    ("XY-3040", "Compressor driver trip relay", "Trip relay", "", "PID-300-002", "K-301", "SIS", "", "", "24 VDC DO", "De-energise to trip"),
    ("LT-3024", "Lube oil reservoir level", "Level transmitter (DP)", "", "PID-300-003", "TK-301", "BPCS", "0-100", "%", HART, ""),
    ("PDT-3023", "Lube oil filter differential pressure", "Differential pressure transmitter", "", "PID-300-003", "L-308", "BPCS", "0-2.5", "bar", HART, ""),
    ("PCV-3028", "Lube oil header pressure regulator", "Self-acting regulator", "", "PID-300-003", "L-308", "LOCAL", "", "", "", ""),
    ("TT-3022", "Lube oil supply temperature", "Temperature transmitter", "", "PID-300-003", "L-308", "BPCS", "0-120", "degC", HART, ""),
    ("PT-3021", "Lube oil header pressure", "Pressure transmitter", "", "PID-300-003", "L-308", "BPCS", "0-6", "barg", HART, ""),
    ("PT-3020A", "Lube oil header pressure (SIS) - A", "Pressure transmitter", "", "PID-300-003", "L-308", "SIS", "0-6", "barg", HART, "2oo3 with PT-3020B/C"),
    ("PT-3020B", "Lube oil header pressure (SIS) - B", "Pressure transmitter", "", "PID-300-003", "L-308", "SIS", "0-6", "barg", HART, ""),
    ("PT-3020C", "Lube oil header pressure (SIS) - C", "Pressure transmitter", "", "PID-300-003", "L-308", "SIS", "0-6", "barg", HART, ""),
    ("PI-3027", "Lube oil header pressure gauge", "Pressure gauge", "", "PID-300-003", "L-308", "LOCAL", "0-6", "barg", "", "Local indication"),
    ("TT-3026", "Compressor thrust bearing temperature", "Temperature transmitter", "", "PID-300-003", "K-301", "BPCS", "0-150", "degC", HART, ""),
    ("PDT-3030", "Seal gas differential pressure", "Differential pressure transmitter", "", "PID-300-003", "L-309", "BPCS", "0-2", "bar", HART, ""),
    ("FT-3032", "Primary seal vent flow", "Flow transmitter (thermal)", "", "PID-300-003", "L-310", "BPCS", "0-20", "m3/h", HART, ""),
]

# loop, service, sensor, final element, protected equipment
LOOPS = [
    ("LIC-3003", "Suction scrubber level control", "LT-3003", "LV-3003", "V-301"),
    ("PIC-3006", "Compressor suction pressure control", "PT-3006", "PV-3006", "K-301"),
    ("FIC-3010", "Compressor anti-surge control (flow FT-3009, pressure PT-3011)", "FT-3009", "FV-3010", "K-301"),
    ("TIC-3016", "Aftercooler outlet temperature control (E-301 fan speed)", "TT-3016", "", "E-301"),
]

TEAM = "Alarm management engineer, operations rep, process engineer (dummy)"
# tag, source, description, type, setpoint, units, priority, class, cause, consequence, action, time to respond,
# deadband, on-delay, protected equipment, IPL credit, LOPA ref
ALARMS = [
    ("LAH-3003", "LT-3003", "Suction scrubber level high", "Absolute high", 1200, "mm", "High", "Safety", "LIC-3003 / LV-3003 fails closed; liquid slug from upstream", "Liquid carry-over to the compressor; SIF-300-01 demand", "Open the LV-3003 bypass; drain the scrubber", "10 min", "20 mm", "10 s", "V-301", "No", ""),
    ("LAL-3003", "LT-3003", "Suction scrubber level low", "Absolute low", 400, "mm", "Medium", "Safety", "LV-3003 stuck open", "Gas blow-by to the closed drain; SIF-300-02 demand", "Close LV-3003 in manual", "10 min", "20 mm", "10 s", "V-301", "No", ""),
    ("PAL-3006", "PT-3006", "Compressor suction pressure low", "Absolute low", 18, "barg", "High", "Safety", "PV-3006 closing; loss of feed gas", "Approach to the SIF-300-06 trip; surge", "Take PIC-3006 to manual and open PV-3006; check the feed", "10 min", "0.5 barg", "5 s", "K-301", "Yes", "S-300-06"),
    ("TAH-3008", "TT-3008", "Compressor suction temperature high", "Absolute high", 55, "degC", "Low", "Operational", "Hot recycle; upstream cooler fault", "Higher discharge temperature; loss of capacity", "Check E-301 and the recycle rate", "30 min", "2 degC", "30 s", "K-301", "No", ""),
    ("FAL-3009", "FT-3009", "Compressor suction flow low (approach to surge)", "Absolute low", 6000, "m3/h", "Medium", "Operational", "Low throughput; FV-3010 not opening", "Compressor surge", "Open FV-3010 in manual", "5 min", "200 m3/h", "2 s", "K-301", "No", ""),
    ("PAH-3011", "PT-3011", "Compressor discharge pressure high (anti-surge)", "Absolute high", 75, "barg", "Medium", "Operational", "Export restriction", "Approach to PAH-3013 and the SIF-300-03 trip", "Reduce load; check the export route", "10 min", "0.5 barg", "5 s", "E-301", "No", ""),
    ("PAH-3013", "PT-3013", "Export gas pressure high", "Absolute high", 76, "barg", "High", "Safety", "Blocked discharge; XV-3002 closing", "SIF-300-03 demand; overpressure of the discharge system", "Open FV-3010 in manual; reduce load", "10 min", "0.5 barg", "5 s", "E-301", "Yes", "S-300-03"),
    ("TAH-3015", "TT-3015", "Compressor discharge temperature high", "Absolute high", 160, "degC", "High", "Safety", "Hot recycle; E-301 fan failure", "Approach to the SIF-300-04 trip; seal damage", "Reduce load or trip the machine", "10 min", "2 degC", "10 s", "K-301", "Yes", "S-300-04"),
    ("TAH-3016", "TT-3016", "Aftercooler outlet temperature high", "Absolute high", 60, "degC", "Low", "Operational", "E-301 fan fault; high ambient temperature", "Hot export gas; hot recycle to suction", "Check the E-301 fans", "30 min", "2 degC", "10 s", "E-301", "No", ""),
    ("VAH-3017A", "VT-3017A", "Compressor shaft vibration high - drive end", "Absolute high", 60, "um", "Medium", "Operational", "Rotor imbalance; bearing wear; surge", "Bearing and seal damage", "Reduce speed; call the rotating equipment engineer", "10 min", "2 um", "3 s", "K-301", "No", ""),
    ("VAH-3017B", "VT-3017B", "Compressor shaft vibration high - non-drive end", "Absolute high", 60, "um", "Medium", "Operational", "Rotor imbalance; bearing wear; surge", "Bearing and seal damage", "Reduce speed; call the rotating equipment engineer", "10 min", "2 um", "3 s", "K-301", "No", ""),
    ("PAL-3021", "PT-3021", "Lube oil header pressure low", "Absolute low", 1.5, "barg", "High", "Safety", "Running lube oil pump tripped; filter blocked", "SIF-300-05 demand; bearing failure if the trip fails", "Start the standby lube oil pump from the panel", "5 min", "0.1 barg", "2 s", "K-301", "Yes", "S-300-05"),
    ("TAH-3022", "TT-3022", "Lube oil supply temperature high", "Absolute high", 60, "degC", "Medium", "Operational", "Lube oil cooler fouled", "Loss of oil film; bearing wear", "Change over the lube oil cooler", "15 min", "2 degC", "30 s", "K-301", "No", ""),
    ("PDAH-3023", "PDT-3023", "Lube oil filter differential pressure high", "Absolute high", 1, "bar", "Low", "Operational", "Filter element blocked", "Falling lube oil header pressure", "Change over the duplex filter", "60 min", "0.05 bar", "30 s", "K-301", "No", ""),
    ("LAL-3024", "LT-3024", "Lube oil reservoir level low", "Absolute low", 30, "%", "Medium", "Operational", "Oil leak; seal oil carry-over", "Loss of lube oil pump suction", "Check for leaks; top up the reservoir", "30 min", "2 %", "10 s", "TK-301", "No", ""),
    ("TAH-3026", "TT-3026", "Compressor thrust bearing temperature high", "Absolute high", 105, "degC", "High", "Operational", "Thrust overload; surge; loss of oil flow", "Thrust bearing failure", "Reduce load; check the lube oil supply", "10 min", "2 degC", "10 s", "K-301", "No", ""),
    ("PDAL-3030", "PDT-3030", "Seal gas differential pressure low", "Absolute low", 0.5, "bar", "High", "Operational", "Seal gas filter blocked; loss of seal gas supply", "Process gas contaminates the dry gas seal; seal failure", "Change over the seal gas filter; check the supply", "5 min", "0.05 bar", "5 s", "K-301", "No", ""),
    ("FAH-3032", "FT-3032", "Primary seal vent flow high", "Absolute high", 8, "m3/h", "High", "Operational", "Primary dry gas seal degrading", "Seal failure; gas release at the machine", "Prepare a controlled shutdown; call the rotating equipment engineer", "10 min", "0.5 m3/h", "10 s", "K-301", "No", ""),
]
ALARM = {a[0]: a for a in ALARMS}

# SIF: description, SIL, RRF, PFD target, sensors, voting, setpoint (value, units, direction), final elements with action,
# FE voting, protects, hazard, PST, response time, max bypass h, compensating alarm
SIFS = {
    "SIF-300-01": dict(desc="Suction scrubber high level - liquid carry-over protection", cause="Suction scrubber level high-high",
                       sil=2, rrf=100, pfd=0.01, sensors=["LT-3002A", "LT-3002B", "LT-3002C"], voting="2oo3", sp=(1500, "mm", "High"),
                       fe=[("XY-3040", "trip"), ("XV-3001", "close")], fe_voting="2oo2", protects="K-301",
                       function="On suction scrubber level high-high, trip K-301 through XY-3040 and close XV-3001",
                       hazard="Liquid carry-over into the compressor; machine damage and loss of containment",
                       safe="K-301 tripped, XV-3001 closed", pst="5 min", rt="20 s", max_h=8, alarm="LAH-3003", sensor_kind="LT"),
    "SIF-300-02": dict(desc="Suction scrubber low level - gas blow-by protection", cause="Suction scrubber level low-low",
                       sil=1, rrf=10, pfd=0.1, sensors=["LT-3005"], voting="1oo1", sp=(150, "mm", "Low"),
                       fe=[("XV-3003", "close")], fe_voting="1oo1", protects="V-301",
                       function="On suction scrubber level low-low, close XV-3003",
                       hazard="Gas blow-by through the drain; overpressure of the closed drain system",
                       safe="XV-3003 closed", pst="2 min", rt="20 s", max_h=2, alarm="LAL-3003", sensor_kind="LT"),
    "SIF-300-03": dict(desc="Compressor discharge high pressure - overpressure protection", cause="Compressor discharge pressure high-high",
                       sil=2, rrf=100, pfd=0.01, sensors=["PT-3012A", "PT-3012B", "PT-3012C"], voting="2oo3", sp=(82, "barg", "High"),
                       fe=[("XY-3040", "trip")], fe_voting="1oo1", protects="E-301",
                       function="On compressor discharge pressure high-high, trip K-301 through XY-3040",
                       hazard="Overpressure and rupture of the discharge system",
                       safe="K-301 tripped", pst="30 s", rt="5 s", max_h=8, alarm="PAH-3013", sensor_kind="PT"),
    "SIF-300-04": dict(desc="Compressor discharge high temperature - seal and casing protection", cause="Compressor discharge temperature high-high",
                       sil=1, rrf=30, pfd=0.033, sensors=["TT-3014A", "TT-3014B"], voting="1oo2", sp=(175, "degC", "High"),
                       fe=[("XY-3040", "trip")], fe_voting="1oo1", protects="K-301",
                       function="On compressor discharge temperature high-high, trip K-301 through XY-3040",
                       hazard="Discharge temperature above the seal and casing design temperature; seal failure and gas release",
                       safe="K-301 tripped", pst="5 min", rt="20 s", max_h=8, alarm="TAH-3015", sensor_kind="TT"),
    "SIF-300-05": dict(desc="Lube oil low pressure - bearing protection", cause="Lube oil header pressure low-low",
                       sil=1, rrf=20, pfd=0.05, sensors=["PT-3020A", "PT-3020B", "PT-3020C"], voting="2oo3", sp=(0.8, "barg", "Low"),
                       fe=[("XY-3040", "trip")], fe_voting="1oo1", protects="K-301",
                       function="On lube oil header pressure low-low, trip K-301 through XY-3040",
                       hazard="Bearing failure; rotor contact, seal failure and fire",
                       safe="K-301 tripped", pst="20 s", rt="3 s", max_h=8, alarm="PAL-3021", sensor_kind="PT"),
    "SIF-300-06": dict(desc="Compressor suction low pressure - machine protection", cause="Compressor suction pressure low-low",
                       sil=1, rrf=20, pfd=0.05, sensors=["PT-3007A", "PT-3007B"], voting="1oo2", sp=(15, "barg", "Low"),
                       fe=[("XY-3040", "trip"), ("XV-3002", "close")], fe_voting="2oo2", protects="K-301",
                       function="On compressor suction pressure low-low, trip K-301 through XY-3040 and close XV-3002 against reverse flow",
                       hazard="Surge and reverse flow at low suction pressure; machine damage and seal failure",
                       safe="K-301 tripped, XV-3002 closed", pst="60 s", rt="10 s", max_h=8, alarm="PAL-3006", sensor_kind="PT"),
}

# reliability data (dummy): lambda DU per hour, beta
LAMBDA = {"LT": (1e-6, 0.05), "PT": (5e-7, 0.05), "TT": (8e-7, 0.05), "XY": (2e-7, 0.0), "XV": (1.5e-6, 0.0)}
PFD_LS = 5e-5
TI = 8760  # hours; every proof test interval assumed in the calculation is 12 months

# LOPA: scenario, node, initiating event, IE frequency, consequence, severity, tolerable frequency, modifiers, SIF, RRF, SIL, notes
SCENARIOS = [
    ("S-300-01", "K-301", "LIC-3003 / LV-3003 fails closed; liquid accumulates in the suction scrubber", 0.1,
     "Liquid carry-over into the compressor; machine damage and loss of containment", "Cat 3", 1e-4,
     "Probability that carry-over leads to loss of containment 0.1", "SIF-300-01", 100, 2,
     "LAH-3003 shares LT-3003 with the initiating loop and is not credited"),
    ("S-300-02", "V-301", "LIC-3003 / LV-3003 fails open; the scrubber drains down", 0.1,
     "Gas blow-by through the drain; overpressure of the closed drain system", "Cat 2", 1e-3,
     "Probability that blow-by overpressures the closed drain drum 0.1", "SIF-300-02", 10, 1, ""),
    ("S-300-03", "E-301", "Blocked discharge (XV-3002 spurious closure or export route blocked)", 0.1,
     "Overpressure and rupture of the discharge system", "Cat 5", 1e-6, "None", "SIF-300-03", 100, 2,
     "PT-3013 has its own tapping and is independent of the anti-surge loop"),
    ("S-300-04", "K-301", "E-301 fan failure with the machine in recycle; hot gas returned to suction", 0.1,
     "Discharge temperature above the seal and casing design temperature; seal failure and gas release", "Cat 3", 1e-4,
     "Probability of ignition 0.3", "SIF-300-04", 30, 1, ""),
    ("S-300-05", "K-301", "Running lube oil pump P-301A trips and the standby P-301B fails to start", 0.2,
     "Bearing failure; rotor contact, seal failure and fire", "Cat 3", 1e-4,
     "Probability that bearing failure leads to seal failure and fire 0.1", "SIF-300-05", 20, 1, ""),
    ("S-300-06", "K-301", "PIC-3006 / PV-3006 fails closed", 0.1,
     "Surge and reverse flow at low suction pressure; machine damage and seal failure", "Cat 3", 1e-4,
     "Probability that surge leads to seal failure and release 0.2", "SIF-300-06", 20, 1, ""),
]
# scenario, type, tag, description, PFD (None = listed, not credited)
IPLS = [
    ("S-300-01", "Alarm + operator response", "LAH-3003", "High level alarm - shares LT-3003 with the initiating loop, not credited", None),
    ("S-300-01", "SIF", "SIF-300-01", "High-high level trip", 0.01),
    ("S-300-02", "SIF", "SIF-300-02", "Low-low level trip", 0.1),
    ("S-300-03", "Relief device", "PSV-3050", "Discharge relief valve, set 90 barg, sized for blocked discharge", 0.01),
    ("S-300-03", "Alarm + operator response", "PAH-3013", "High export pressure alarm on PT-3013, operator opens FV-3010 in manual; 15 min available between the alarm and the trip point", 0.1),
    ("S-300-03", "SIF", "SIF-300-03", "High-high discharge pressure trip", 0.01),
    ("S-300-04", "Alarm + operator response", "TAH-3015", "High discharge temperature alarm on TT-3015, operator reduces load or trips the machine; 10 min available between the alarm and the trip point", 0.1),
    ("S-300-04", "SIF", "SIF-300-04", "High-high discharge temperature trip", 0.033),
    ("S-300-05", "Alarm + operator response", "PAL-3021", "Low lube oil pressure alarm on PT-3021, operator starts the standby pump from the panel", 0.1),
    ("S-300-05", "SIF", "SIF-300-05", "Low-low lube oil pressure trip", 0.05),
    ("S-300-06", "SIF", "SIF-300-06", "Low-low suction pressure trip", 0.05),
]

# P&ID lines: line, sheet, from, instruments in flow order, to
LINES = [
    ("L-301", "PID-300-001", "BL-300", ["HV-3001", "XV-3001", "ZSC-3001"], "V-301"),
    ("L-302", "PID-300-001", "V-301", ["PV-3006", "PT-3006", "PT-3007A", "PT-3007B", "TT-3008", "FT-3009"], "K-301"),
    ("L-306", "PID-300-001", "V-301", ["LV-3003", "XV-3003"], "BL-320"),
    ("L-303", "PID-300-002", "K-301", ["PT-3011", "PT-3012A", "PT-3012B", "PT-3012C", "TT-3014A", "TT-3014B", "TT-3015"], "E-301"),
    ("L-304", "PID-300-002", "E-301", ["PT-3013", "XV-3002", "ZSC-3002"], "BL-310"),
    ("L-305", "PID-300-002", "E-301", ["FV-3010"], "V-301"),
    ("L-308", "PID-300-003", "TK-301", ["PDT-3023", "PCV-3028", "TT-3022", "PT-3021", "PT-3020A", "PT-3020B", "PT-3020C", "PI-3027"], "K-301"),
    ("L-309", "PID-300-003", "BL-330", ["PDT-3030"], "K-301"),
    ("L-310", "PID-300-003", "K-301", ["FT-3032"], "FLARE-HDR"),
]
# The topology CSV can only carry tags the loader classes as instruments, lines or equipment. Push-buttons, relief
# valves and relays (HS-, PSV-, XY-) would be read as equipment, so they are left out of the extraction.
NOT_IN_TOPOLOGY = ("HS-3001", "PSV-3050", "XY-3040")

MOCS = [
    ("MOC-2026-050", "Re-range PT-3011 compressor discharge pressure from 0-100 to 0-120 barg (anti-surge controller upgrade)", "Instrument re-range", "Closed",
     "2026-05-11", "2026-05-18", "2026-06-02", "2026-06-09", "PT-3011; PAH-3011", "U300-INST-INDEX", "U300-INST-INDEX", "Instrument Engineer (dummy)",
     "Index re-issued; DCS point re-scaled on 2026-06-02"),
    ("MOC-2026-051", "Temporary: bypass PT-3007B for transmitter replacement", "Temporary bypass", "Closed",
     "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-21", "PT-3007B; MOS-3007B; SIF-300-06", "", "", "Maintenance Planner (dummy)",
     "Bypass 08:00-14:10 on 2026-10-21 (6.2 h); see out-of-service entry OOS-300-0009"),
    ("MOC-2026-052", "Lower the SIF-300-04 discharge temperature trip from 175 to 165 degC (proposed after a seal inspection)", "Trip setting change", "Cancelled",
     "2026-08-03", "", "", "2026-08-24", "SIF-300-04; TT-3014A; TT-3014B", "U300-SRS-001; U300-CE-CHART; U300-PTP-001", "", "Rotating Equipment Engineer (dummy)",
     "Cancelled: the seal rating was confirmed adequate; the trip stays at 175 degC"),
    ("MOC-2026-053", "Lower the SIF-300-03 discharge pressure trip from 85 to 82 barg (discharge system re-rated after inspection)", "Trip setting change", "Closed",
     "2026-08-10", "2026-08-24", "2026-09-08", "2026-09-15", "SIF-300-03; PT-3012A; PT-3012B; PT-3012C", "U300-SRS-001; U300-CE-CHART; U300-PTP-001",
     "U300-SRS-001; U300-CE-CHART; U300-PTP-001", "Functional Safety Engineer (dummy)", "SRS and C&E re-issued at Rev C"),
    ("MOC-2026-054", "Add PT-3033 seal gas supply pressure transmitter upstream of PDT-3030", "New instrument", "Implemented - awaiting close-out",
     "2026-09-01", "2026-09-14", "2026-10-12", "", "PT-3033", "U300-INST-INDEX; PID-300-003", "PID-300-003", "Instrument Engineer (dummy)",
     "Installed and commissioned on 2026-10-12; indication only"),
    ("MOC-2026-055", "Extend the XV-3001 proof test interval (SIF-300-01) from 12 to 24 months to align with the compressor overhaul", "Proof test interval change", "Closed",
     "2026-07-06", "2026-07-20", "2026-08-03", "2026-08-10", "SIF-300-01; XV-3001", "U300-SRS-001; U300-SILV-001; U300-PTP-001", "U300-SRS-001; U300-PTP-001",
     "Maintenance Planner (dummy)", "Maintenance plan changed to 24 months on 2026-08-03"),
    ("MOC-2026-056", "Raise the LAH-3003 suction scrubber high level alarm from 1100 to 1200 mm (nuisance alarms during pigging)", "Alarm setting change", "Closed",
     "2026-08-17", "2026-08-31", "2026-09-07", "2026-09-14", "LAH-3003; LT-3003", "U300-MADB-001; U300-ALM-REG", "U300-MADB-001; U300-ALM-REG",
     "Alarm Management Engineer (dummy)", ""),
    ("MOC-2026-057", "Temporary: bypass TT-3014B for thermowell replacement", "Temporary bypass", "Closed",
     "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "TT-3014B; MOS-3014B; SIF-300-04", "", "", "Maintenance Planner (dummy)",
     "Bypass 08:00-15:20 on 2026-11-04 (7.3 h); see out-of-service entry OOS-300-0010"),
    ("MOC-2026-058", "Remove LAL-3003 suction scrubber low level alarm (rationalised as a duplicate of the SIF-300-02 pre-trip indication)", "Alarm removal", "Closed",
     "2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26", "LAL-3003; LT-3003", "U300-MADB-001; U300-ALM-REG", "U300-MADB-001",
     "Alarm Management Engineer (dummy)", "Alarm deleted from the DCS on 2026-10-19"),
    ("MOC-2026-059", "Temporary: disable VAH-3017B while the non-drive end proximity probe is replaced", "Temporary alarm disable", "Implemented - temporary, expires 2026-11-19",
     "2026-11-03", "2026-11-04", "2026-11-05", "", "VAH-3017B; VT-3017B", "", "", "Rotating Equipment Engineer (dummy)",
     "See out-of-service entry OOS-300-0016; VAH-3017A remains in service"),
    ("MOC-2026-060", "Increase the TAH-3016 on-delay from 10 s to 60 s (chattering on fan speed changes)", "Alarm setting change", "In review",
     "2026-11-05", "", "", "", "TAH-3016; TT-3016", "U300-MADB-001", "", "Alarm Management Engineer (dummy)", ""),
]

SUP, TECH, PLAN, PANEL = "Shift Supervisor (dummy)", "Instrument Technician (dummy)", "Maintenance Planner (dummy)", "Panel Operator (dummy)"
# id, element, kind, status, start, expiry, authorised by, requester, reason, compensating measures confirmed, notes
OOS = [
    ("OOS-300-0009", "PT-3007B", "mos", "closed", "2026-10-21 08:00", "2026-10-21 16:00", SUP, PLAN, "Transmitter replacement (MOC-2026-051)", "y", "Restored 14:10; MOS-3007B confirmed off"),
    ("OOS-300-0010", "TT-3014B", "mos", "closed", "2026-11-04 08:00", "2026-11-04 16:00", SUP, PLAN, "Thermowell replacement (MOC-2026-057)", "y", "Restored 15:20; MOS-3014B confirmed off"),
    ("OOS-300-0011", "PT-3013.PAH", "shelve", "active", "2026-11-10 10:00", "2026-11-17 10:00", SUP, PANEL, "PT-3013 impulse line leak; transmitter isolated, reading frozen", "n", "Awaiting impulse line repair"),
    ("OOS-300-0012", "PT-3012A", "mos", "active", "2026-11-11 23:00", "2026-11-12 07:00", SUP, TECH, "Transmitter drifting high - calibration", "y", "PAH-3013 confirmed active before the override was set"),
    ("OOS-300-0013", "LT-3002B", "mos", "active", "2026-11-12 01:30", "2026-11-12 09:30", SUP, TECH, "Probe cleaning", "y", "LAH-3003 confirmed active before the override was set"),
    ("OOS-300-0014", "PT-3020B", "mos", "active", "2026-11-12 00:30", "2026-11-12 08:30", SUP, TECH, "Impulse line flushing", "y", "PAL-3021 confirmed active before the override was set"),
    ("OOS-300-0015", "PT-3020C", "mos", "active", "2026-11-12 04:00", "2026-11-12 12:00", SUP, TECH, "Transmitter replacement", "y", "PAL-3021 confirmed active before the override was set"),
    ("OOS-300-0016", "VT-3017B.VAH", "shelve", "active", "2026-11-05 09:00", "2026-11-19 09:00", SUP, "Rotating Equipment Engineer (dummy)", "Proximity probe failed; alarm disabled in the DCS under MOC-2026-059", "n", "VAH-3017A in service; probe on order"),
]
# override switches active at the export time: switch -> active since (as the logic solver records it)
ACTIVE_MOS = {"MOS-3012A": "2026-11-11 23:00", "MOS-3002B": "2026-11-12 01:30", "MOS-3020B": "2026-11-12 00:30", "MOS-3020C": "2026-11-12 04:00"}

CUR_BY, CUR_DATE = "RK (dummy)", "2026-10-02"
# sif, alarm id, rank, basis, conditions, rationale
CURATED = [
    ("SIF-300-01", "LT-3003.LAH", 1, "independent_bpcs", "Valid while LT-3003 is in service and LAH-3003 is not shelved or suppressed.",
     "SIF-300-01 trips at 1500 mm on LT-3002A/B/C. LT-3003 is the BPCS DP transmitter on the same vessel, a separate transmitter on a separate system; LAH-3003 at 1200 mm annunciates before the trip point. Not credited in the LOPA only because the initiating loop uses LT-3003."),
    ("SIF-300-02", "LT-3003.LAL", 1, "independent_bpcs", "Valid while LT-3003 is in service and LAL-3003 is not shelved.",
     "SIF-300-02 trips at 150 mm on LT-3005. LAL-3003 at 400 mm is taken from the BPCS transmitter LT-3003 and annunciates before the trip point."),
    ("SIF-300-03", "PT-3013.PAH", 1, "independent_bpcs", "Valid while PT-3013 is in service and PAH-3013 is not shelved.",
     "SIF-300-03 trips at 82 barg on PT-3012A/B/C. PT-3013 is a BPCS transmitter with its own tapping downstream of E-301; PAH-3013 at 76 barg annunciates before the trip point."),
    ("SIF-300-04", "TT-3015.TAH", 1, "independent_bpcs", "Valid while TT-3015 is in service and TAH-3015 is not shelved.",
     "SIF-300-04 trips at 175 degC on TT-3014A/B. TAH-3015 at 160 degC is taken from the BPCS transmitter TT-3015 in its own thermowell."),
    ("SIF-300-05", "PT-3021.PAL", 1, "independent_bpcs", "Valid while PT-3021 is in service and PAL-3021 is not shelved.",
     "SIF-300-05 trips at 0.8 barg on PT-3020A/B/C. PT-3021 is the BPCS transmitter on the lube oil header; PAL-3021 at 1.5 barg annunciates before the trip point."),
    ("SIF-300-06", "PT-3006.PAL", 1, "independent_bpcs", "Valid while PT-3006 is in service and PAL-3006 is not shelved.",
     "SIF-300-06 trips at 15 barg on PT-3007A/B. PAL-3006 at 18 barg is taken from the BPCS transmitter PT-3006, independent of the SIS transmitters."),
]

# document register: number, title, type, rev, covers (None = filled in below)
ALL_SIFS = "; ".join(SIFS)
DOCREG = [
    ("U300-SRS-001", "Safety Requirements Specification - Unit 300", "SRS", "C", f"{ALL_SIFS}; {LS}"),
    ("U300-LOPA-001", "LOPA Report - Unit 300", "LOPA", "B", f"{ALL_SIFS}; V-301; K-301; E-301"),
    ("U300-SILV-001", "SIL Verification Calculations - Unit 300", "SIL verification", "B", ALL_SIFS),
    ("U300-CE-CHART", "Cause & Effect Chart - Unit 300", "C&E", "C", ALL_SIFS),
    ("U300-INST-INDEX", "Instrument Index - Unit 300", "Instrument index", "D", UNIT),
    ("U300-LOOP-REG", "Loop Register - Unit 300 (sheet of the instrument index workbook)", "Instrument index", "D", UNIT),
    ("U300-ALM-REG", "Alarm Register - Unit 300 (sheet of the instrument index workbook)", "Instrument index", "D", UNIT),
    ("U300-ALM-PHIL", "Alarm Philosophy and Rationalisation - Unit 300", "Alarm philosophy", "A", UNIT),
    ("U300-OP-PROC-010", "Operating Procedure - Export Gas Compressor Start-up and Shutdown", "Operating procedure", "C", "K-301; XV-3001; XV-3002; HV-3001; HS-3001; FV-3010"),
    ("U300-OP-PROC-020", "SIS Bypass Management Procedure", "SIS bypass procedure", "B", ALL_SIFS),
    ("U300-PTP-001", "SIS Proof Test Procedures - Unit 300", "Proof test procedure", "D", ALL_SIFS),
    ("U300-LOOP-3012", "Loop Drawings PT-3012A/B/C", "Loop drawing", "A", "PT-3012A; PT-3012B; PT-3012C"),
    ("U300-SIS-IO-001", "SIS I/O Allocation and Application Logic - SIS-LS-300", "SIS logic", "B", LS),
    ("U300-MADB-001", "Master Alarm Database - Unit 300", "MADB", "B", "; ".join(a[0] for a in ALARMS)),
    ("U300-CFG-EXPORT", "DCS / SIS Configuration Export - Unit 300", "Configuration export", "A", f"{DCS}; {LS}"),
    ("U300-MOC-REG", "Management of Change Register - Unit 300", "MOC register", "A", UNIT),
    ("U300-DOC-REGISTER", "Document Register - Unit 300", "Document register", "A", UNIT),
    ("PID-300-001", "P&ID - Suction Scrubber V-301 and Compressor Suction", "P&ID", "E", None),
    ("PID-300-002", "P&ID - Export Gas Compressor K-301, Aftercooler E-301 and Anti-surge Recycle", "P&ID", "D", None),
    ("PID-300-003", "P&ID - Lube Oil and Seal Gas Systems", "P&ID", "C", None),
]
PID_EQUIPMENT = {"PID-300-001": ["V-301"], "PID-300-002": ["K-301", "E-301"], "PID-300-003": ["TK-301"]}

# =====================================================================================
# 2. PLANTED discrepancies. Each entry is one deliberate departure from section 1, used by exactly one writer.
#    Ids are the answer-key ids. Nothing else in this file makes two documents disagree.
# =====================================================================================
PLANTED = {
    "B3-01": dict(cfg_voting={"SIF-300-06": "2oo2"}),
    "B3-02": dict(cfg_fe_dropped={"SIF-300-01": "XV-3001"}),
    "B3-03": dict(cfg_trip_setpoint={"SIF-300-03": 85}),
    "B3-04": dict(srs_pti={"SIF-300-01": "Sensors 12 months, XY-3040 12 months, XV-3001 24 months"}),
    "B3-05": dict(lopa_scenario={"S-300-02": dict(ie=1, rrf=100, sil=2, pfd=0.01,
                                                  note="Initiating event frequency raised from 0.1 to 1 /yr at the revalidation (site history of LV-3003 passing)")}),
    "B3-06": dict(lopa_extra_ipl=("S-300-06", "Alarm + operator response", "PAL-3006", "Low suction pressure alarm on PT-3006, operator takes PIC-3006 to manual and opens PV-3006", 0.1)),
    "B3-07": dict(cfg_alarm_limit={"PAL-3021": 0.7}),
    "B3-08": dict(cfg_mos_active={"MOS-3014B": "2026-11-04 08:00"}),
    "B3-09": "OOS-300-0011 and OOS-300-0012 as written in section 1 (the shelving and the confirmation contradict each other)",
    "B3-10": dict(cfg_dcs_sif="SIF-300-02", cfg_dcs_points=("LT-3005", "XV-3003")),
    "B3-11": "MOS-3020B and MOS-3020C both active (ACTIVE_MOS, OOS-300-0014 and -0015) against the SRS 'one channel at a time'",
    "B3-12": dict(madb_removed="LAL-3003", cfg_alarm_absent_removed="LAL-3003"),
    "B3-13": dict(cfg_range={"LT-3002C": (0, 1500)}),
    "B3-14": dict(silv_sensors={"SIF-300-04": ["TT-3014A", "TT-3015"]}),
    "B3-15": dict(cfg_mos_since={"MOS-3020C": "2026-11-10 16:00"}),
    "B3-16": dict(cfg_alarm_limit_kpa={"PDAL-3030": 5}),          # 0.5 bar is 50 kPa
    "B3-17": dict(extra_point=("PT-3033", "Seal gas supply pressure", 0, 100, "barg"), topology_extra=("L-309", "PT-3033")),
    "B3-18": dict(register_setpoint={"LAH-3003": 1100}),
    "B3-19": dict(cfg_alarm_absent="FAH-3032"),
    "B3-20": dict(madb_time_to_respond={"TAH-3015": "30 min"}),
    "B3-21": dict(silv_target={"SIF-300-05": ("U300-SRS-001 Rev B", 10)}),
    "B3-22": dict(cfg_on_delay={"TAH-3016": "60 s"}),
    "B3-23": dict(cfg_extra_alarm=("PAH-3006", "PT-3006", "DCS", "HI", 32, "barg", "Low", "0.5 barg", "5 s")),
    "B3-24": dict(topology_moved={"TT-3008": "L-301"}),
    "B3-25": dict(docreg_rev={"U300-CE-CHART": "B"}),
}

# =====================================================================================
# 3. Helpers
# =====================================================================================
BOLD = Font(bold=True)


def sig3(x: float) -> float:
    return float(f"{x:.3g}")


def sheet(wb: Workbook, name: str, title: str, docline: str, header: list, rows: list, extra_title_rows: tuple = ()):
    ws = wb.create_sheet(name)
    ws.append([title])
    ws.append([docline])
    for t in extra_title_rows:
        ws.append([t])
    ws.append(header)
    for c in ws[ws.max_row]:
        c.font = BOLD
    ws["A1"].font = BOLD
    for r in rows:
        ws.append(["" if v is None else v for v in r])
    for i, h in enumerate(header, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, min(48, len(str(h)) + 6))
    return ws


def docline(doc_no: str, rev: str, status: str) -> str:
    return f"Document No. {doc_no}    Rev {rev}    Status: {status}    {DUMMY}"


def save(wb: Workbook, name: str) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    wb.properties.created = wb.properties.modified = datetime(2026, 11, 12, 6, 0)
    wb.properties.creator = "make_dummy_batch3.py (dummy data)"
    wb.save(OUT / name)


def with_units(v, u) -> str:
    return f"{v} {u}"


def p1oo1(lam, ti):
    return lam * ti / 2


def p1oo2(lam, beta, ti):
    return (lam * ti) ** 2 / 3 + beta * lam * ti / 2


def p2oo3(lam, beta, ti):
    return (lam * ti) ** 2 + beta * lam * ti / 2


def pfd_sensors(kind: str, voting: str) -> float:
    lam, beta = LAMBDA[kind]
    return {"1oo1": p1oo1(lam, TI), "1oo2": p1oo2(lam, beta, TI), "2oo3": p2oo3(lam, beta, TI)}[voting]


def sil_band(pfd: float) -> int:
    return 3 if pfd < 1e-3 else 2 if pfd < 1e-2 else 1 if pfd < 1e-1 else 0


DEGRADED = {"2oo3": "1oo2", "1oo2": "1oo1", "1oo1": "None - function lost"}


def one_of(tags: list[str]) -> str:
    if len(tags) == 1:
        return tags[0]
    if len(tags) == 2:
        return f"{tags[0]} or {tags[1]}"
    stem = tags[0][:-1]
    return f"One of {stem}{'/'.join(t[-1] for t in tags)}"


# =====================================================================================
# 4. Writers
# =====================================================================================
def write_index() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cover"
    for r in (("UNIT 300 - EXPORT GAS COMPRESSOR", ""), ("INSTRUMENT INDEX", ""), ("Document No.", "U300-INST-INDEX"), ("Revision", "D"),
              ("Status", "As Built"), ("Sheets", "Instrument Index, Loop Register, Alarm Register"),
              ("Note", "DUMMY DATA generated for a blind test of the cross-document checks. Not a real facility.")):
        ws.append(r)
    sheet(wb, "Instrument Index", "INSTRUMENT INDEX - UNIT 300", docline("U300-INST-INDEX", "D", "As Built"),
          ["Tag No.", "Service Description", "Instrument Type", "Loop No.", "Area / Unit", "P&ID No.", "Line / Equipment No.", "System", "Range",
           "Units", "Signal", "Remarks"],
          [(t, s, ty, lp, UNIT, pid, loc, sysm, rng, un, sig, rem) for t, s, ty, lp, pid, loc, sysm, rng, un, sig, rem in INSTRUMENTS])
    sheet(wb, "Loop Register", "LOOP REGISTER - UNIT 300", docline("U300-LOOP-REG", "D", "As Built"),
          ["Loop No.", "Service Description", "Sensor", "Final Element", "Protected Equipment", "System"],
          [(*lp, "BPCS") for lp in LOOPS])
    stale = PLANTED["B3-18"]["register_setpoint"]
    sheet(wb, "Alarm Register", "ALARM REGISTER - UNIT 300", docline("U300-ALM-REG", "D", "As Built"),
          ["Alarm Tag", "Source Tag", "Setpoint", "Priority", "System", "Protected Equipment", "Alarm Description"],
          [(a[0], a[1], with_units(stale.get(a[0], a[4]), a[5]), a[6], "BPCS", a[14], a[2]) for a in ALARMS])
    save(wb, F_INDEX)


def write_ce() -> None:
    wb = Workbook()
    effects = ["XY-3040", "XV-3001", "XV-3002", "XV-3003"]
    actions = {"XY-3040": "Trip", "XV-3001": "Close", "XV-3002": "Close", "XV-3003": "Close"}
    rows = [["EFFECTS ->", "", "", "", "", "", "", "", "", ""] + [actions[e] for e in effects]]
    for sif, d in SIFS.items():
        marks = ["X" if e in [t for t, _ in d["fe"]] else "" for e in effects]
        for i, s in enumerate(d["sensors"]):
            head = [sif, d["desc"], d["sil"], LS] if i == 0 else ["", "", "", ""]
            rows.append(head + [s, d["cause"], d["voting"], with_units(d["sp"][0], d["sp"][1]), d["protects"] if i == 0 else "", ""] + marks)
    sheet(wb, "CE-300", "CAUSE & EFFECT CHART - UNIT 300 EXPORT GAS COMPRESSOR", docline("U300-CE-CHART", "C", "As Built"),
          ["SIF No.", "SIF Description", "SIL", "Logic Solver", "Cause Tag", "Cause Description", "Voting", "Setpoint", "Protected Equipment", ""] + effects,
          rows, extra_title_rows=("Legend: X = cause initiates effect. Voting per cause group. Effect action shown under each effect tag.",))
    save(wb, F_CE)


def fe_text(d: dict) -> str:
    tags = [t for t, _ in d["fe"]]
    return f"{d['fe_voting']} ({' and '.join(tags)})"


# setpoints the SRS states in another unit than the C&E; the same value (clean controls CC3-01 and CC3-02)
SRS_SETPOINT_TEXT = {"SIF-300-01": "1.5 m", "SIF-300-05": "80 kPag"}


def write_srs() -> None:
    wb = Workbook()
    pti = PLANTED["B3-04"]["srs_pti"]
    rows = []
    for sif, d in SIFS.items():
        if sif == "SIF-300-02":
            bypass = f"Not permitted unless {d['alarm']} is confirmed active and an operator is stationed at LG-3004; max {d['max_h']} h"
        else:
            bypass = f"One channel at a time, with {d['alarm']} confirmed active; max {d['max_h']} h"
        rows.append((sif, d["function"], d["hazard"], d["sil"], d["rrf"], d["pfd"], "Low demand", d["safe"], d["pst"], d["rt"],
                     SRS_SETPOINT_TEXT.get(sif, with_units(d["sp"][0], d["sp"][1])), f"{d['voting']} {d['sensor_kind']}", fe_text(d),
                     pti.get(sif, "12 months"), bypass, "HS-3001 on panel", "Manual, after the cause has cleared", LS, d["protects"]))
    sheet(wb, "SIF Requirements", "SAFETY REQUIREMENTS SPECIFICATION - UNIT 300 EXPORT GAS COMPRESSOR", docline("U300-SRS-001", "C", "As Built"),
          ["SIF No.", "Functional Description", "Hazard / Consequence", "SIL Target", "RRF Target", "PFDavg Target", "Demand Mode", "Safe State",
           "Process Safety Time", "SIF Response Time", "Trip Setpoint", "Sensor Architecture", "Final Element Architecture", "Proof Test Interval",
           "Bypass Conditions", "Manual Shutdown", "Reset", "Logic Solver", "Protected Equipment"], rows)
    save(wb, F_SRS)


def write_lopa() -> None:
    wb = Workbook()
    changed = PLANTED["B3-05"]["lopa_scenario"]
    rows = []
    for sc, node, ie, freq, cons, sev, tol, mod, sif, rrf, sil, note in SCENARIOS:
        c = changed.get(sc)
        if c:
            freq, rrf, sil, note = c["ie"], c["rrf"], c["sil"], c["note"]
        rows.append((sc, node, ie, freq, cons, sev, tol, mod, sif, rrf, sil, note))
    sheet(wb, "Scenarios", "LAYER OF PROTECTION ANALYSIS - UNIT 300 EXPORT GAS COMPRESSOR", docline("U300-LOPA-001", "B", "Revalidated"),
          ["Scenario No.", "Node / Equipment", "Initiating Event", "IE Frequency (/yr)", "Consequence", "Severity", "Tolerable Frequency (/yr)",
           "Conditional Modifiers", "Required SIF", "Required RRF", "Required SIL", "Notes"], rows)
    ipls = []
    extra = PLANTED["B3-06"]["lopa_extra_ipl"]
    for row in IPLS:
        sc, typ, tag, desc, pfd = row
        if sc == extra[0] and typ == "SIF":
            ipls.append(extra)
        if typ == "SIF" and sc in changed:
            pfd = changed[sc]["pfd"]
        ipls.append((sc, typ, tag, desc, pfd))
    sheet(wb, "IPLs", "LOPA - INDEPENDENT PROTECTION LAYERS CREDITED", docline("U300-LOPA-001", "B", "Revalidated"),
          ["Scenario No.", "IPL Type", "Tag", "Description", "PFD Credited"], ipls)
    save(wb, F_LOPA)


def silv_numbers(sif: str) -> dict:
    d = SIFS[sif]
    ps = pfd_sensors(d["sensor_kind"], d["voting"])
    fe_rows = [(t, LAMBDA[t[:2]][0], p1oo1(LAMBDA[t[:2]][0], TI)) for t, _ in d["fe"]]
    pfe = sum(p for _, _, p in fe_rows)
    total = ps + PFD_LS + pfe
    deg_voting = DEGRADED[d["voting"]]
    deg = None if deg_voting.startswith("None") else pfd_sensors(d["sensor_kind"], deg_voting) + PFD_LS + pfe
    return dict(ps=ps, pfe=pfe, fe_rows=fe_rows, total=total, deg_voting=deg_voting, deg=deg)


def write_silv() -> None:
    wb = Workbook()
    wrong_sensors = PLANTED["B3-14"]["silv_sensors"]
    stale_target = PLANTED["B3-21"]["silv_target"]
    summary, subs, degr = [], [], []
    for sif, d in SIFS.items():
        n = silv_numbers(sif)
        sensors = wrong_sensors.get(sif, d["sensors"])
        source, rrf_target = stale_target.get(sif, ("U300-SRS-001 Rev C", d["rrf"]))
        fe_tags = ", ".join(t for t, _ in d["fe"])
        summary.append((sif, d["sil"], source, rrf_target, ", ".join(sensors), d["voting"], LS, fe_tags, d["fe_voting"], sig3(n["ps"]), PFD_LS,
                        sig3(n["pfe"]), sig3(n["total"]), round(1 / n["total"]), sil_band(n["total"]), "12 months", "12 months", "Meets target"))
        lam, beta = LAMBDA[d["sensor_kind"]]
        subs.append((sif, "Sensors", ", ".join(sensors), d["voting"], lam, beta if len(sensors) > 1 else 0, TI, sig3(n["ps"]), "Generic data (dummy)"))
        for t, lam_fe, p in n["fe_rows"]:
            subs.append((sif, "Final element", t, "1oo1", lam_fe, 0, TI, sig3(p), "Generic data (dummy)"))
        subs.append((sif, "Logic solver", LS, "1oo1D", "", "", "", PFD_LS, "Certificate data (dummy)"))
        mb = f"{d['max_h']} h"
        if n["deg"] is None:
            degr.append((sif, one_of(sensors), d["voting"], n["deg_voting"], "", "", mb,
                         "No protection while bypassed. Compensating measures per the SRS bypass conditions."))
        else:
            degr.append((sif, one_of(sensors), d["voting"], n["deg_voting"], sig3(n["deg"]), sil_band(n["deg"]), mb,
                         "Degraded voting assumed in the logic solver while one channel is overridden"))
        degr.append((sif, " or ".join(t for t, _ in d["fe"]), d["fe_voting"], "None - function lost", "", "", mb,
                     "No protection while bypassed. Compensating measures per the SRS bypass conditions."))
    dl = docline("U300-SILV-001", "B", "As Built")
    sheet(wb, "SIF Summary", "SIL VERIFICATION - UNIT 300 EXPORT GAS COMPRESSOR", dl,
          ["SIF No.", "SIL Target", "Target Source", "RRF Target", "Sensor Tags", "Sensor Voting", "Logic Solver", "Final Element Tags",
           "Final Element Voting", "PFD Sensors", "PFD Logic Solver", "PFD Final Elements", "PFDavg", "RRF Achieved", "SIL Achieved",
           "Proof Test Interval - Sensors", "Proof Test Interval - Final Elements", "Result"], summary)
    sheet(wb, "Subsystems", "SIL VERIFICATION - SUBSYSTEM DATA", dl,
          ["SIF No.", "Subsystem", "Tags", "Voting", "Lambda DU (/h)", "Beta", "Proof Test Interval (h)", "PFDavg", "Data Source"], subs)
    sheet(wb, "Degraded Operation", "SIL VERIFICATION - ONE ELEMENT BYPASSED", dl,
          ["SIF No.", "Element Bypassed", "Normal Voting", "Degraded Voting Assumed", "PFDavg Degraded", "SIL Degraded", "SRS Max Bypass", "Note"], degr)
    save(wb, F_SILV)


def write_madb() -> None:
    wb = Workbook()
    removed = PLANTED["B3-12"]["madb_removed"]
    ttr = PLANTED["B3-20"]["madb_time_to_respond"]
    dates = {"LAH-3003": "2026-08-27", removed: "2026-10-08"}
    rows = []
    for tag, src, desc, typ, sp, un, pri, cls, cause, cons, action, t, db, ond, _prot, ipl, ref in ALARMS:
        outcome, status = ("Remove - duplicates the SIF-300-02 pre-trip indication", "Removed") if tag == removed else ("Keep", "Implemented")
        rows.append((tag, src, desc, typ, sp, un, pri, cls, cause, cons, action, ttr.get(tag, t), db, ond, "0 s", ipl, ref, outcome, status,
                     dates.get(tag, "2026-05-14"), TEAM))
    sheet(wb, "Alarms", "MASTER ALARM DATABASE - UNIT 300", docline("U300-MADB-001", "B", "Rationalised"),
          ["Alarm Tag", "Source Tag", "Description", "Alarm Type", "Setpoint", "Units", "Priority", "Alarm Class", "Cause", "Consequence of No Action",
           "Operator Action", "Time to Respond", "Deadband", "On-delay", "Off-delay", "IPL Credit", "LOPA Ref", "Rationalisation Outcome",
           "Implementation Status", "Rationalised", "Team"], rows)
    save(wb, F_MADB)


BLOCK = {"XV": "DO", "XY": "DO", "ZSC": "DI", "HS": "DI", "LV": "AO", "PV": "AO", "FV": "AO"}
KPA_POINTS = ("PDT-3023", "PDT-3030")      # configured in kPa; the index gives bar (1 bar = 100 kPa)


def mos_for(sensor: str) -> str:
    return "MOS-" + sensor.split("-", 1)[1]


def write_cfg() -> None:
    wb = Workbook()
    dl = docline("U300-CFG-EXPORT", "A", f"Configuration export {EXPORT_TIME} from DCS-300 and {LS}")
    dcs_points = PLANTED["B3-10"]["cfg_dcs_points"]
    ranges = PLANTED["B3-13"]["cfg_range"]
    counters: dict[str, int] = {}

    def channel(sysm: str, block: str) -> str:
        k = f"{sysm}-{block}"
        counters[k] = counters.get(k, 0) + 1
        n = counters[k] - 1
        return f"{k}-{n // 8 + 1:02d}/{n % 8 + 1:02d}"

    points = []
    for tag, service, _ty, loop, _pid, _loc, sysm, rng, un, _sig, _rem in INSTRUMENTS:
        if sysm == "LOCAL":
            continue
        s = "DCS" if (sysm == "BPCS" or tag in dcs_points) else "SIS"
        block = BLOCK.get(tag.split("-")[0], "AI")
        lo, hi = "", ""
        if rng:
            lo, hi = (float(x) for x in rng.split("-"))
            if tag in KPA_POINTS:
                lo, hi, un = lo * 100, hi * 100, "kPa"
            lo, hi = ranges.get(tag, (lo, hi))
        points.append((tag, s, DCS if s == "DCS" else LS, block, channel(s, block), lo, hi, un if rng else "", service, loop))
    t, service, lo, hi, un = PLANTED["B3-17"]["extra_point"]
    points.append((t, "DCS", DCS, "AI", channel("DCS", "AI"), lo, hi, un, service, ""))
    for lp, service, *_ in LOOPS:
        points.append((lp, "DCS", DCS, "PID", "", "", "", "", service, lp))
    sheet(wb, "Points", "DCS / SIS CONFIGURATION EXPORT - UNIT 300 - POINTS", dl,
          ["Point Tag", "System", "Controller", "Block Type", "I/O Channel", "Range Low", "Range High", "Units", "Description", "Loop"], points)

    absent = {PLANTED["B3-12"]["cfg_alarm_absent_removed"], PLANTED["B3-19"]["cfg_alarm_absent"]}
    limits = PLANTED["B3-07"]["cfg_alarm_limit"]
    kpa_wrong = PLANTED["B3-16"]["cfg_alarm_limit_kpa"]
    delays = PLANTED["B3-22"]["cfg_on_delay"]
    disabled = {"VAH-3017B"}                    # temporary, under MOC-2026-059 and OOS-300-0016 (clean control)
    alarms = []
    for tag, src, _d, typ, sp, un, pri, _c, _ca, _co, _ac, _t, db, ond, *_ in ALARMS:
        if tag in absent:
            continue
        if src in KPA_POINTS:
            sp, un, db = sp * 100, "kPa", f"{float(db.split()[0]) * 100:g} kPa"
            sp = kpa_wrong.get(tag, sp)
        sp = limits.get(tag, sp)
        alarms.append((tag, src, "DCS", "HI" if "high" in typ else "LO", sp, un, pri, db, delays.get(tag, ond), "No" if tag in disabled else "Yes"))
        if tag == "PAL-3006":
            alarms.append((*PLANTED["B3-23"]["cfg_extra_alarm"], "Yes"))
    sheet(wb, "Alarms", "DCS / SIS CONFIGURATION EXPORT - UNIT 300 - ALARMS", dl,
          ["Alarm Tag", "Source Tag", "System", "Alarm Type", "Limit", "Units", "Priority", "Deadband", "On-delay", "Enabled"], alarms)

    votes, dropped, sps = PLANTED["B3-01"]["cfg_voting"], PLANTED["B3-02"]["cfg_fe_dropped"], PLANTED["B3-03"]["cfg_trip_setpoint"]
    trips = []
    for sif, d in SIFS.items():
        fe = [(tg, a) for tg, a in d["fe"] if tg != dropped.get(sif)]
        trips.append((sif, DCS if sif == PLANTED["B3-10"]["cfg_dcs_sif"] else LS, ", ".join(d["sensors"]), votes.get(sif, d["voting"]),
                      sps.get(sif, d["sp"][0]), d["sp"][1], d["sp"][2], ", ".join(tg for tg, _ in fe), ", ".join(f"{tg} {a}" for tg, a in fe), "Yes"))
    sheet(wb, "SIS Trips", "DCS / SIS CONFIGURATION EXPORT - UNIT 300 - SIS TRIPS", dl,
          ["SIF No.", "Logic Solver", "Initiators", "Voting", "Trip Setpoint", "Units", "Direction", "Final Elements", "Action", "Trip Enabled"], trips)

    active = dict(ACTIVE_MOS)
    active.update(PLANTED["B3-08"]["cfg_mos_active"])
    active.update(PLANTED["B3-15"]["cfg_mos_since"])
    overrides = []
    for sif, d in SIFS.items():
        for s in d["sensors"]:
            m = mos_for(s)
            overrides.append((m, sif, s, DEGRADED[d["voting"]], d["max_h"], "Alarm only", "Medium", "Yes" if m in active else "No", active.get(m, "")))
    sheet(wb, "Overrides", "DCS / SIS CONFIGURATION EXPORT - UNIT 300 - MAINTENANCE OVERRIDES", dl,
          ["Override Tag", "SIF No.", "Element", "Degraded Voting", "Max Duration (h)", "Timeout Action", "Override Alarm Priority", "Active",
           "Active Since"], overrides)
    save(wb, F_CFG)


def write_moc() -> None:
    wb = Workbook()
    sheet(wb, "Register", "MANAGEMENT OF CHANGE REGISTER - UNIT 300", docline("U300-MOC-REG", "A", "Live register"),
          ["MOC No.", "Title", "Change Type", "Status", "Raised", "Approved", "Implemented", "Closed", "Tags Affected", "Documents to Revise",
           "Documents Revised", "Originator", "Notes"], MOCS)
    save(wb, F_MOC)


def write_csv(name: str, rows: list, title_rows: tuple = ()) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        for t in title_rows:
            f.write(t + "\n")
        csv.writer(f, lineterminator="\n").writerows(rows)


def write_docreg() -> None:
    revs = PLANTED["B3-25"]["docreg_rev"]
    extra_tag = PLANTED["B3-17"]["extra_point"][0]
    rows = [["Document No.", "Title", "Type", "Rev", "Covers"]]
    for no, title, typ, rev, covers in DOCREG:
        if covers is None:
            tags = [i[0] for i in INSTRUMENTS if i[4] == no]
            if no == "PID-300-003":
                tags.append(extra_tag)           # MOC-2026-054 says the drawing was revised
            covers = "; ".join(PID_EQUIPMENT[no] + tags)
        rows.append([no, title, typ, revs.get(no, rev), covers])
    write_csv(F_DOCREG, rows, title_rows=("DOCUMENT REGISTER - UNIT 300", f"Document No. U300-DOC-REGISTER    Rev A    Status: Current    {DUMMY}", ""))


def write_curated() -> None:
    rows = [["sif_id", "alarm_id", "rank", "basis", "conditions", "rationale", "status", "curated_by", "date"]]
    rows += [[s, a, r, b, c, why, "approved", CUR_BY, CUR_DATE] for s, a, r, b, c, why in CURATED]
    write_csv(F_CUR, rows)


def write_oos() -> None:
    rows = [["id", "element", "kind", "status", "start", "expiry", "authorised_by", "requester", "reason", "compensating_measures_confirmed", "notes"]]
    write_csv(F_OOS, rows + [list(r) for r in OOS])


def write_topology() -> None:
    moved = PLANTED["B3-24"]["topology_moved"]
    extra_line, extra_tag = PLANTED["B3-17"]["topology_extra"]
    by_tag = {i[0]: i for i in INSTRUMENTS}
    rows = [["sheet", "from", "to", "line_no", "confidence", "verified"]]
    conf = (0.95, 0.93, 0.92, 0.91, 0.9)
    n = 0
    placed = set()
    for line, pid, src, tags, dst in LINES:
        tags = [t for t in tags if moved.get(t, line) == line] + [t for t, ln in moved.items() if ln == line]
        if line == extra_line:
            tags = [extra_tag] + tags
        chain = [src] + tags + [dst]
        for a, b in zip(chain, chain[1:]):
            rows.append([pid, a, b, line, conf[n % len(conf)], "yes" if n % 6 == 0 else ""])
            n += 1
        placed |= set(tags)
    for tag, *_rest in INSTRUMENTS:
        i = by_tag[tag]
        if tag in placed or tag in NOT_IN_TOPOLOGY:
            continue
        assert not i[5].startswith("L-"), f"{tag} is on line {i[5]} but not in LINES"
        rows.append([i[4], i[5], tag, "", (0.88, 0.87, 0.89)[n % 3], ""])
        n += 1
    write_csv(F_TOPO, rows)


def write_unit_json() -> None:
    cfg = {"unit": UNIT,
           "files": {"index": F_INDEX, "ce": F_CE, "srs": F_SRS, "lopa": F_LOPA, "curated": F_CUR, "madb": F_MADB, "config": F_CFG,
                     "silv": F_SILV, "moc": F_MOC, "docreg": F_DOCREG, "topology": F_TOPO, "pdf": None},
           "oos": F_OOS, "blind": "U300-BLIND-ADJUDICATION.json"}
    (OUT / "unit.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


# =====================================================================================
# 5. Answer key (sealed). Evidence cells are read back from the files just written.
# =====================================================================================
class Evidence:
    def __init__(self) -> None:
        self._wb: dict[str, object] = {}
        self._csv: dict[str, list] = {}

    def x(self, file: str, sheet_name: str, col: str, **match) -> str:
        """file:sheet:cell = value for the row whose cells equal `match` (header -> value)."""
        wb = self._wb.setdefault(file, load_workbook(OUT / file))
        ws = wb[sheet_name]
        hrow = next(r for r in range(1, 8) if sum(c.value not in (None, "") for c in ws[r]) >= 3)
        cols = {str(c.value): c.column for c in ws[hrow] if c.value not in (None, "")}
        for r in range(hrow + 1, ws.max_row + 1):
            if all(str(ws.cell(r, cols[k]).value) == str(v) for k, v in match.items()):
                cell = ws.cell(r, cols[col])
                return f"{file}:{sheet_name}:{cell.coordinate} = {cell.value if cell.value is not None else '(blank)'}"
        raise KeyError(f"{file}:{sheet_name}: no row {match}")

    def absent(self, file: str, sheet_name: str, col: str, value: str) -> str:
        wb = self._wb.setdefault(file, load_workbook(OUT / file))
        ws = wb[sheet_name]
        assert all(value != str(c.value) for row in ws.iter_rows() for c in row), f"{value} is in {file}:{sheet_name}"
        return f"{file}:{sheet_name}: no row with {col} = {value}"

    def c(self, file: str, col: str, **match) -> str:
        if file not in self._csv:
            with (OUT / file).open(newline="", encoding="utf-8") as f:
                self._csv[file] = list(csv.reader(f))
        rows = self._csv[file]
        h = next(i for i, r in enumerate(rows) if len(r) >= 4)
        head = rows[h]
        for i, r in enumerate(rows[h + 1:], start=h + 2):
            if len(r) == len(head) and all(r[head.index(k)] == str(v) for k, v in match.items()):
                return f"{file}:row {i}:{col} = {r[head.index(col)] or '(blank)'}"
        raise KeyError(f"{file}: no row {match}")


def answer_key() -> dict:
    e = Evidence()
    x, c = e.x, e.c
    n1 = silv_numbers("SIF-300-01")
    xv = p1oo1(LAMBDA["XV"][0], 2 * TI)
    rrf2 = round(1 / silv_numbers("SIF-300-02")["total"])
    total_24 = n1["total"] - p1oo1(LAMBDA["XV"][0], TI) + xv
    items = [
        dict(id="B3-01", severity="high", kind="voting as configured",
             finding="SIF-300-06 is 1oo2 on PT-3007A/B in the C&E, the SRS and the SIL verification, but the logic solver is configured 2oo2, so one failed transmitter defeats the trip.",
             documents=["U300-CE-CHART", "U300-SRS-001", "U300-SILV-001", "U300-CFG-EXPORT"], tags=["SIF-300-06", "PT-3007A", "PT-3007B"],
             evidence=[x(F_CE, "CE-300", "Voting", **{"Cause Tag": "PT-3007A"}), x(F_SRS, "SIF Requirements", "Sensor Architecture", **{"SIF No.": "SIF-300-06"}),
                       x(F_SILV, "SIF Summary", "Sensor Voting", **{"SIF No.": "SIF-300-06"}), x(F_CFG, "SIS Trips", "Voting", **{"SIF No.": "SIF-300-06"})]),
        dict(id="B3-02", severity="high", kind="final element missing from the configured trip",
             finding="SIF-300-01 must trip K-301 through XY-3040 and close XV-3001 (C&E, SRS, SIL verification), but the configured trip drives XY-3040 only; XV-3001 is not closed.",
             documents=["U300-CE-CHART", "U300-SRS-001", "U300-SILV-001", "U300-CFG-EXPORT"], tags=["SIF-300-01", "XV-3001", "XY-3040"],
             evidence=[f"{F_CE}:CE-300:L6 = X (XV-3001 column, row of LT-3002A)", x(F_SRS, "SIF Requirements", "Final Element Architecture", **{"SIF No.": "SIF-300-01"}),
                       x(F_SILV, "SIF Summary", "Final Element Tags", **{"SIF No.": "SIF-300-01"}), x(F_CFG, "SIS Trips", "Final Elements", **{"SIF No.": "SIF-300-01"})]),
        dict(id="B3-03", severity="high", kind="change closed on paper, not made in the plant",
             finding="MOC-2026-053 (closed) lowered the SIF-300-03 trip from 85 to 82 barg and the SRS and C&E say 82 barg, but the logic solver still trips at 85 barg.",
             documents=["U300-MOC-REG", "U300-SRS-001", "U300-CE-CHART", "U300-CFG-EXPORT"], tags=["SIF-300-03", "PT-3012A", "PT-3012B", "PT-3012C", "MOC-2026-053"],
             evidence=[x(F_MOC, "Register", "Status", **{"MOC No.": "MOC-2026-053"}), x(F_MOC, "Register", "Title", **{"MOC No.": "MOC-2026-053"}),
                       x(F_SRS, "SIF Requirements", "Trip Setpoint", **{"SIF No.": "SIF-300-03"}), x(F_CE, "CE-300", "Setpoint", **{"Cause Tag": "PT-3012A"}),
                       x(F_CFG, "SIS Trips", "Trip Setpoint", **{"SIF No.": "SIF-300-03"})]),
        dict(id="B3-04", severity="high", kind="calculation rests on a superseded proof test interval",
             finding=f"MOC-2026-055 (closed) extended the XV-3001 proof test interval to 24 months and the SRS says so, but the SIL verification still assumes 12 months and was not revised; at 24 months SIF-300-01 achieves about RRF {round(1 / total_24)} against a target of 100.",
             documents=["U300-MOC-REG", "U300-SRS-001", "U300-SILV-001"], tags=["SIF-300-01", "XV-3001", "MOC-2026-055"],
             evidence=[x(F_SRS, "SIF Requirements", "Proof Test Interval", **{"SIF No.": "SIF-300-01"}),
                       x(F_SILV, "SIF Summary", "Proof Test Interval - Final Elements", **{"SIF No.": "SIF-300-01"}),
                       x(F_SILV, "Subsystems", "Proof Test Interval (h)", **{"SIF No.": "SIF-300-01", "Tags": "XV-3001"}),
                       x(F_SILV, "SIF Summary", "RRF Achieved", **{"SIF No.": "SIF-300-01"}), x(F_SILV, "SIF Summary", "RRF Target", **{"SIF No.": "SIF-300-01"}),
                       x(F_MOC, "Register", "Documents to Revise", **{"MOC No.": "MOC-2026-055"}), x(F_MOC, "Register", "Documents Revised", **{"MOC No.": "MOC-2026-055"}),
                       x(F_MOC, "Register", "Status", **{"MOC No.": "MOC-2026-055"})]),
        dict(id="B3-05", severity="high", kind="LOPA requirement not carried into the SRS",
             finding=f"The revalidated LOPA requires SIL 2 / RRF 100 of SIF-300-02 (scenario S-300-02), but the SRS and the C&E still specify SIL 1 (RRF 10) and the SIL verification achieves only RRF {rrf2}.",
             documents=["U300-LOPA-001", "U300-SRS-001", "U300-CE-CHART", "U300-SILV-001"], tags=["SIF-300-02", "S-300-02"],
             evidence=[x(F_LOPA, "Scenarios", "Required SIL", **{"Scenario No.": "S-300-02"}), x(F_LOPA, "Scenarios", "Required RRF", **{"Scenario No.": "S-300-02"}),
                       x(F_LOPA, "IPLs", "PFD Credited", **{"Tag": "SIF-300-02"}), x(F_SRS, "SIF Requirements", "SIL Target", **{"SIF No.": "SIF-300-02"}),
                       x(F_SRS, "SIF Requirements", "RRF Target", **{"SIF No.": "SIF-300-02"}), x(F_CE, "CE-300", "SIL", **{"Cause Tag": "LT-3005"}),
                       x(F_SILV, "SIF Summary", "RRF Achieved", **{"SIF No.": "SIF-300-02"}), x(F_SILV, "SIF Summary", "SIL Target", **{"SIF No.": "SIF-300-02"})]),
        dict(id="B3-06", severity="high", kind="credited alarm not independent of the initiating event",
             finding="LOPA scenario S-300-06 credits PAL-3006 (PFD 0.1), but PAL-3006 is generated from PT-3006, the transmitter of the PIC-3006 loop whose failure is the initiating event; without the credit SIF-300-06 would need RRF 200, not 20.",
             documents=["U300-LOPA-001", "U300-LOOP-REG", "U300-ALM-REG", "U300-MADB-001"], tags=["S-300-06", "PAL-3006", "PT-3006", "PIC-3006", "SIF-300-06"],
             evidence=[x(F_LOPA, "IPLs", "PFD Credited", **{"Scenario No.": "S-300-06", "Tag": "PAL-3006"}), x(F_LOPA, "Scenarios", "Initiating Event", **{"Scenario No.": "S-300-06"}),
                       x(F_LOPA, "Scenarios", "Required RRF", **{"Scenario No.": "S-300-06"}), x(F_INDEX, "Loop Register", "Sensor", **{"Loop No.": "PIC-3006"}),
                       x(F_INDEX, "Alarm Register", "Source Tag", **{"Alarm Tag": "PAL-3006"}), x(F_MADB, "Alarms", "Source Tag", **{"Alarm Tag": "PAL-3006"})]),
        dict(id="B3-07", severity="high", kind="alarm relied on as protection is set beyond the trip point",
             finding="PAL-3021 (credited IPL in S-300-05, compensating measure and SRS bypass condition for SIF-300-05) is rationalised at 1.5 barg but configured at 0.7 barg, below the 0.8 barg trip, so it cannot annunciate before the trip.",
             documents=["U300-MADB-001", "U300-ALM-REG", "U300-CFG-EXPORT", "U300-LOPA-001", "U300-CE-CHART"], tags=["PAL-3021", "PT-3021", "SIF-300-05", "S-300-05"],
             evidence=[x(F_MADB, "Alarms", "Setpoint", **{"Alarm Tag": "PAL-3021"}), x(F_INDEX, "Alarm Register", "Setpoint", **{"Alarm Tag": "PAL-3021"}),
                       x(F_CFG, "Alarms", "Limit", **{"Alarm Tag": "PAL-3021"}), x(F_CFG, "SIS Trips", "Trip Setpoint", **{"SIF No.": "SIF-300-05"}),
                       x(F_LOPA, "IPLs", "PFD Credited", **{"Tag": "PAL-3021"}), c(F_CUR, "alarm_id", sif_id="SIF-300-05")]),
        dict(id="B3-08", severity="high", kind="bypass closed on paper, still active in the plant",
             finding="MOC-2026-057 and out-of-service entry OOS-300-0010 record the TT-3014B bypass as restored and closed on 2026-11-04, but MOS-3014B is still active in the configuration export of 2026-11-12 06:00 (since 2026-11-04 08:00, about 190 h against 8 h), leaving SIF-300-04 on one transmitter with no live record.",
             documents=["U300-MOC-REG", "out_of_service_U-300", "U300-CFG-EXPORT", "U300-SRS-001"], tags=["TT-3014B", "MOS-3014B", "SIF-300-04", "MOC-2026-057", "OOS-300-0010"],
             evidence=[x(F_CFG, "Overrides", "Active", **{"Override Tag": "MOS-3014B"}), x(F_CFG, "Overrides", "Active Since", **{"Override Tag": "MOS-3014B"}),
                       x(F_CFG, "Overrides", "Max Duration (h)", **{"Override Tag": "MOS-3014B"}), c(F_OOS, "status", id="OOS-300-0010"), c(F_OOS, "notes", id="OOS-300-0010"),
                       x(F_MOC, "Register", "Status", **{"MOC No.": "MOC-2026-057"}), x(F_MOC, "Register", "Closed", **{"MOC No.": "MOC-2026-057"})]),
        dict(id="B3-09", severity="high", kind="compensating alarm out of service while the channel is bypassed",
             finding="PT-3012A is overridden (OOS-300-0012) with compensating measures recorded as confirmed and PAH-3013 noted as active, but PAH-3013 has been shelved since 2026-11-10 with PT-3013 isolated (OOS-300-0011); PAH-3013 is the only approved compensating measure and the SRS bypass condition for SIF-300-03, and a credited IPL in S-300-03.",
             documents=["out_of_service_U-300", "compensating_measures_U-300", "U300-SRS-001", "U300-LOPA-001", "U300-CFG-EXPORT"],
             tags=["PT-3012A", "MOS-3012A", "PAH-3013", "PT-3013", "SIF-300-03", "OOS-300-0011", "OOS-300-0012"],
             evidence=[c(F_OOS, "status", id="OOS-300-0011"), c(F_OOS, "start", id="OOS-300-0011"), c(F_OOS, "reason", id="OOS-300-0011"),
                       c(F_OOS, "compensating_measures_confirmed", id="OOS-300-0012"), c(F_OOS, "notes", id="OOS-300-0012"),
                       x(F_CFG, "Overrides", "Active", **{"Override Tag": "MOS-3012A"}), c(F_CUR, "alarm_id", sif_id="SIF-300-03"),
                       x(F_SRS, "SIF Requirements", "Bypass Conditions", **{"SIF No.": "SIF-300-03"}), x(F_LOPA, "IPLs", "PFD Credited", **{"Tag": "PAH-3013"})]),
        dict(id="B3-10", severity="high", kind="safety function implemented in the control system",
             finding="SIF-300-02 is assigned to the logic solver SIS-LS-300 in the C&E, SRS, SIL verification and index, but it is configured in the DCS controller DCS-300-C01, with LT-3005 and XV-3003 wired to DCS I/O; it is not independent of the BPCS level loop whose failure is its demand.",
             documents=["U300-CE-CHART", "U300-SRS-001", "U300-SILV-001", "U300-INST-INDEX", "U300-CFG-EXPORT"], tags=["SIF-300-02", "LT-3005", "XV-3003"],
             evidence=[x(F_CFG, "SIS Trips", "Logic Solver", **{"SIF No.": "SIF-300-02"}), x(F_CFG, "Points", "System", **{"Point Tag": "LT-3005"}),
                       x(F_CFG, "Points", "Controller", **{"Point Tag": "LT-3005"}), x(F_CFG, "Points", "System", **{"Point Tag": "XV-3003"}),
                       x(F_CFG, "Points", "Controller", **{"Point Tag": "XV-3003"}), x(F_INDEX, "Instrument Index", "System", **{"Tag No.": "LT-3005"}),
                       x(F_INDEX, "Instrument Index", "System", **{"Tag No.": "XV-3003"}), x(F_CE, "CE-300", "Logic Solver", **{"Cause Tag": "LT-3005"}),
                       x(F_SRS, "SIF Requirements", "Logic Solver", **{"SIF No.": "SIF-300-02"}), x(F_SILV, "SIF Summary", "Logic Solver", **{"SIF No.": "SIF-300-02"})]),
        dict(id="B3-11", severity="high", kind="two channels of one function overridden together",
             finding="PT-3020B and PT-3020C are both overridden at the export time (MOS-3020B and MOS-3020C active; OOS-300-0014 and OOS-300-0015 overlap), but the SRS allows only one channel of SIF-300-05 at a time and the SIL verification covers one bypassed channel only; the trip rests on PT-3020A alone.",
             documents=["U300-CFG-EXPORT", "out_of_service_U-300", "U300-SRS-001", "U300-SILV-001"], tags=["PT-3020B", "PT-3020C", "MOS-3020B", "MOS-3020C", "SIF-300-05"],
             evidence=[x(F_CFG, "Overrides", "Active", **{"Override Tag": "MOS-3020B"}), x(F_CFG, "Overrides", "Active", **{"Override Tag": "MOS-3020C"}),
                       c(F_OOS, "status", id="OOS-300-0014"), c(F_OOS, "expiry", id="OOS-300-0014"), c(F_OOS, "status", id="OOS-300-0015"), c(F_OOS, "start", id="OOS-300-0015"),
                       x(F_SRS, "SIF Requirements", "Bypass Conditions", **{"SIF No.": "SIF-300-05"}),
                       x(F_SILV, "Degraded Operation", "Degraded Voting Assumed", **{"SIF No.": "SIF-300-05", "Normal Voting": "2oo3"})]),
        dict(id="B3-12", severity="medium", kind="removed alarm still relied on",
             finding="LAL-3003 was removed under MOC-2026-058 (MADB 'Removed', no longer configured), but it is still the SRS bypass condition and the approved compensating measure for SIF-300-02 and is still listed in the alarm register; the MOC did not list the SRS or the compensating measures register and the alarm register was not revised.",
             documents=["U300-MADB-001", "U300-CFG-EXPORT", "U300-SRS-001", "compensating_measures_U-300", "U300-ALM-REG", "U300-MOC-REG"],
             tags=["LAL-3003", "LT-3003", "SIF-300-02", "MOC-2026-058"],
             evidence=[x(F_MADB, "Alarms", "Implementation Status", **{"Alarm Tag": "LAL-3003"}), e.absent(F_CFG, "Alarms", "Alarm Tag", "LAL-3003"),
                       x(F_SRS, "SIF Requirements", "Bypass Conditions", **{"SIF No.": "SIF-300-02"}), c(F_CUR, "alarm_id", sif_id="SIF-300-02"), c(F_CUR, "status", sif_id="SIF-300-02"),
                       x(F_INDEX, "Alarm Register", "Setpoint", **{"Alarm Tag": "LAL-3003"}), x(F_MOC, "Register", "Documents to Revise", **{"MOC No.": "MOC-2026-058"}),
                       x(F_MOC, "Register", "Documents Revised", **{"MOC No.": "MOC-2026-058"})]),
        dict(id="B3-13", severity="medium", kind="range of one voted transmitter differs",
             finding="LT-3002C is configured 0-1500 mm while the index gives 0-2000 mm (as LT-3002A/B are configured); the SIF-300-01 trip point of 1500 mm is at the top of that channel's configured range.",
             documents=["U300-INST-INDEX", "U300-CFG-EXPORT", "U300-CE-CHART"], tags=["LT-3002C", "SIF-300-01"],
             evidence=[x(F_INDEX, "Instrument Index", "Range", **{"Tag No.": "LT-3002C"}), x(F_CFG, "Points", "Range High", **{"Point Tag": "LT-3002C"}),
                       x(F_CFG, "Points", "Range High", **{"Point Tag": "LT-3002A"}), x(F_CFG, "SIS Trips", "Trip Setpoint", **{"SIF No.": "SIF-300-01"})]),
        dict(id="B3-14", severity="medium", kind="calculation uses the wrong sensor",
             finding="The SIL verification of SIF-300-04 takes TT-3014A and TT-3015 as the 1oo2 sensor pair; TT-3015 is the BPCS transmitter. The C&E and the configured trip use TT-3014A and TT-3014B.",
             documents=["U300-SILV-001", "U300-CE-CHART", "U300-CFG-EXPORT", "U300-INST-INDEX"], tags=["SIF-300-04", "TT-3014A", "TT-3014B", "TT-3015"],
             evidence=[x(F_SILV, "SIF Summary", "Sensor Tags", **{"SIF No.": "SIF-300-04"}), x(F_SILV, "Subsystems", "Tags", **{"SIF No.": "SIF-300-04", "Subsystem": "Sensors"}),
                       x(F_CFG, "SIS Trips", "Initiators", **{"SIF No.": "SIF-300-04"}), x(F_CE, "CE-300", "Cause Tag", **{"Cause Tag": "TT-3014B"}),
                       x(F_INDEX, "Instrument Index", "System", **{"Tag No.": "TT-3015"})]),
        dict(id="B3-15", severity="medium", kind="records disagree on when a bypass began",
             finding="The out-of-service register starts the PT-3020C override at 2026-11-12 04:00 (2 h before the export), but the logic solver shows MOS-3020C active since 2026-11-10 16:00: 38 h at the export against the 8 h limit, which the register does not show.",
             documents=["out_of_service_U-300", "U300-CFG-EXPORT", "U300-SRS-001"], tags=["PT-3020C", "MOS-3020C", "SIF-300-05", "OOS-300-0015"],
             evidence=[c(F_OOS, "start", id="OOS-300-0015"), x(F_CFG, "Overrides", "Active Since", **{"Override Tag": "MOS-3020C"}),
                       x(F_CFG, "Overrides", "Max Duration (h)", **{"Override Tag": "MOS-3020C"}), x(F_SRS, "SIF Requirements", "Bypass Conditions", **{"SIF No.": "SIF-300-05"})]),
        dict(id="B3-16", severity="medium", kind="unit conversion error in a configured limit",
             finding="PDAL-3030 is rationalised at 0.5 bar (50 kPa) but configured at 5 kPa on a point scaled 0-200 kPa: a factor of ten low, so the seal gas differential pressure alarm will not annunciate until the differential is almost lost.",
             documents=["U300-MADB-001", "U300-ALM-REG", "U300-CFG-EXPORT"], tags=["PDAL-3030", "PDT-3030"],
             evidence=[x(F_MADB, "Alarms", "Setpoint", **{"Alarm Tag": "PDAL-3030"}), x(F_MADB, "Alarms", "Units", **{"Alarm Tag": "PDAL-3030"}),
                       x(F_INDEX, "Alarm Register", "Setpoint", **{"Alarm Tag": "PDAL-3030"}), x(F_CFG, "Alarms", "Limit", **{"Alarm Tag": "PDAL-3030"}),
                       x(F_CFG, "Alarms", "Units", **{"Alarm Tag": "PDAL-3030"}), x(F_CFG, "Points", "Range High", **{"Point Tag": "PDT-3030"})]),
        dict(id="B3-17", severity="medium", kind="installed instrument missing from the index",
             finding="PT-3033 (MOC-2026-054, implemented) is on PID-300-003 and configured in the DCS, but it is not in the instrument index, which the MOC lists as still to be revised.",
             documents=["U300-INST-INDEX", "PID-300-003", "U300-CFG-EXPORT", "U300-MOC-REG"], tags=["PT-3033", "MOC-2026-054"],
             evidence=[e.absent(F_INDEX, "Instrument Index", "Tag No.", "PT-3033"), x(F_CFG, "Points", "Description", **{"Point Tag": "PT-3033"}),
                       c(F_TOPO, "line_no", sheet="PID-300-003", **{"from": "BL-330", "to": "PT-3033"}), x(F_MOC, "Register", "Status", **{"MOC No.": "MOC-2026-054"}),
                       x(F_MOC, "Register", "Documents to Revise", **{"MOC No.": "MOC-2026-054"}), x(F_MOC, "Register", "Documents Revised", **{"MOC No.": "MOC-2026-054"})]),
        dict(id="B3-18", severity="medium", kind="document recorded as revised but not revised",
             finding="MOC-2026-056 (closed) raised LAH-3003 from 1100 to 1200 mm and records the alarm register as revised; the MADB and the configuration say 1200 mm but the alarm register still says 1100 mm.",
             documents=["U300-ALM-REG", "U300-MADB-001", "U300-CFG-EXPORT", "U300-MOC-REG"], tags=["LAH-3003", "LT-3003", "MOC-2026-056"],
             evidence=[x(F_INDEX, "Alarm Register", "Setpoint", **{"Alarm Tag": "LAH-3003"}), x(F_MADB, "Alarms", "Setpoint", **{"Alarm Tag": "LAH-3003"}),
                       x(F_CFG, "Alarms", "Limit", **{"Alarm Tag": "LAH-3003"}), x(F_MOC, "Register", "Documents Revised", **{"MOC No.": "MOC-2026-056"}),
                       x(F_MOC, "Register", "Status", **{"MOC No.": "MOC-2026-056"})]),
        dict(id="B3-19", severity="medium", kind="rationalised alarm not configured",
             finding="FAH-3032 (primary seal vent flow high, High priority) is in the MADB as implemented and in the alarm register, but no such alarm is configured.",
             documents=["U300-MADB-001", "U300-ALM-REG", "U300-CFG-EXPORT"], tags=["FAH-3032", "FT-3032"],
             evidence=[x(F_MADB, "Alarms", "Implementation Status", **{"Alarm Tag": "FAH-3032"}), x(F_INDEX, "Alarm Register", "Priority", **{"Alarm Tag": "FAH-3032"}),
                       e.absent(F_CFG, "Alarms", "Alarm Tag", "FAH-3032"), x(F_CFG, "Points", "System", **{"Point Tag": "FT-3032"})]),
        dict(id="B3-20", severity="medium", kind="credited operator response slower than the time available",
             finding="The LOPA credits TAH-3015 in S-300-04 on the basis that 10 min are available between the alarm and the trip point, but the MADB rationalises TAH-3015 with a time to respond of 30 min.",
             documents=["U300-LOPA-001", "U300-MADB-001"], tags=["TAH-3015", "TT-3015", "S-300-04", "SIF-300-04"],
             evidence=[x(F_LOPA, "IPLs", "Description", **{"Tag": "TAH-3015"}), x(F_LOPA, "IPLs", "PFD Credited", **{"Tag": "TAH-3015"}),
                       x(F_MADB, "Alarms", "Time to Respond", **{"Alarm Tag": "TAH-3015"}), x(F_MADB, "Alarms", "IPL Credit", **{"Alarm Tag": "TAH-3015"})]),
        dict(id="B3-21", severity="low", kind="calculation cites a superseded target",
             finding="The SIL verification takes the SIF-300-05 target from SRS Rev B (RRF 10); the current SRS Rev C and the LOPA require RRF 20. The achieved RRF still exceeds both.",
             documents=["U300-SILV-001", "U300-SRS-001", "U300-LOPA-001"], tags=["SIF-300-05"],
             evidence=[x(F_SILV, "SIF Summary", "Target Source", **{"SIF No.": "SIF-300-05"}), x(F_SILV, "SIF Summary", "RRF Target", **{"SIF No.": "SIF-300-05"}),
                       x(F_SRS, "SIF Requirements", "RRF Target", **{"SIF No.": "SIF-300-05"}), x(F_LOPA, "Scenarios", "Required RRF", **{"Scenario No.": "S-300-05"}),
                       f"{F_SRS}:SIF Requirements:A2 = {docline('U300-SRS-001', 'C', 'As Built')}"]),
        dict(id="B3-22", severity="low", kind="change made before approval",
             finding="MOC-2026-060 (in review, not approved) proposes raising the TAH-3016 on-delay from 10 s to 60 s; the configuration already has 60 s while the MADB has 10 s.",
             documents=["U300-MOC-REG", "U300-MADB-001", "U300-CFG-EXPORT"], tags=["TAH-3016", "TT-3016", "MOC-2026-060"],
             evidence=[x(F_MOC, "Register", "Status", **{"MOC No.": "MOC-2026-060"}), x(F_MOC, "Register", "Approved", **{"MOC No.": "MOC-2026-060"}),
                       x(F_MADB, "Alarms", "On-delay", **{"Alarm Tag": "TAH-3016"}), x(F_CFG, "Alarms", "On-delay", **{"Alarm Tag": "TAH-3016"})]),
        dict(id="B3-23", severity="low", kind="configured alarm never rationalised",
             finding="PAH-3006 (PT-3006, 32 barg, Low) is configured in the DCS but is in neither the MADB nor the alarm register.",
             documents=["U300-CFG-EXPORT", "U300-MADB-001", "U300-ALM-REG"], tags=["PAH-3006", "PT-3006"],
             evidence=[x(F_CFG, "Alarms", "Limit", **{"Alarm Tag": "PAH-3006"}), e.absent(F_MADB, "Alarms", "Alarm Tag", "PAH-3006"),
                       e.absent(F_INDEX, "Alarm Register", "Alarm Tag", "PAH-3006")]),
        dict(id="B3-24", severity="low", kind="instrument location differs between index and drawing",
             finding="The index places TT-3008 on L-302 (compressor suction, downstream of V-301); the P&ID extraction shows it on L-301, upstream of the scrubber.",
             documents=["U300-INST-INDEX", "PID-300-001"], tags=["TT-3008"],
             evidence=[x(F_INDEX, "Instrument Index", "Line / Equipment No.", **{"Tag No.": "TT-3008"}), c(F_TOPO, "line_no", **{"to": "TT-3008"}),
                       c(F_TOPO, "line_no", **{"from": "TT-3008"})]),
        dict(id="B3-25", severity="low", kind="document register out of date",
             finding="The document register lists the cause & effect chart U300-CE-CHART at Rev B; the chart in use is Rev C (re-issued under MOC-2026-053).",
             documents=["U300-DOC-REGISTER", "U300-CE-CHART"], tags=[],
             evidence=[c(F_DOCREG, "Rev", **{"Document No.": "U300-CE-CHART"}), f"{F_CE}:CE-300:A2 = {docline('U300-CE-CHART', 'C', 'As Built')}",
                       x(F_MOC, "Register", "Notes", **{"MOC No.": "MOC-2026-053"})]),
    ]
    controls = [
        dict(id="CC3-01", description="SIF-300-05 trip setpoint: 0.8 barg in the C&E and the configuration, 80 kPag in the SRS.",
             why_consistent="80 kPa is 0.8 bar; the same value in another unit."),
        dict(id="CC3-02", description="SIF-300-01 trip setpoint: 1500 mm in the C&E and the configuration, 1.5 m in the SRS.",
             why_consistent="1.5 m is 1500 mm."),
        dict(id="CC3-03", description="PDT-3023 and PDAH-3023: index range 0-2.5 bar and alarm 1 bar (register, MADB) against a configured range of 0-250 kPa, limit 100 kPa and deadband 5 kPa. The configured range of PDT-3030 (0-200 kPa against 0-2 bar) and the PDAL-3030 deadband are the same kind.",
             why_consistent="Correct conversions at 100 kPa per bar. Only the PDAL-3030 limit (B3-16) is wrong."),
        dict(id="CC3-04", description="LT-3002B overridden: MOS-3002B active since 2026-11-12 01:30, out-of-service entry OOS-300-0013 active from 01:30 to 09:30.",
             why_consistent="One channel of a 2oo3 function, 4.5 h at the export against the 8 h limit, authorised, the times agree between the register and the logic solver, and the compensating alarm LAH-3003 is configured, enabled and not shelved."),
        dict(id="CC3-05", description="MOC-2026-052 proposed lowering the SIF-300-04 trip from 175 to 165 degC; every document and the configuration still say 175 degC and no document was revised.",
             why_consistent="The change was cancelled, so nothing should have changed."),
        dict(id="CC3-06", description="LAH-3003 is listed in the LOPA IPL sheet for S-300-01 with no PFD, and is marked 'IPL Credit: No' in the MADB, yet it is the approved compensating measure and the SRS bypass condition for SIF-300-01.",
             why_consistent="A deliberate non-credit: the alarm shares LT-3003 with the initiating loop, so the LOPA takes no credit and the required RRF of 100 is calculated without it. It is independent of the SIS transmitters, which is what a compensating measure for a bypassed SIS channel needs."),
        dict(id="CC3-07", description="PT-3011 remark says it was re-ranged from 0-100 to 0-120 barg; MOC-2026-050.",
             why_consistent="Closed properly: index and configuration both say 0-120 barg and the one document to revise was revised."),
        dict(id="CC3-08", description="PT-3007B temporary bypass (MOC-2026-051, OOS-300-0009).",
             why_consistent="Closed on paper and in the plant: MOS-3007B is not active, the entry is closed, 6.2 h against the 8 h limit."),
        dict(id="CC3-09", description="VAH-3017B is disabled in the configuration while the MADB says implemented.",
             why_consistent="A recorded, in-date temporary state: MOC-2026-059 (implemented, expires 2026-11-19) and out-of-service entry OOS-300-0016 (active to 2026-11-19). The alarm is not credited in the LOPA and is nobody's compensating measure; VAH-3017A remains in service."),
        dict(id="CC3-10", description="SIF-300-03, -04, -05 and -06 achieve a higher SIL band in the SIL verification than their target; PAH-3011 (75 barg) and PAH-3013 (76 barg) are two high pressure alarms on the discharge with different limits.",
             why_consistent="Exceeding a target is not a discrepancy; the two alarms are on different transmitters (PT-3011 anti-surge, PT-3013 monitoring) and every document gives each the same limit."),
    ]
    return {
        "_note": ("SEALED answer key for the blind test of unit U-300 (export gas compressor K-301 with suction scrubber V-301, aftercooler E-301, "
                  "anti-surge recycle, lube oil and seal gas). ALL DATA IS SYNTHETIC; not a real facility. Written by scripts/make_dummy_batch3.py, which "
                  "builds every document from one consistent design and applies each planted item as one named override, then reads the evidence cells "
                  "back from the files. Expected on load and not discrepancies in themselves: (1) the LOPA loader reports the LAH-3003 row of the IPL "
                  "sheet as skipped, 'listed, not credited' (clean control CC3-06); (2) the configuration loader reports the MOS-3xxx override switches as configured-only points "
                  "and PAH-3006 (item B3-23) as a new alarm; (3) PT-3033 is on a drawing and configured but not in the index (item B3-17); (4) HS-3001, PSV-3050 and XY-3040 are in the index with a P&ID number "
                  "but are not in the topology CSV, because that format would read push-button, relief valve and relay tags as equipment: a finding "
                  "that these three are 'not on a drawing' is an artefact of the format, neither planted nor a fair false alarm; (5) with no PDF, "
                  "P&ID revisions are unknown to the loaders. Several items touch the same function (for example SIF-300-05: B3-07, B3-11, B3-15, "
                  "B3-21; the PT-3012A override in B3-09 depends on an alarm that is itself shelved). A finding that states the consequence of two "
                  "planted items together should be credited to both. Timestamps: configuration export 2026-11-12 06:00."),
        "unit": UNIT,
        "items": items,
        "clean_controls": controls,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_index()
    write_ce()
    write_srs()
    write_lopa()
    write_silv()
    write_madb()
    write_cfg()
    write_moc()
    write_docreg()
    write_curated()
    write_oos()
    write_topology()
    write_unit_json()
    key = answer_key()
    (OUT / F_KEY).write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sev = {}
    for it in key["items"]:
        sev[it["severity"]] = sev.get(it["severity"], 0) + 1
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")
    print(f"instruments {len(INSTRUMENTS)}, SIFs {len(SIFS)}, alarms {len(ALARMS)}, MOCs {len(MOCS)}, planted {len(key['items'])} {sev}, "
          f"clean controls {len(key['clean_controls'])}")


if __name__ == "__main__":
    main()
