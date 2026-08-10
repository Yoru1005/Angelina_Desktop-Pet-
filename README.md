# Angelina 桌寵

使用 PySide6 製作的 Windows 透明動畫桌寵。

## 功能

- 透明背景的桌面動畫角色
- 預設維持在其他視窗上方
- 播放數輪動畫後自動隨機切動作
- 右鍵開啟桌寵旁的中文功能選單
- 直接選擇 10 種動作
- 放大或縮小桌寵
- 開啟或關閉永遠置頂
- 固定形態與自由移動形態
- 系統托盤、單實例保護及開機自動啟動
- 全螢幕程式執行時自動隱藏
- 主動字幕與本機聊天紀錄
- 支援 OpenAI 相容 API 聊天

## 操作方式

- 左鍵拖曳：移動桌寵
- 滑鼠滾輪：調整大小
- 雙擊左鍵：隨機切換動作
- Ctrl + 雙擊左鍵：開啟聊天
- 右鍵：在桌寵旁邊開啟功能選單

## 聊天設定

右鍵桌寵並選擇 `設定…`，啟用聊天後填入 OpenAI 相容 API 網址、API 金鑰與模型名稱。API 金鑰只保存在本機 `settings.json`；此檔案已加入 `.gitignore`，請勿手動提交。

聊天紀錄儲存在本機 `chat_history.json`，最多保留 200 則訊息。

## 專案內容

- `angelina_pet.py`：PySide6 桌寵主程式
- `assets/`：透明動畫影格與 `manifest.json`
- `prepare_assets.py`：將原始 GIF 轉換為透明動畫影格
- `build.ps1`：安裝相依套件並封裝 Windows EXE
- `requirements.txt`：Python 套件相依

## 系統需求

- Windows 10/11
- 64 位元 Python 3.10 以上版本

## 執行原始碼

在 PowerShell 進入專案資料夾，執行：

```powershell
py -m pip install -r requirements.txt
py .\angelina_pet.py
```

如果系統找不到 `py`，改用：

```powershell
python -m pip install -r requirements.txt
python .\angelina_pet.py
```

## 封裝為 EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

完成後的執行檔位於：

```text
dist\Angelina桌寵.exe
```

修改原始碼後必須重新封裝，舊 EXE 不會自動更新。

## 技術說明

桌寵介面使用 PySide6 統一處理透明視窗、動畫、滑鼠事件與中文右鍵選單，避免原生 Windows 分層視窗與選單互相遮擋。
