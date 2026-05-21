import os
import json
import requests
from datetime import datetime, timezone

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]
JOB_NAME = "用户服务运营负责人"
JOB_ID = "7639671785348614438"

# ── 1. 获取 tenant_access_token ──────────────────────────────
def get_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    return r.json()["tenant_access_token"]

# ── 2. 获取所有职位，找到目标职位 ID ─────────────────────────
def get_job_id(token):
    if JOB_ID:
        print(f"使用固定职位 ID: {JOB_ID}")
        return JOB_ID

    headers = {"Authorization": f"Bearer {token}"}
    url = "https://open.feishu.cn/open-apis/hire/v1/jobs"
    params = {"page_size": 100}
    r = requests.get(url, headers=headers, params=params)
    jobs = r.json().get("data", {}).get("items", [])
    print("飞书返回的职位列表：")
    for job in jobs:
        print("-", job.get("title") or job.get("name") or job)
    for job in jobs:
        if JOB_NAME in (job.get("title") or job.get("name") or ""):
            return job["id"]
    return None

# ── 3. 获取该职位下所有投递（候选人）────────────────────────
def get_applications(token, job_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://open.feishu.cn/open-apis/hire/v1/applications"
    items = []
    page_token = ""
    while True:
        params = {"page_size": 100, "job_id": job_id, "active_status": 3}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(url, headers=headers, params=params)
        data = r.json().get("data", {})
        if not isinstance(data, dict):
            return items
        items.extend(data.get("items", []))
        page_token = data.get("page_token", "")
        if not data.get("has_more") or not page_token:
            return items

def get_application(token, application_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://open.feishu.cn/open-apis/hire/v1/applications/{application_id}"
    r = requests.get(url, headers=headers)
    data = r.json().get("data", {})
    if not isinstance(data, dict):
        return {}
    application = data.get("application")
    return application if isinstance(application, dict) else data

# ── 4. 获取候选人详情（姓名）────────────────────────────────
def get_talent(token, talent_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://open.feishu.cn/open-apis/hire/v1/talents/{talent_id}"
    r = requests.get(url, headers=headers)
    data = r.json().get("data", {})
    if not isinstance(data, dict):
        return {}
    talent = data.get("talent")
    return talent if isinstance(talent, dict) else data

# ── 5. 将飞书投递阶段映射到看板状态 ─────────────────────────
STAGE_MAP = {
    "投递": "wishlist",
    "简历筛选": "applied",
    "笔试": "applied",
    "初面": "interview",
    "复面": "interview",
    "终面": "interview",
    "offer": "offer",
    "Offer": "offer",
}

def map_status(stage_name: str) -> str:
    for key, val in STAGE_MAP.items():
        if key.lower() in stage_name.lower():
            return val
    return "wishlist"

def pick_name_from_talent(talent, fallback):
    if not isinstance(talent, dict):
        return fallback
    basic_info = talent.get("basic_info") or {}
    if isinstance(basic_info, dict) and basic_info.get("name"):
        return basic_info["name"]
    return talent.get("name") or fallback

def normalize_date(value):
    if value in (None, ""):
        return ""
    text = str(value)
    if text.isdigit():
        ts = int(text)
        if ts > 10_000_000_000:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    return text[:10]

# ── 主流程 ───────────────────────────────────────────────────
def main():
    print("🔑 获取飞书 token...")
    token = get_token()

    print(f"🔍 查找职位「{JOB_NAME}」...")
    job_id = get_job_id(token)
    if not job_id:
        print(f"⚠️  未找到职位「{JOB_NAME}」，使用空数据")
        candidates = []
    else:
        print(f"✅ 找到职位 ID: {job_id}")
        print("📋 获取候选人列表...")
        apps = get_applications(token, job_id)
        print(f"   共 {len(apps)} 位候选人")

        candidates = []
        for i, app_item in enumerate(apps):
            if isinstance(app_item, str):
                app_id = app_item
                app = get_application(token, app_id)
                if not isinstance(app, dict):
                    app = {}
            else:
                app = app_item
                app_id = app.get("id", "")

            talent_info = app.get("talent")
            talent_id = app.get("talent_id", "")
            if not talent_id and isinstance(talent_info, dict):
                talent_id = talent_info.get("id", "")
            stage_info = app.get("stage") or app.get("active_stage") or {}
            if isinstance(stage_info, dict):
                stage = stage_info.get("name", "投递")
            elif isinstance(stage_info, str):
                stage = stage_info
            else:
                stage = "投递"
            create_time = app.get("create_time") or app.get("created_time") or app.get("delivery_time") or ""
            date = normalize_date(create_time)

            # 获取姓名
            name = f"候选人{i+1}"
            name = pick_name_from_talent(talent_info, name)
            if talent_id:
                talent = get_talent(token, talent_id)
                name = pick_name_from_talent(talent, name)

            candidates.append({
                "id": i + 1,
                "name": name,
                "source": (app.get("resume_source") or {}).get("name", "飞书招聘") if isinstance(app.get("resume_source"), dict) else "飞书招聘",
                "status": map_status(stage),
                "date": date,
                "note": f"当前阶段：{stage}",
                "feishu_app_id": app_id,
            })

    # ── 写入 data.json ────────────────────────────────────────
    output = {"candidates": candidates, "job": JOB_NAME}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ data.json 已写入，共 {len(candidates)} 条候选人记录")

if __name__ == "__main__":
    main()
