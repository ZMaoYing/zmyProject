# -*- coding: utf-8 -*-
"""
学生查询性能测试脚本
测试不同数据量下的查询性能，找出性能拐点
"""
import time
import random
import string
import pymysql
import json
import sys
import os

# 将当前目录加入path，以便导入db模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import init_db

# ==================== 配置 ====================
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "student_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

# 每个数据量级别重复测试次数（取平均值）
REPEAT_TIMES = 10

# 数据量梯度（逐步递增）
DATA_SCALES = [100, 500, 1000, 5000, 10000, 50000, 100000]


# ==================== 工具函数 ====================
def get_connection():
    return pymysql.connect(**DB_CONFIG)


def random_string(length=6):
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def random_phone():
    return '1' + ''.join(random.choices(string.digits, k=10))


# ==================== 数据准备 ====================
def get_current_count():
    """获取当前数据量"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM students")
            return cursor.fetchone()["cnt"]
    finally:
        conn.close()


def batch_insert(target_count):
    """批量插入测试数据到指定数量"""
    current = get_current_count()
    if current >= target_count:
        print("  当前数据量 {} 已 >= 目标 {}，跳过插入".format(current, target_count))
        return

    need = target_count - current
    print("  需要插入 {} 条数据（当前 {}，目标 {}）...".format(need, current, target_count))

    conn = get_connection()
    batch_size = 500
    inserted = 0

    try:
        with conn.cursor() as cursor:
            while inserted < need:
                batch = []
                for _ in range(min(batch_size, need - inserted)):
                    name = random_string(8)
                    age = random.randint(16, 35)
                    gender = random.choice(["男", "女"])
                    student_no = "STU{}{}".format(
                        time.strftime("%Y%m%d"),
                        ''.join(random.choices(string.digits, k=8))
                    )
                    phone = random_phone()
                    address = "测试地址{}".format(random_string(10))
                    batch.append((name, age, gender, student_no, phone, address))

                sql = """INSERT INTO students (name, age, gender, student_no, phone, address) 
                         VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.executemany(sql, batch)
                conn.commit()
                inserted += len(batch)
                print("    已插入 {}/{} 条".format(inserted, need))
    except pymysql.err.IntegrityError:
        conn.rollback()
        # 学号重复时逐条插入
        print("  学号有重复，改为逐条插入...")
        with conn.cursor() as cursor:
            while inserted < need:
                name = random_string(8)
                age = random.randint(16, 35)
                gender = random.choice(["男", "女"])
                student_no = "STU{}{}".format(
                    time.strftime("%Y%m%d%H%M%S"),
                    ''.join(random.choices(string.digits, k=10))
                )
                phone = random_phone()
                address = "测试地址{}".format(random_string(10))
                try:
                    cursor.execute(sql, (name, age, gender, student_no, phone, address))
                    conn.commit()
                    inserted += 1
                except pymysql.err.IntegrityError:
                    conn.rollback()
                    continue
                if inserted % 1000 == 0:
                    print("    已插入 {}/{} 条".format(inserted, need))
    finally:
        conn.close()


def clean_test_data():
    """清空测试数据"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM students")
        conn.commit()
        print("  已清空所有数据")
    finally:
        conn.close()


# ==================== 性能测试 ====================
def measure_query(sql, params=None, repeat=REPEAT_TIMES):
    """测量SQL执行时间（秒），取平均值"""
    conn = get_connection()
    times = []
    try:
        for _ in range(repeat):
            with conn.cursor() as cursor:
                start = time.perf_counter()
                cursor.execute(sql, params)
                cursor.fetchall()
                end = time.perf_counter()
                times.append(end - start)
    finally:
        conn.close()

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    return {
        "avg": round(avg_time * 1000, 3),   # 转为毫秒
        "min": round(min_time * 1000, 3),
        "max": round(max_time * 1000, 3),
    }


def test_full_table_query():
    """测试1：全表查询（SELECT * WHERE is_deleted=0）"""
    sql = "SELECT * FROM students WHERE is_deleted=0 ORDER BY id DESC"
    return measure_query(sql)


def test_keyword_search(keyword):
    """测试2：模糊搜索（LIKE查询）"""
    sql = """SELECT * FROM students 
             WHERE is_deleted=0 AND (name LIKE %s OR student_no LIKE %s OR phone LIKE %s) 
             ORDER BY id DESC"""
    like_kw = "%{}%".format(keyword)
    return measure_query(sql, (like_kw, like_kw, like_kw))


def test_single_query(student_id):
    """测试3：单条查询（按ID）"""
    sql = "SELECT * FROM students WHERE id = %s AND is_deleted=0"
    return measure_query(sql, (student_id,))


def test_count_query():
    """测试4：COUNT统计"""
    sql = "SELECT COUNT(*) FROM students WHERE is_deleted=0"
    return measure_query(sql)


def get_random_student_id():
    """获取一个随机的学生ID"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM students WHERE is_deleted=0 ORDER BY RAND() LIMIT 1")
            row = cursor.fetchone()
            return row["id"] if row else 1
    finally:
        conn.close()


def get_random_keyword():
    """获取一个随机搜索关键词"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM students WHERE is_deleted=0 ORDER BY RAND() LIMIT 1")
            row = cursor.fetchone()
            if row and row["name"]:
                return row["name"][:2]  # 取前2个字符
            return "test"
    finally:
        conn.close()


# ==================== 拐点分析 ====================
def find_inflection_point(results, key="avg"):
    """
    找出性能拐点
    拐点定义：当数据量增长N倍时，响应时间增长超过2N倍的那个点
    """
    if len(results) < 3:
        return None, "数据点太少，无法分析"

    inflection = None
    max_ratio = 0

    for i in range(1, len(results)):
        data_ratio = results[i]["count"] / results[i - 1]["count"]
        time_ratio = results[i][key] / results[i - 1][key] if results[i - 1][key] > 0 else 1

        if time_ratio > max_ratio:
            max_ratio = time_ratio
            inflection = {
                "from_count": results[i - 1]["count"],
                "to_count": results[i]["count"],
                "from_time": results[i - 1][key],
                "to_time": results[i][key],
                "data_ratio": round(data_ratio, 1),
                "time_ratio": round(time_ratio, 1),
            }

    return inflection, max_ratio


# ==================== 主流程 ====================
def run_performance_test():
    """运行完整性能测试"""
    print("=" * 70)
    print("  学生查询性能测试")
    print("  测试时间: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    print("  每个级别重复 {} 次取平均值".format(REPEAT_TIMES))
    print("=" * 70)

    all_results = []

    for scale in DATA_SCALES:
        print("\n【数据量: {}】".format(scale))

        # 准备数据
        batch_insert(scale)
        actual_count = get_current_count()
        print("  实际数据量: {}".format(actual_count))

        # 获取测试参数
        random_id = get_random_student_id()
        random_kw = get_random_keyword()

        # 执行4种查询测试
        t1 = test_full_table_query()
        t2 = test_keyword_search(random_kw)
        t3 = test_single_query(random_id)
        t4 = test_count_query()

        result = {
            "count": actual_count,
            "full_query": t1,
            "keyword_search": t2,
            "single_query": t3,
            "count_query": t4,
        }
        all_results.append(result)

        # 打印当前结果
        print("  全表查询:   avg={avg}ms  min={min}ms  max={max}ms".format(**t1))
        print("  模糊搜索:   avg={avg}ms  min={min}ms  max={max}ms  (关键词: '{}')".format(
            random_kw, **t2))
        print("  单条查询:   avg={avg}ms  min={min}ms  max={max}ms  (id={})".format(
            random_id, **t3))
        print("  COUNT统计:  avg={avg}ms  min={min}ms  max={max}ms".format(**t4))

    # ==================== 拐点分析 ====================
    print("\n" + "=" * 70)
    print("  性能拐点分析")
    print("=" * 70)

    test_names = [
        ("全表查询", "full_query"),
        ("模糊搜索", "keyword_search"),
        ("单条查询", "single_query"),
        ("COUNT统计", "count_query"),
    ]

    for name, key in test_names:
        print("\n--- {} ---".format(name))
        # 构造分析序列
        seq = [{"count": r["count"], "avg": r[key]["avg"]} for r in all_results]
        inflection, ratio = find_inflection_point(seq)

        if inflection:
            print("  拐点: 数据量 {} -> {}".format(inflection["from_count"], inflection["to_count"]))
            print("  数据量增长: {}倍".format(inflection["data_ratio"]))
            print("  响应时间增长: {}倍 ({}ms -> {}ms)".format(
                inflection["time_ratio"], inflection["from_time"], inflection["to_time"]))
            if inflection["time_ratio"] > inflection["data_ratio"] * 1.5:
                print("  ⚠️  性能劣化明显！响应时间增长远超数据量增长")
        else:
            print("  未检测到明显拐点")

        # 打印趋势
        print("  趋势: ", end="")
        for r in seq:
            bar_len = max(1, int(r["avg"] / max(s["avg"] for s in seq) * 30))
            print("\n    {:>8}条 |{}| {}ms".format(
                r["count"], "█" * bar_len, r["avg"]), end="")
        print()

    # ==================== 汇总报告 ====================
    print("\n" + "=" * 70)
    print("  测试汇总")
    print("=" * 70)
    print("{:>10} | {:>12} | {:>12} | {:>12} | {:>12}".format(
        "数据量", "全表查询", "模糊搜索", "单条查询", "COUNT"))
    print("-" * 70)
    for r in all_results:
        print("{:>8}条 | {:>9}ms | {:>9}ms | {:>9}ms | {:>9}ms".format(
            r["count"],
            r["full_query"]["avg"],
            r["keyword_search"]["avg"],
            r["single_query"]["avg"],
            r["count_query"]["avg"],
        ))

    # 保存JSON结果
    report_file = "performance_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("\n详细报告已保存到: {}".format(report_file))

    return all_results


if __name__ == "__main__":
    print("\n提示: 测试会向数据库插入大量数据，测试完成后可手动清理\n")

    # 初始化数据库（确保表结构最新，包含is_deleted等字段）
    print("正在初始化数据库...")
    init_db()
    print("数据库初始化完成\n")

    choice = input("是否清空现有数据重新开始？(y/n): ").strip().lower()
    if choice == "y":
        clean_test_data()

    run_performance_test()
