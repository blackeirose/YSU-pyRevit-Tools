# Create Color Legend 0.2.0-candidate

已安裝，待 Reload 實測。Target: Revit 2026 / pyRevit IronPython 2.7.12.

0.2.0：選 Category（Casework、Generic Models、Walls、Floors、Ceilings，可複選；新圖例預設 Casework）→ 掃描 → 勾選材質（色塊、Description、Name、Category、ID；搜尋、全選／全不選目前顯示、已選／總數）→ 建立或更新。Walls 只取 Exterior 最外層、Floors 只取最上層、Ceilings 只取最下層構造層；Casework／Generic Models 依範圍內每個 solid 的面材質。每張圖例記住自己的 Category 與排除材質（與圖例同一交易寫入）；新材質預設納入、曾排除者持續排除。Curtain／Stacked／In-Place 牆樓板天花、無構造類型、表層無材質等在範圍內時於寫入前列出並停止，保留圖例與設定。舊版圖例視為 Casework、無排除，可直接更新。Revit 內成功仍為 UNVERIFIED。

0.1.4：有 Plan Region 的平面不再整份拒絕。依使用者決策忽略 Plan Region 的局部 View Range，所有 Casework solid 一律以來源平面的主要 View Range＋Crop 逐一裁切判定；Region 內外符合主要範圍者都納入，只在局部範圍內出現者不納入。有 Plan Region 時，另外檢查 View collector 可能因局部範圍漏掉的 Casework，並套用可由 API 判定的 View 隱藏規則（元素隱藏、類別、篩選器、Phase、Workset）；Design Option 等無法可靠判定者明確停止並保留舊圖例。結果顯示「已忽略 Plan Region 局部範圍，依主要 View Range 掃描。」圖例因此不保證等同 Plan Region 局部顯示差異。工具不修改 Plan Region、View Range 或 View Template。

0.1.3：0.1.2 在「Write / Text layout and move」以 `TextNote.get_BoundingBox(view)` 量測新文字，Revit 2026.4 回傳 null 而整份 rollback（Cannot measure text layout）。改用 Autodesk 文件化的 `TextElement.Height`（圖紙單位、Regenerate 後依內容與換行計算）排列高；文字以 Left/Top 對齊直接放在色塊右側，不再依 bounding box 搬移。文字類型有邊框時加上 Leader/Border Offset。來源平面若隱藏 Text Notes／Detail Items／註解類別，會在選文字類型前明確停止，不修改 View 設定。每列輸出 `Color Legend text layout` 診斷；失敗訊息附 Active View、OwnerViewId、文字類型、比例與量測值。Revit 內建立成功仍為 UNVERIFIED。

0.1.2：新建完成後的 ownership 讀回驗證與既有元素修改保護分開。原生 Sketch 尺寸需有建立當下的身分與 references 記錄；後加人工尺寸、未知或跨 View 相依仍阻擋。刪除沿用同一保護並檢查實際連帶刪除 ID。首次建立會輸出相依診斷；出錯請保留完整 pyRevit output。原始事故的實際相依元素未讀取，Revit 建立／更新成功為 UNVERIFIED。

修補首次材質掃描的 ElementId overload ambiguity；保留既有 ID，數值 ID 明確使用 System.Int64。真實 CLR binding 回歸已通過，尚不代表 Revit 中已成功建立圖例。失敗會提供階段、來源 View、相關元素、原始錯誤與完整 traceback，明確區分寫入前失敗、確認 rollback 或復原狀態不明。

`pyRevit → Reload → YSU Tools → Materials → Create Color Legend`

- Create Legend：從 Floor Plan 或 Sheet 的 Floor Plan Viewport 開始，選既有文字類型，再點來源平面的圖例左上角。
- Update Current Legend：更新目前來源平面的工具圖例。
- Update All Tool Legends：各自重掃此文件所有已登記圖例的來源平面。

本機 Casework solid 的直接材質；一個 In-Place Component 中可有多個各自指定材質的 solid。列文字使用原始 Description；方框使用 Material.Color。缺 Description 會獨立列出並報告材質 ID。取消不保留圖例或 Type，不需手動設定 Work Plane。

此版明確拒絕 Underlay、Split／特殊 Crop、dependent views、非有限 View Range、Mesh、同一連通 solid 多面材質等不支援情況。掃描錯誤時保留舊圖例；成功零結果清除工具列但保留登記。複製 View metadata 不符時停止，不修改原 View。

先在隔離測試文件驗收跨樓層移動、RGB、長文字、重複更新、Undo、手動存檔重開。沒有執行 Revit runtime 驗收，不宣稱已完整通過。工具不 Save／Sync、不修改 Material，不主動取得他人所有權。

完整規格、限制、來源及驗證紀錄位於 source repo 的 `tools/create-color-legend/README.md` 與 `VALIDATION.md`。停用時只將此 `.pushbutton` 資料夾移出 extension 後 Reload，保留其他工具。
