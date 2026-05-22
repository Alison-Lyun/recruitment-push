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
