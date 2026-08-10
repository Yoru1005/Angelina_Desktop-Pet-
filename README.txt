Angelina 桌寵
=============

功能：
- 透明背景的桌面動畫角色
- 預設維持在其他視窗上方
- 播放數輪動畫後自動隨機切換動作
- 右鍵開啟桌寵旁的 PySide6 中文功能選單

操作方式：
- 左鍵拖曳：移動桌寵
- 滑鼠滾輪：調整大小
- 雙擊左鍵：隨機切換動作
- 右鍵：在桌寵旁邊開啟功能選單

右鍵功能選單：
- 直接選擇 10 種動作
- 放大或縮小桌寵
- 開啟或關閉永遠置頂
- 顯示滑鼠操作說明
- 退出桌寵

執行原始碼：
1. 安裝 64 位元 Python 3.10 以上版本。
2. 在 PowerShell 執行：

    py -m pip install -r requirements.txt
    py .\angelina_pet.py

封裝為 EXE：

    powershell -ExecutionPolicy Bypass -File .\build.ps1

完成後的執行檔位於 dist 資料夾。修改原始碼後必須重新封裝，舊 EXE 不會自動更新。

系統需求：
- 僅支援 Windows。
- 介面使用 PySide6，可透過 requirements.txt 安裝。
