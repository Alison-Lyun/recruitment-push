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

def merge_application(summary, detail):
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(detail, dict):
        detail = {}
    merged = dict(summary)
    merged.update(detail)
    return merged

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

# ── 5. 提取飞书投递阶段 ─────────────────────────────────────
STAGE_FIELD_NAMES = (
    "stage",
    "active_stage",
    "current_stage",
    "current_process_stage",
    "process_stage",
    "application_stage",
    "talent_stage",
)

def pick_name(value):
    if isinstance(value, dict):
        for key in ("name", "zh_name", "title", "stage_name"):
            if value.get(key):
                return str(value[key])
    elif isinstance(value, str):
        return value
    return ""

def find_stage_name(value):
    if isinstance(value, dict):
        direct = pick_name(value)
        if direct:
            return direct
        for key in STAGE_FIELD_NAMES:
            if key in value:
                found = find_stage_name(value[key])
                if found:
                    return found
        for key, child in value.items():
            if "stage" in key or "process" in key:
                found = find_stage_name(child)
                if found:
                    return found
    elif isinstance(value, list):
        for item in value:
            found = find_stage_name(item)
            if found:
                return found
    return ""

def get_stage_name(app):
    for key in STAGE_FIELD_NAMES:
        stage = find_stage_name(app.get(key))
        if stage:
            return stage
    return "投递"

def map_status(stage_name: str) -> str:
    text = (stage_name or "").lower()
    if "offer" in text or "录用" in text or "待入职" in text:
        return "offer"
    if "面" in text or "邀约" in text or "沟通" in text:
        return "interview"
    if "评估" in text or "筛" in text or "笔试" in text:
        return "applied"
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
            else:
                app = app_item
                app_id = app.get("id", "")
                if app_id:
                    app = merge_application(app, get_application(token, app_id))
            if not isinstance(app, dict):
                app = {}

            talent_info = app.get("talent")
            talent_id = app.get("talent_id", "")
            if not talent_id and isinstance(talent_info, dict):
                talent_id = talent_info.get("id", "")
            stage = get_stage_name(app)
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
                "stage": stage,
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
