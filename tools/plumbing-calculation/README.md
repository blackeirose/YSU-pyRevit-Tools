# Plumbing Calculation — Revit → Web bridge (unreleased)

Source under the existing `YSU Tools.extension / YSU Tools.tab / Planning.panel /
Plumbing Calculation.pushbutton`. One button; no PDF/Image/calculator buttons.
Canonical Web URL: https://tools.ycsu.cc/plumbing-chart/

Select an explicitly chosen ViewSchedule in the active project. Read formatted
Body cells through ViewSchedule.GetCellText, using GetTableData/GetSectionData
and actual section index bounds. Visible ScheduleFields supply column headings;
unsupported column/field counts fail rather than guess. Body header, blank,
subtotal and grand-total rows remain for explicit Web review. No Transaction,
model writes, room/geometry reconstruction, engineering formulas or XLSX engine.

The dependency-free Python 2.7/3-compatible `handoff.py` creates schemaVersion 1
JSON (source, documentTitle, scheduleName, scheduleId, indexed columns and string
rows), UTF-8 encodes it and creates unpadded base64url in `#revit=`. Complete URL
limit: 2,000 characters. Measured SHYFC fixture: 547 JSON bytes / 774 URL chars.
No truncation/compression/upload. Windows ProcessStartInfo.UseShellExecute opens
the default HTTPS browser without a shell command or embedded browser.

Web imports into the existing calculation/Excel engine. Explicit mapping, row
edits and exclusions happen in the browser. Clear Revit Import returns to normal
PDF/Image/multi-file use. The fragment is removed only after successful parsing.

Development baseline: `77dd904215caead0d153ceaf9cadc63a6a311ddb`.
Core loaded from GitHub revision `57a69136b7473718dfcf26311ae801f033696f05`.
Web companion repo: `blackeirose/arch-tools-plumbing-calculation`, branch
`feature/revit-web-bridge-v1`. No independent/native review PASS is claimed.
Tests: `python -m unittest discover -s tools/plumbing-calculation/tests -v`
(five pure tests passed), plus Web Edge Python→fragment→decode→golden→Excel.
Golden totals remain 5/3/2/3/2/2/1.

## Native acceptance pending

No downloadable package/release/tag until owner acceptance. Revit version and
pyRevit runtime support must be recorded after actual tests; compatibility is
not claimed from syntax checks. Default browser launch/length limit has not been
tested inside Revit. Test schedule selection/cancel, no project/schedules, empty
and unsupported tables, large payload, browser failure, golden schedule, edits,
Excel generation and clear→PDF/Image. Check document remains unchanged.

For owner testing, add only this pushbutton folder to Planning.panel of the
existing configured YSU extension, then reload pyRevit. Do not replace extension
roots/shared libraries or install another extension. Canonical Web must have the
approved handoff release before this button can complete a production round trip.
Remove only the added pushbutton folder to uninstall the bridge.
