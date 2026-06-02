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
   # 開始精準巡邏
    for c_id in range(start_id, end_id + 1):
        try:
            checkin_url = f"https://irs.zuvio.com.tw/student5/irs/rollcall/{c_id}"
            checkin_res = session.get(checkin_url)
            
            # 【新防線 1】：如果這根本不是你的課，直接跳過
            if any(no_auth in checkin_res.text for no_auth in ["尚未選修", "不屬於", "請先加入", "權限不足", "錯誤", "無此課程"]):
                continue
                
            # 【新防線 2】：只有網頁明確顯示「簽到」相關控制項，且「不在簽到時間」這幾個字沒出現時才算數
            if "目前不在簽到時間" not in checkin_res.text and "登入" not in checkin_res.text:
                # 必須包含真正的簽到按鈕或輸入框特徵
                if any(k in checkin_res.text for k in ["我要簽到", "輸入簽到碼", "手動簽到", "GPS簽到", "點名開始"]):
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
