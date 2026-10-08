# Create Color Legend — 0.2.0-candidate

候選來源已補齊，Revit 2026 原生操作驗收尚未完成；沒有正式下載 Release。
Candidate source is archived. Native Revit 2026 acceptance is pending; no production download release is offered.

Source provenance: `43906e98b14c8c34b3e19954d22b3bd5b8214a43`.
The nine original button files are preserved byte-for-byte; see SOURCE_MANIFEST.json.

選取來源樓層平面、Category 與材質，以 Description 與 Material.Color 建立或更新圖例。
Select a source floor plan, categories and materials to create/update a Description/RGB legend.
Casework／Generic Models 使用範圍內 solid 面材質；Walls 使用外側構造層、Floors 上層、Ceilings 下層。
Casework/Generic Models use scoped solid-face materials; Walls use the exterior layer, Floors the top layer, Ceilings the bottom layer.

依主要 View Range 與 Crop 掃描，忽略 Plan Region 局部範圍，不保證完全重現其畫面。
Scope follows the main View Range and Crop; local Plan Region ranges are ignored.
每張圖例保存 Category 與排除材質；Update All 逐張交易，部分失敗須逐項檢查。
Categories/exclusions persist per legend. Update All commits independently per legend; inspect partial failures.
掃描失敗保留舊圖例。工具寫入自有圖例註解及登記，不改來源材質，不自動 Save/Sync。
Failed scans preserve old legends. The tool changes owned annotations/registration, not source materials; no automatic Save/Sync.

## Environment / 環境
Target: Revit 2026, existing pyRevit, IronPython 2.7.12 and .NET/WPF.
本機 imports 全在本按鈕資料夾；不需要 extension/lib，也不需新服務或安裝器。
Local imports reside inside the pushbutton. No shared extension/lib or new service/installer is required.

## Coexistence / 多工具共存
Candidate testing only: back up and merge only Materials.panel/Create Color Legend.pushbutton.
只處理本按鈕，保留所有其他工具、panel、tab、lib、extension.json 及設定。
Never delete the entire shared YSU Tools.extension. Disable by moving only this button outside the extension search path and Reload.
本輪沒有修改使用中的 extension，也沒有執行或存檔模型。
The installed extension and models were not modified by this source-publication task.

See [VALIDATION.md](VALIDATION.md) for exact evidence limits and pending acceptance.
