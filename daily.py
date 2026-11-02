#!/usr/bin/env python3
"""每日更新（GitHub Actions 與本機共用）：fetch → check → select → ToAlpha → build → extras（A/B/C 分頁資料）。完全不需要 LLM。
用法：python3 daily.py [--force] [--no-toalpha]
  --force       不檢查「今天是否交易日」，直接用最新一個完整交易日重建（手動測試／補跑用）
  --no-toalpha  不呼叫 ToAlpha（詳情沿用上次資料並標註日期）
結束碼：0 正常（含休市日略過，無變更）、其他＝真的出錯。"""
import sys, time
import build, toalpha_fetch

def main():
    force = "--force" in sys.argv; skip_ta = "--no-toalpha" in sys.argv
    tries = 1 if force else 7          # 行情已出但法人/上櫃資料未齊時，每 5 分鐘重試，最多再等 30 分鐘
    for t in range(tries):
        build.fetch()
        if force: break
        try: build.cmd_check(); break
        except SystemExit as e:
            if e.code == 3: print("休市日，不更新。"); return 0
            if e.code == 4 and t < tries - 1: print("資料未齊，5 分鐘後重試（%d/%d）" % (t + 1, tries - 1)); time.sleep(300); continue
            if e.code == 4: print("等待逾時：以最新完整交易日重建，下次排程會補上今天。"); break
            raise
    build.cmd_select()
    if skip_ta: print("略過 ToAlpha")
    else: toalpha_fetch.run()
    build.cmd_build()
    try:                                  # 起漲偵測／輪動／工具箱：失敗不影響主頁
        import extras; extras.main()
    except Exception as e:
        import traceback; traceback.print_exc(); print("extras 失敗（主頁不受影響）：", repr(e))
    return 0

if __name__ == "__main__":
    sys.exit(main())
