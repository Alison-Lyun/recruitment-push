import os
import json
import requests

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]
JOB_NAME = "用户服务运营负责人"

# ── 1. 获取 tenant_access_token ──────────────────────────────
def get_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    return r.json()["tenant_access_token"]

# ── 2. 获取所有职位，找到目标职位 ID ─────────────────────────
def get_job_id(token):
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
    params = {"page_size": 100, "job_id": job_id}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("data", {}).get("items", [])

# ── 4. 获取候选人详情（姓名）────────────────────────────────
def get_talent(token, talent_id):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://open.feishu.cn/open-apis/hire/v1/talents/{talent_id}"
    r = requests.get(url, headers=headers)
    return r.json().get("data", {}).get("talent", {})

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
        for i, app in enumerate(apps):
            talent_id = app.get("talent_id", "")
            stage = app.get("stage", {}).get("name", "投递")
            create_time = app.get("create_time", "")
            date = create_time[:10] if create_time else ""

            # 获取姓名
            name = f"候选人{i+1}"
            if talent_id:
                talent = get_talent(token, talent_id)
                name = talent.get("name", name)

            candidates.append({
                "id": i + 1,
                "name": name,
                "source": app.get("resume_source", {}).get("name", "飞书招聘"),
                "status": map_status(stage),
                "date": date,
                "note": f"当前阶段：{stage}",
                "feishu_app_id": app.get("id", ""),
            })

    # ── 写入 data.json ────────────────────────────────────────
    output = {"candidates": candidates, "job": JOB_NAME}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ data.json 已写入，共 {len(candidates)} 条候选人记录")

if __name__ == "__main__":
    main()
