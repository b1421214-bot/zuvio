from flask import Flask, render_template
import requests
import os
import re
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

ZUVIO_EMAIL = os.environ.get('ZUVIO_EMAIL')
ZUVIO_PASSWORD = os.environ.get('ZUVIO_PASSWORD')

def check_zuvio_status():
    status_report = {
        "status": "success",
        "message": "🟢 所有課程巡邏完畢，目前安全。",
        "time": "",
        "courses_checked": 0,
        "active_checkins": [],
        "debug_html": "" 
    }
    
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

    # 🚀 更改為直接抓取 Zuvio 後台 API 資料包
    course_ids = []
    try:
        # 直接跟後台要課程清單 JSON
        api_res = session.post("https://irs.zuvio.com.tw/student5/irs/getCourseList")
        
        # 把 API 回傳的文字倒在除錯區，讓我們知道後台吐了什麼
        status_report["debug_html"] = api_res.text[:2000]
        
        # 從 JSON/字串 中撈出所有符合 5~7 位的課程 ID
        course_ids = re.findall(r'["\']id["\']\s*:\s*["\']?([0-9]{5,7})["\']?', api_res.text)
        
        # 防呆：如果 API 欄位名稱不同，改撈純數字
        if not course_ids:
            course_ids = re.findall(r'\b([0-9]{5,7})\b', api_res.text)

        course_ids = list(set(course_ids))
        status_report["courses_checked"] = len(course_ids)
        
        if len(course_ids) == 0:
            status_report["status"] = "warning"
            status_report["message"] = "⚠️ 登入成功，但 API 沒有回傳任何課程。請檢查下方黑色除錯區。"
            return status_report
            
    except Exception as e:
        status_report["status"] = "warning"
        status_report["message"] = f"⚠️ 獲取 API 課程列表異常: {str(e)}"
        return status_report

    # 巡邏點名
    for c_id in course_ids:
        try:
            checkin_url = f"https://irs.zuvio.com.tw/student5/course/{c_id}/checkin"
            checkin_res = session.get(checkin_url)
            
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
        status_report["message"] = f"🚨 警報發布！有 {len(status_report['active_checkins'])} 門課程正在點名！"
        
    return status_report

@app.route('/')
def home():
    data = check_zuvio_status()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
