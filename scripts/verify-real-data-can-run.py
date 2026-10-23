"""在隔离副本上验证：真实数据要补到什么程度，正式答辩才能真的排定。

只读业务库 app-data/db.sqlite3，全部写操作发生在 .tmp/verify-run 的副本上。
四段对照：
  A 现状（43 教师 / 5 间仅 4 月可用的教室）
  B 补齐外院导师（导师关系完整）
  C 再补齐真实教室与 5 月可用时段
  D 在 C 基础上调小每组人数
"""
import json
import os
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:/项目/智能答辩分组编排系统")
SRC_DB = ROOT / "app-data" / "db.sqlite3"
WORK = ROOT / ".tmp" / "verify-run"
DB = WORK / "db.sqlite3"

WORK.mkdir(parents=True, exist_ok=True)
if DB.exists():
    DB.unlink()
shutil.copy2(SRC_DB, DB)

os.environ["DJANGO_DB_PATH"] = str(DB)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "defense_scheduler.settings")
os.environ.setdefault("DJANGO_DEBUG", "false")
sys.path.insert(0, str(ROOT))

import django  # noqa: E402

django.setup()

from api.models import Room, Student, Teacher  # noqa: E402
from api.services.scheduling_input import build_algorithm_input  # noqa: E402
from algorithm import generate_schedule  # noqa: E402

FORMAL_DATES = ("2026-05-06", "2026-05-15")

# Word 里正式答辩（5/6-5/12）实际用到的教室；4-xxxx 创新港，2-xxxx 兴庆。
REAL_ROOMS = {
    "4-3202": "创新港", "4-3204": "创新港", "4-3214": "创新港",
    "4-3218": "创新港", "4-3222": "创新港",
    "2-1206": "兴庆", "2-1208": "兴庆", "2-1242": "兴庆", "2-1248": "兴庆",
    "2-1257": "兴庆", "2-2213": "兴庆", "2-2247": "兴庆", "2-2248": "兴庆",
}
# 答辩日：Word 中出现的 6 个日期。
REAL_DAYS = ["2026-05-06", "2026-05-07", "2026-05-08", "2026-05-09", "2026-05-11", "2026-05-12"]


def base_rules(group_size=6):
    return {
        "defense_type": "formal", "policy_version": 2,
        "start_date": FORMAL_DATES[0], "end_date": FORMAL_DATES[1],
        "group_size": group_size, "group_min": 4, "group_max": 8,
        "expert_count": 5, "expert_min": 5,
        "avoid_weekend": False, "avoid_holiday": False, "exclude_dates": [],
        "formal_software_min": 3, "chair_title": "教授", "secretary_title": "讲师",
        "grouping": "secretary", "formal_mentor_same_session": True,
        "preserve_pre_defense_groups": False, "random_seed": 20261021,
    }


def run(label, rules):
    payload, notices = build_algorithm_input("formal", (rules["start_date"], rules["end_date"]), rules)
    try:
        result = generate_schedule(**payload, rules=rules)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[{label}] 生成抛错: {type(exc).__name__}: {exc}")
        return None
    groups = result.get("groups", [])
    # serialize_group 的字段是 time / room_id / chair_id / expert_ids，
    # 不是 API 层的 date / classroom，统计必须按算法层字段来。
    assigned = [g for g in groups if g.get("time")]
    staffed = [g for g in groups if g.get("chair_id") or g.get("expert_ids")]
    full = [g for g in groups if g.get("time") and g.get("chair_id") and len(g.get("expert_ids") or []) == 4]
    hard = Counter(c.get("type") for c in result.get("conflicts", []))
    print(f"\n{'='*64}\n[{label}]")
    print(f"  输入: 学生 {len(payload['students'])} / 教师 {len(payload['teachers'])} / 教室 {len(payload['rooms'])}")
    print(f"  组数 {len(groups)} | 已排出时间教室 {len(assigned)} | 已分配委员 {len(staffed)} | 完整5人委员 {len(full)}")
    if hard:
        print("  冲突:", dict(hard.most_common(6)))
    return {"groups": len(groups), "assigned": len(assigned), "staffed": len(staffed),
            "fullCommittee": len(full), "hard": dict(hard.most_common(8))}


results = {}

# ---- A 现状 ----
results["A_现状"] = run("A 现状：43 教师 / 教室仅 4 月可用", base_rules())

# ---- B 补齐外院导师 ----
student_rows = list(Student.objects.values_list("id", "name", "mentor_name", "mentor_id"))
existing = set(Teacher.objects.values_list("name", flat=True))
missing = sorted({(row[2] or "").strip() for row in student_rows} - existing - {""})
created = 0
for name in missing:
    Teacher.objects.create(
        name=name, college="外院（学院待确认）", title="外院导师（职称待确认）",
        is_external=True, is_software_teacher=False, expert_only=True,
        member_eligible=True, roles=["普通专家"], available_types=["正式答辩"],
    )
    created += 1
by_name = {t.name: t for t in Teacher.objects.all()}
fixed = 0
for sid, name, mentor_name, mentor_id in student_rows:
    if mentor_id is None and mentor_name and mentor_name in by_name:
        Student.objects.filter(pk=sid).update(mentor_id=by_name[mentor_name].pk)
        fixed += 1
print(f"\n[补齐] 新增外院导师 {created} 位，回填学生导师关联 {fixed} 条")
results["B_补导师"] = run("B 补齐 73 位外院导师 + 回填导师关联", base_rules())

# ---- C 补齐真实教室与 5 月时段 ----
# 源数据只有 4 月时段，正式答辩窗口因此一个候选时段都没有；这里按 Word 里的
# 真实教室和真实答辩日补 08:00-18:30 宽窗，使 09:00-12:00 / 14:00-17:00 两个标准段成立。
for name, campus in REAL_ROOMS.items():
    windows = ",".join(f"{day} 08:00-18:30" for day in REAL_DAYS)
    Room.objects.update_or_create(
        name=name, defaults={"campus": campus, "capacity": 40,
                             "available_times": windows, "remark": "按 Word 正式答辩真实教室补齐"},
    )
results["C_补教室"] = run("C 补齐 13 间真实教室 + 5 月可用时段", base_rules())

# ---- D 调小每组人数 ----
results["D_小班"] = run("D 在 C 基础上把每组调到 5 人", base_rules(group_size=5))

print("\n" + "=" * 64)
print("汇总:")
for key, value in results.items():
    print(f"  {key}: {value}")

out = WORK / "verify-summary.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n结果已写出:", out)
