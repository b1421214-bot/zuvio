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

    # 抓取課程列表 (精準對焦 student5 版)
    try:
        # 使用你提供的新首頁路徑
        course_res = session.get("https://irs.zuvio.com.tw/student5/irs/index")
        
        # 抓取 student5 專屬的課程 ID 結構
        course_ids = re.findall(r'/student5/course/([0-9]+)', course_res.text)
        
        # 防呆盲測其他可能結構
        if not course_ids:
            course_ids = re.findall(r'course/([0-9]{5,7})', course_res.text)
        if not course_ids:
            course_ids = re.findall(r'course_id=["\']([0-9]{5,7})["\']', course_res.text)

        course_ids = list(set(course_ids))
        status_report["courses_checked"] = len(course_ids)
        
        if len(course_ids) == 0:
            status_report["status"] = "warning"
            status_report["message"] = "⚠️ 登入成功，但 student5 頁面仍找不到課程。請確認 Zuvio 內是否有當季課程。"
            return status_report
            
    except Exception as e:
        status_report["status"] = "warning"
        status_report["message"] = f"⚠️ 獲取課程列表發生異常: {str(e)}"
        return status_report

    # 逐一檢查點名
    for c_id in course_ids:
        try:
            # 點名路徑也同步升級為 student5
            checkin_url = f"https://irs.zuvio.com.tw/student5/course/{c_id}/checkin"
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
