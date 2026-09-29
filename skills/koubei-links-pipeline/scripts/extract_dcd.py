# -*- coding: utf-8 -*-
"""从 cdp_batch.js 落盘的 kb_<seq>.json (__NEXT_DATA__ 的 props 子树) 提取懂车帝口碑字段。
输出 data/dcd_extracted.json [{seq, acct, car, title, score, date, url, body, dims}]
用法：python extract_dcd.py
"""
import os, re, json, glob, datetime

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(WORK, "html_snapshots")
ROWS = json.load(open(os.path.join(WORK, "data", "rows.json"), encoding="utf-8"))
OUT = os.path.join(WORK, "data", "dcd_extracted.json")

DIM_MAP = [
    ("space_score", "空间"),
    ("driving_score", "驾驶感受"),
    ("power_score", "动力"),
    ("oil_consumption_score", "油耗"),
    ("appearance_score", "外观"),
    ("interiors_score", "内饰"),
    ("configuration_score", "配置"),
    ("intelligence_score", "智能化"),
    ("smart_cockpit_score", "智能座舱"),
    ("comfort_score", "舒适性"),
    ("control_score", "操控"),
    ("continuation_score", "续航"),
    ("assist_driving_score", "辅助驾驶"),
]

def norm_title(raw):
    if not raw:
        return ""
    cleaned = re.sub(r'^(?:【[^】]*】[\s]*)+', '', raw)
    first = re.split(r'[。！？\n]', cleaned)[0]
    return re.sub(r'\s+', ' ', first).strip()

def main():
    out = []
    for r in ROWS:
        seq = r["seq"]
        fp = os.path.join(SNAP, f"kb_{seq}.json")
        rec = {"seq": seq, "url": r["url"], "cid": r["cid"],
               "acct": "", "car": "", "title": "", "score": None,
               "date": None, "body": "", "dims": {}}
        if not os.path.exists(fp):
            print(f"{seq:02d} | MISSING {fp}")
            out.append(rec)
            continue
        try:
            data = json.load(open(fp, encoding="utf-8"))
            pp = data.get("props", {}).get("pageProps", {})
            ad = pp.get("articleDetail") or {}
        except Exception as e:
            print(f"{seq:02d} | PARSE FAIL {e}")
            out.append(rec)
            continue

        cv = ad.get("car_view") or {}
        # 车型：优先 relation_car_info（含具体配置名），回退 series_name + 年款
        rci = ad.get("relation_car_info") or {}
        car = ""
        if rci.get("series_name"):
            car = rci["series_name"].strip()
            if rci.get("car_name"):
                car = f"{car} {rci['car_name'].strip()}"
            elif rci.get("year"):
                car = f"{car} {rci['year']}款"
        if not car:
            series = (cv.get("series_name") or "").strip()
            year = cv.get("year_id")
            car = f"{series} {year}款" if series and year else series
        # 账号/昵称：motor_profile_info.name 为准
        acct = ""
        mpi = ad.get("motor_profile_info") or {}
        acct = (mpi.get("name") or "").strip()
        if not acct:
            ui = mpi.get("user_info") or {}
            acct = (ui.get("name") or "").strip()
        if not acct:
            for k in ("author", "user_info", "user", "media_user"):
                v = ad.get(k) or pp.get(k)
                if isinstance(v, dict):
                    acct = (v.get("name") or v.get("nickname") or v.get("user_name") or "").strip()
                    if acct:
                        break
                elif isinstance(v, str) and v.strip():
                    acct = v.strip()
                    break
        # 正文：懂车帝把全文放在 motor_title（可能含摘要首句）；content 常为空
        body = (ad.get("content") or ad.get("content_html") or "").strip()
        body = re.sub(r'<[^>]+>', '', body)
        body = body.replace("&nbsp;", " ").replace("&quot;", '"').replace("&amp;", "&")
        body = re.sub(r'\n{2,}', '\n', body).strip()
        if len(body) < 50:
            mt = (ad.get("motor_title") or "").strip()
            if mt:
                body = re.sub(r'\s*\n\s*', '\n', mt).strip()
        # 综合评分
        if cv.get("score"):
            rec["score"] = round(float(cv["score"]) / 100, 2)
        # 日期
        cpt = ad.get("content_publish_time") or ad.get("created_time")
        if cpt:
            rec["date"] = datetime.datetime.fromtimestamp(int(cpt)).strftime("%Y-%m-%d")
        # 标题：motor_title 优先，否则正文首句
        rec["title"] = norm_title(ad.get("motor_title", "")) or norm_title(body)
        # 分项
        for key, label in DIM_MAP:
            v = cv.get(key)
            if v:
                rec["dims"][label] = round(float(v) / 100, 2)

        rec["acct"] = acct
        rec["car"] = car
        rec["body"] = body
        out.append(rec)
        print(f"{seq:02d} | {car} | 评分={rec['score']} | {rec['date']} | {rec['title'][:34]}")

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n提取完成 {len(out)} 条 -> {OUT}")

if __name__ == "__main__":
    main()
