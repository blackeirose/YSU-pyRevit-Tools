面材質查詢 / Pick Face Material
套件版本 / Package version: 1.0.1
文件修正 patch；執行程式與 v1.0.0 完全相同。
Documentation-only patch; executable files are byte-identical to v1.0.0.

用途與限制
點選目前模型表面，優先辨識 Paint 材質，複製名稱並開啟 Materials。無法解析材質或連結模型表面不支援；不修改模型。
涉及刪除的工具請先在副本操作，確認預覽、模型備份與 worksharing 狀態。

安裝／更新（多工具共存）
1. 已安裝 Revit 與 pyRevit 後，在 pyRevit Settings 確認目前 extensions 搜尋位置。
2. 解壓到獨立暫存目錄，保留 .extension/.tab/.panel/.pushbutton 結構。
3. 若已有 YSU Tools.extension，先備份本工具按鈕，再只合併以下目標：
   YSU Tools.extension/YSU Tools.tab/Materials.panel/Pick Face Material.pushbutton
4. 若有同名檔案或 lib，先比較版本／雜湊；內容不同時停止合併，確認所有引用後再處理。不要覆蓋其他工具、extension.json 或共用設定。
5. Sheet/View 包還需要 lib/__init__.py 與 lib/ysu_sheets.py。另兩包不需要共用 lib。
6. 全新安裝可放入本包的 extension；共存安裝只合併缺少的目錄與經確認的目標檔案。Reload pyRevit 或重新啟動 Revit。

安全卸載／回復
只將上述目標 .pushbutton 移出 extension 搜尋目錄，再 Reload。保留其他按鈕、panel、tab、設定及整個共用 YSU Tools.extension。
移除 lib 前，必須查明所有其他按鈕都沒有引用；不確定就保留。更新回復只還原事先備份的本工具檔案，不能整包覆蓋共用 extension。

環境與驗證界線
原始 README 宣告相容範圍：Revit 2019+、pyRevit 4.8+。這不是逐版本或跨引擎實測證據。
本次僅驗證包裝、依賴、Python 語法與既有執行檔一致性；沒有新做 Revit 執行驗收，不保證全部版本通過。
已驗證的下載／雜湊與 Revit 操作驗收分開記錄。SHA-256 見 Release 隨附校驗檔；包內 manifest 列出內容雜湊。

INSTALL / UPDATE
Extract into staging first. Locate your configured pyRevit extensions directory.
Back up only this tool's existing pushbutton, then merge the exact target above.
Preserve neighboring tools, shared extension.json and settings. Compare duplicate
files and libraries before replacing; stop on a mismatch until every consumer is understood.
Sheet/View additionally needs lib/__init__.py and lib/ysu_sheets.py. The other two tools need no shared library.
For a new installation use the supplied extension; for coexistence merge only missing folders and reviewed target files. Reload pyRevit or restart Revit.

UNINSTALL / RECOVERY
Move only the target .pushbutton outside extension search paths, then Reload.
Never delete the entire shared YSU Tools.extension. Remove libraries only after
checking every remaining tool for references; retain them when uncertain.
To undo an update, restore only the target files backed up before this update.

COMPATIBILITY / EVIDENCE
Legacy declared range: Revit 2019+; pyRevit 4.8+. This is not a tested-version matrix
or proof of compatibility with every Python engine. No new Revit runtime test
was performed for this packaging patch. Package verification and HTTP downloads
are separate from browser-download and native Revit execution acceptance.

PICK FACE MATERIAL
Version: 1.0.1

Purpose:
Lets you pick a face in the active Revit model and immediately identify
its material. If the face has a Paint override, that painted material is
used; otherwise the face's base material is used. The material's exact
name is copied to the Windows clipboard, and Revit's Materials browser is
opened automatically so you can paste the name into its search box. The
tool never modifies the model.

Usage:
1. Click "Pick Face Material" on the YSU Tools tab (Materials panel).
2. Pick a face in the active model when prompted.
3. The material name is copied to the clipboard and the Materials
   browser opens.
4. Press Esc while picking to cancel with no action.

Notes / limitations:
- Faces belonging to linked Revit models are not supported in this
  version; pick a face in the active (host) model.
- If a face uses category/default graphics with no assigned material,
  or geometry the tool cannot resolve, no material can be identified.
- Only the "Pick Face Material" tool (Materials panel) is included in
  this package. Other tools from the full YSU Tools extension are not
  part of this download.
