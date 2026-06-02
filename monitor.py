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
        "active_checkins": []
    }
    
    # 台北時區設定
    tz = timezone(timedelta(hours=8))
    status_report["time"] = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    session = requests.Session()
    login_url = "https://irs.zuvio.com.tw/irs/submitLogin"
    login_data = {'email': ZUVIO_EMAIL, 'password': ZUVIO_PASSWORD}
    
    try:
        res = session.post(login_url, data=login_data)
        if "登入失敗" in res.text:
            status_report["status"] = "danger"
            status_report["message"] = "❌ Zuvio 登入失敗，請檢查 GitHub 密鑰設定。"
            return status_report
    except:
        status_report["status"] = "danger"
        status_report["message"] = "❌ 連線到 Zuvio 伺服器異常。"
        return status_report

    try:
        course_res = session.get("https://irs.zuvio.com.tw/course/list")
        course_ids = list(set(re.findall(r'https://irs.zuvio.com.tw/student/course/([0-9]+)', course_res.text)))
        status_report["courses_checked"] = len(course_ids)
    except:
        status_report["status"] = "warning"
        status_report["message"] = "⚠️ 登入成功，但無法獲取課程列表。"
        return status_report

    for c_id in course_ids:
        try:
            checkin_url = f"https://irs.zuvio.com.tw/student/course/{c_id}/checkin"
            checkin_res = session.get(checkin_url)
            
            if "目前不在簽到時間" not in checkin_res.text:
                if any(k in checkin_res.text for k in ["簽到", "點名", "checkin-methods", "method-item"]):
                    status_report["active_checkins"].append({
                        "id": c_id,
                        "url": checkin_url
                    })
        except:
            continue

    if status_report["active_checkins"]:
        status_report["status"] = "danger"
        status_report["message"] = f"🚨 警報！發現有 {len(status_report['active_checkins'])} 門課程正在點名！"
        
    return status_report

@app.route('/')
def home():
    data = check_zuvio_status()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    # 綁定 0.0.0.0 才能讓外部網路連進網頁
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
