from flask import Flask, render_template
import requests
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

ZUVIO_EMAIL = os.environ.get('ZUVIO_EMAIL')
ZUVIO_PASSWORD = os.environ.get('ZUVIO_PASSWORD')

def check_zuvio_status():
    status_report = {
        "status": "success",
        "message": "🟢 新版區間盲巡完畢，目前沒有任何課程在點名。",
        "time": "",
        "courses_checked": 0,
        "active_checkins": [],
        "debug_html": "已成功鎖定 1496XXX 新版點名區間。"
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
            status_report["message"] = "❌ Zuvio 登入失敗，請檢查帳密設定。"
            return status_report
    except Exception as e:
        status_report["status"] = "danger"
        status_report["message"] = f"❌ 連線到 Zuvio 異常: {str(e)}"
        return status_report

    # 🚀 【新版精準區間】鎖定 1496033 周圍的課
    start_id = 1496000  
    end_id = 1496060    
    
    status_report["courses_checked"] = end_id - start_id + 1
    
    # 開始精準巡邏
    for c_id in range(start_id, end_id + 1):
        try:
            # 升級為你提供的新版 rollcall 路徑！
            checkin_url = f"https://irs.zuvio.com.tw/student5/irs/rollcall/{c_id}"
            checkin_res = session.get(checkin_url)
            
            # 只要沒顯示「不在簽到時間」，且網頁沒有被導回登入頁
            if "目前不在簽到時間" not in checkin_res.text and "登入" not in checkin_res.text:
                # 判斷點名關鍵字
                if any(k in checkin_res.text for k in ["簽到", "點名", "rollcall", "click", "碼", "GPS"]):
                    status_report["active_checkins"].append({
                        "id": str(c_id),
                        "url": checkin_url
                    })
        except:
            continue

    if status_report["active_checkins"]:
        status_report["status"] = "danger"
        status_report["message"] = f"🚨 警報！新版盲巡發現有 {len(status_report['active_checkins'])} 門課程抓到點名訊號！"
        
    return status_report

@app.route('/')
def home():
    data = check_zuvio_status()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
