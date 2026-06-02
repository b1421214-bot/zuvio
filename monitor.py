from flask import Flask, render_template
import requests
import os
import re
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# 從環境變數讀取帳密
ZUVIO_EMAIL = os.environ.get('ZUVIO_EMAIL')
ZUVIO_PASSWORD = os.environ.get('ZUVIO_PASSWORD')

def check_zuvio_status():
    status_report = {
        "status": "success",
        "message": "🟢 所有課程巡邏完畢，目前安全。",
        "time": "",
        "courses_checked": 0,
        "active_checkins": []
    }
    
    # 修正時區：確保顯示台北時間
    tz = timezone(timedelta(hours=8))
    status_report["time"] = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    session = requests.Session()
    login_url = "https://irs.zuvio.com.tw/irs/submitLogin"
    login_data = {'email': ZUVIO_EMAIL, 'password': ZUVIO_PASSWORD}
    
    try:
        res = session.post(login_url, data=login_data)
        if "登入失敗" in res.text:
            status_report["status"] = "danger"
            status_report["message"] = "❌ Zuvio 登入失敗，請檢查 Render 的 Environment 帳密設定。"
            return status_report
    except Exception as e:
        status_report["status"] = "danger"
        status_report["message"] = f"❌ 連線到 Zuvio 伺服器異常: {str(e)}"
        return status_report

  # 抓取課程列表 (地毯式搜索終極版)
    try:
        course_res = session.get("https://irs.zuvio.com.tw/course/list")
        
        # 1. 收集網頁裡所有可能是課程 ID 的數字
        # 找所有包含 student/course/數字 的片段
        method1 = re.findall(r'course/([0-9]{5,8})', course_res.text)
        # 找所有 course_id="數字" 或 id="數字" 且剛好是 5~8 位數的特徵
        method2 = re.findall(r'id=["\']([0-9]{5,8})["\']', course_res.text)
        # 找網頁中所有純粹的 5 到 7 位數數字（Zuvio 課程 ID 通常是 5 或 6 位數）
        method3 = re.findall(r'\b([0-9]{5,7})\b', course_res.text)
        
        # 把所有抓到的可能 ID 混在一起
        all_possible_ids = method1 + method2 + method3
        
        # 排除掉一些固定的系統數字（例如 Zuvio 自己的客服 ID 或版本號，通常沒差，先保留）
        course_ids = list(set(all_possible_ids))
        
        # 【重要安全機制】：如果抓到太多奇怪數字，過濾掉明顯不是課程的（比如太長的數字）
        course_ids = [cid for cid in course_ids if len(cid) >= 5 and len(cid) <= 7]
        
        status_report["courses_checked"] = len(course_ids)
        
        if len(course_ids) == 0:
            status_report["status"] = "warning"
            status_report["message"] = "⚠️ 登入成功，但地毯式搜索仍找不到任何課程 ID。請確認 Zuvio 內是否有當季課程。"
            return status_report
            
    except Exception as e:
        status_report["status"] = "warning"
        status_report["message"] = f"⚠️ 獲取課程列表發生異常: {str(e)}"
        return status_report
        
    # 逐一檢查點名
    for c_id in course_ids:
        try:
            checkin_url = f"https://irs.zuvio.com.tw/student/course/{c_id}/checkin"
            checkin_res = session.get(checkin_url)
            
            # 只要沒有顯示「不在簽到時間」，且抓到相關關鍵字就觸發
            if "目前不在簽到時間" not in checkin_res.text:
                if any(k in checkin_res.text for k in ["簽到", "點名", "checkin-methods", "method-item", "碼", "GPS"]):
                    status_report["active_checkins"].append({
                        "id": c_id,
                        "url": checkin_url
                    })
        except:
            continue

    if status_report["active_checkins"]:
        status_report["status"] = "danger"
        status_report["message"] = f"🚨 警報發布！偵測到有 {len(status_report['active_checkins'])} 門課程正在點名！"
        
    return status_report

@app.route('/')
def home():
    data = check_zuvio_status()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
