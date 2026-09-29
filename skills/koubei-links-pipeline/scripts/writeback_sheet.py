# -*- coding: utf-8 -*-
"""通用写回腾讯文档表格：批量写值 + 标色 + 设链接。
输入：任务 JSON 文件，格式见下。用法：python writeback_sheet.py <task.json>

task.json 示例：
{
  "file_id": "DRmdKeHRvSEZIWVZG",
  "sheet_id": "000001",
  "values": [                                   // 批量写值（set_range_value）
    {"row": 0, "col": 11, "value_type": "STRING", "string_value": "图片要求"},
    {"row": 1, "col": 7, "value_type": "STRING", "string_value": "3.80"}
  ],
  "styles": [                                   // 标色（set_cell_style，ARGB）
    {"row": 5, "col": 11, "font_color": "FF0000FF", "bg_color": "FFDEEBF7", "bold": true}
  ],
  "links": [                                    // 设超链接（set_link，可选）
    {"row": 1, "col": 4, "url": "https://..."}
  ]
}

关键：set_range_value 用 values 数组（非 start_row 参数）；
     set_cell_style 用 font_color/bg_color（非 textColor/fill）；
     call_tool 返回 tuple (response_dict, _)，取 [0]。
"""
import sys, json, glob, os

# 自动探测 tencent-docs 插件目录（版本号随插件升级变化，用通配符匹配）
# 用户名不固定（本机为中文用户名），用 ~ 展开而非硬编码
_td_candidates = glob.glob(os.path.expanduser(
    r"~\.workbuddy\plugins\cache\workbuddy-builtin\tencent-docs-plugin\*\skills\tencent-docs"))
if not _td_candidates:
    raise SystemExit("未找到 tencent-docs 插件目录，请确认腾讯文档连接器已安装")
# 多版本时取版本号最大者
_td_candidates.sort()
sys.path.insert(0, _td_candidates[-1])
from tencentdocs import call_tool

def call_safe(service, method, params):
    r = call_tool(service, method, params)
    return r[0] if isinstance(r, tuple) else r

def main():
    task = json.load(open(sys.argv[1], encoding="utf-8"))
    file_id = task["file_id"]
    sheet_id = task["sheet_id"]

    # 1) 写值（分批 ≤15 条）
    values = task.get("values", [])
    print(f"=== 写值 {len(values)} 条 ===")
    for i in range(0, len(values), 15):
        batch = values[i:i + 15]
        r = call_safe("sheet-mcp", "set_range_value", {
            "file_id": file_id, "sheet_id": sheet_id, "values": batch,
        })
        err = r.get("error")
        print(f"  批次{i // 15}: {'OK' if not err else 'ERR ' + str(err.get('message',''))[:120]}")

    # 2) 标色
    styles = task.get("styles", [])
    print(f"=== 标色 {len(styles)} 条 ===")
    for s in styles:
        r = call_safe("sheet-mcp", "set_cell_style", {
            "file_id": file_id, "sheet_id": sheet_id,
            "start_row": s["row"], "start_col": s["col"],
            "end_row": s["row"], "end_col": s["col"],
            "font_color": s.get("font_color", ""),
            "bg_color": s.get("bg_color", ""),
            "bold": s.get("bold", False),
        })
        err = r.get("error")
        print(f"  ({s['row']},{s['col']}): {'OK' if not err else 'ERR ' + str(err.get('message',''))[:120]}")

    # 3) 设链接
    links = task.get("links", [])
    print(f"=== 设链接 {len(links)} 条 ===")
    for lk in links:
        r = call_safe("sheet-mcp", "set_link", {
            "file_id": file_id, "sheet_id": sheet_id,
            "row": lk["row"], "col": lk["col"], "url": lk["url"],
        })
        err = r.get("error")
        print(f"  ({lk['row']},{lk['col']}): {'OK' if not err else 'ERR ' + str(err.get('message',''))[:120]}")

    print("\n完成")

if __name__ == "__main__":
    main()
