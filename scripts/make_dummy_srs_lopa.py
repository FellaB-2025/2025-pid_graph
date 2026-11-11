"""Fabricate a Safety Requirements Specification and a LOPA report for unit U-100,
as tabular registers (the form these documents are exported in for a project's
safety register). DUMMY DATA. Deliberate discrepancies so the reconciliation has
something to find:

  * LOPA scenario S-100-02 requires SIL 2 for SIF-100-02; the SRS and the C&E say SIL 1
  * LOPA scenario S-100-01 credits alarm PAH-1001 (alarm + operator response) as an IPL
    alongside SIF-100-01 - but PAH-1001 derives from PT-1001A, one of the SIF's initiators
  * SRS trip setpoint for SIF-100-01 is 65 barg; the C&E says 68 barg
  * LOPA credits relief valve PSV-1001, which is not in the instrument index

    python scripts/make_dummy_srs_lopa.py
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"


def _title(ws, title, doc, rev):
    ws.append([title]); ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Document No. {doc}    Rev {rev}    Status: Issued for Design    (DUMMY DATA - not a real facility)"])
    ws.append([])


def make_srs():
    wb = Workbook()
    ws = wb.active
    ws.title = "SIF Requirements"
    _title(ws, "SAFETY REQUIREMENTS SPECIFICATION - UNIT 100 FEED GAS INLET", "U100-SRS-001", "B")
    ws.append(["SIF No.", "Functional Description", "Hazard / Consequence", "SIL Target", "RRF Target", "PFDavg Target", "Demand Mode",
               "Safe State", "Process Safety Time", "SIF Response Time", "Trip Setpoint", "Sensor Architecture", "Final Element Architecture",
               "Proof Test Interval", "Bypass Conditions", "Manual Shutdown", "Reset", "Logic Solver", "Protected Equipment"])
    for c in ws[4]:
        c.font = Font(bold=True)
    ws.append(["SIF-100-01", "On feed gas high-high pressure, close XV-1001 and open BDV-1001 to protect V-1002", "Overpressure of inlet KO drum V-1002; loss of containment",
               2, 250, 0.004, "Low demand", "XV-1001 closed, BDV-1001 open", "120 s", "30 s", "65 barg", "2oo3 PT", "1oo2 (XV-1001 or BDV-1001)",
               "12 months", "Bypass permitted for testing only, one channel at a time, with PAH-1005 confirmed active; max 8 h", "HS-1001 on panel", "Manual, after cause cleared", "SIS-LS-100", "V-1002"])
    ws.append(["SIF-100-02", "On inlet KO drum high-high level, close XV-1001 and XV-1002 to prevent liquid carry-over", "Liquid carry-over to compressor; equipment damage",
               1, 25, 0.04, "Low demand", "XV-1001 closed, XV-1002 closed", "300 s", "60 s", "1750 mm", "2oo3 LT", "1oo2 (XV-1001 or XV-1002)",
               "12 months", "Bypass permitted with LAH-1006 confirmed active and operator on watch; max 4 h", "HS-1001 on panel", "Manual", "SIS-LS-100", "V-1002"])
    ws.append(["SIF-100-03", "On feed gas low-low pressure (reverse flow), close XV-1001", "Reverse flow from V-1002 to battery limit",
               1, 15, 0.06, "Low demand", "XV-1001 closed", "60 s", "20 s", "5 barg", "1oo1 PT", "1oo1 (XV-1001)",
               "12 months", "No bypass without a temporary low-pressure alarm configured; max 2 h", "HS-1001 on panel", "Manual", "SIS-LS-100", "V-1002"])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    p = OUT / "U100-SRS-001-Rev-B.xlsx"
    wb.save(p)
    return p


def make_lopa():
    wb = Workbook()
    ws = wb.active
    ws.title = "Scenarios"
    _title(ws, "LAYER OF PROTECTION ANALYSIS - UNIT 100 FEED GAS INLET", "U100-LOPA-001", "A")
    ws.append(["Scenario No.", "Node / Equipment", "Initiating Event", "IE Frequency (/yr)", "Consequence", "Severity", "Tolerable Frequency (/yr)",
               "Conditional Modifiers", "Required SIF", "Required RRF", "Required SIL", "Notes"])
    for c in ws[4]:
        c.font = Font(bold=True)
    ws.append(["S-100-01", "V-1002", "PIC-1005 / PV-1005 fails open on upstream pressure surge", 0.1, "Overpressure of V-1002 above design; loss of containment", "Cat 4", 1e-5,
               "Probability of ignition 0.5", "SIF-100-01", 200, 2, "PSV-1001 also credited; SIF sized for residual"])
    ws.append(["S-100-02", "V-1002", "LIC-1006 / LV-1006 fails closed; slug from upstream", 0.2, "Liquid carry-over to K-201 compressor", "Cat 3", 1e-4,
               "-", "SIF-100-02", 100, 2, "Required RRF 100 puts the SIF at SIL 2"])
    ws.append(["S-100-03", "V-1002", "Upstream depressurisation; reverse flow from V-1002", 0.05, "Reverse flow to battery limit", "Cat 2", 1e-3,
               "-", "SIF-100-03", 10, 1, ""])
    ws2 = wb.create_sheet("IPLs")
    _title(ws2, "LOPA - INDEPENDENT PROTECTION LAYERS CREDITED", "U100-LOPA-001", "A")
    ws2.append(["Scenario No.", "IPL Type", "Tag", "Description", "PFD Credited"])
    for c in ws2[4]:
        c.font = Font(bold=True)
    rows = [
        ("S-100-01", "BPCS", "PIC-1005", "Pressure control loop (initiating event source - not credited)", ""),
        ("S-100-01", "Alarm + operator response", "PAH-1001", "High pressure alarm, operator closes HV-1001", 0.1),
        ("S-100-01", "Relief", "PSV-1001", "Relief valve on V-1002 to flare", 0.01),
        ("S-100-01", "SIF", "SIF-100-01", "High-high pressure trip", 0.005),
        ("S-100-02", "Alarm + operator response", "LAH-1006", "High level alarm, operator reduces feed", 0.1),
        ("S-100-02", "SIF", "SIF-100-02", "High-high level trip", 0.01),
        ("S-100-03", "SIF", "SIF-100-03", "Low-low pressure trip", 0.1),
    ]
    for r in rows:
        ws2.append(list(r))
    for w in (ws, ws2):
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = 24
    p = OUT / "U100-LOPA-001-Rev-A.xlsx"
    wb.save(p)
    return p


if __name__ == "__main__":
    print(make_srs())
    print(make_lopa())
