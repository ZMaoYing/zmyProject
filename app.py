# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash
from db import get_connection, init_db

app = Flask(__name__)
app.secret_key = "student_management_secret_key"


@app.before_first_request
def before_first_request():
    """首次请求前初始化数据库"""
    init_db()


# ==================== 首页 ====================
@app.route("/")
def index():
    return redirect(url_for("student_list"))


# ==================== 查询（列表 + 搜索 + 分页） ====================
@app.route("/students")
def student_list():
    keyword = request.args.get("keyword", "").strip()
    page = request.args.get("page", 1, type=int)          # 当前页码
    per_page = request.args.get("per_page", 20, type=int)  # 每页条数
    per_page = min(per_page, 100)  # 限制最大100条/页

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询总数
            if keyword:
                count_sql = """SELECT COUNT(*) as total FROM students 
                               WHERE is_deleted=0 AND (name LIKE %s OR student_no LIKE %s OR phone LIKE %s)"""
                like_kw = "%{}%".format(keyword)
                cursor.execute(count_sql, (like_kw, like_kw, like_kw))
            else:
                count_sql = "SELECT COUNT(*) as total FROM students WHERE is_deleted=0"
                cursor.execute(count_sql)
            total = cursor.fetchone()["total"]

            # 计算分页
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            page = max(1, min(page, total_pages))  # 限制页码范围
            offset = (page - 1) * per_page

            # 查询当前页数据
            if keyword:
                sql = """SELECT * FROM students 
                         WHERE is_deleted=0 AND (name LIKE %s OR student_no LIKE %s OR phone LIKE %s) 
                         ORDER BY id DESC LIMIT %s OFFSET %s"""
                cursor.execute(sql, (like_kw, like_kw, like_kw, per_page, offset))
            else:
                sql = "SELECT * FROM students WHERE is_deleted=0 ORDER BY id DESC LIMIT %s OFFSET %s"
                cursor.execute(sql, (per_page, offset))
            students = cursor.fetchall()
    finally:
        conn.close()

    return render_template("students.html",
                           students=students,
                           keyword=keyword,
                           page=page,
                           per_page=per_page,
                           total=total,
                           total_pages=total_pages)


# ==================== 新增 ====================
@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        student_no = request.form.get("student_no", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not all([name, age, gender, student_no]):
            flash("请填写所有必填字段（姓名、年龄、性别、学号）", "error")
            return render_template("add_student.html")

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO students (name, age, gender, student_no, phone, address) 
                         VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (name, int(age), gender, student_no, phone, address or None))
            conn.commit()
            flash("学生添加成功！", "success")
            return redirect(url_for("student_list"))
        except Exception as e:
            conn.rollback()
            flash("添加失败：学号可能已存在 - {}".format(str(e)), "error")
        finally:
            conn.close()

    return render_template("add_student.html")


# ==================== 修改 ====================
@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    conn = get_connection()
    try:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            age = request.form.get("age", "").strip()
            gender = request.form.get("gender", "").strip()
            student_no = request.form.get("student_no", "").strip()
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()

            if not all([name, age, gender, student_no]):
                flash("请填写所有必填字段（姓名、年龄、性别、学号）", "error")
                return render_template("edit_student.html", student_id=student_id)

            with conn.cursor() as cursor:
                sql = """UPDATE students SET name=%s, age=%s, gender=%s, 
                         student_no=%s, phone=%s, address=%s WHERE id=%s"""
                cursor.execute(sql, (name, int(age), gender, student_no, phone, address or None, student_id))
            conn.commit()
            flash("学生信息更新成功！", "success")
            return redirect(url_for("student_list"))
        else:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
                student = cursor.fetchone()
            if not student:
                flash("学生不存在", "error")
                return redirect(url_for("student_list"))
            return render_template("edit_student.html", student=student)
    except Exception as e:
        conn.rollback()
        flash("更新失败：{}".format(str(e)), "error")
        return redirect(url_for("student_list"))
    finally:
        conn.close()


# ==================== 软删除 ====================
@app.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 软删除：标记is_deleted=1，记录删除时间
            cursor.execute(
                "UPDATE students SET is_deleted=1, deleted_at=NOW() WHERE id=%s AND is_deleted=0",
                (student_id,)
            )
        conn.commit()
        flash("学生已移至回收站！", "success")
    except Exception as e:
        conn.rollback()
        flash("删除失败：{}".format(str(e)), "error")
    finally:
        conn.close()
    return redirect(url_for("student_list"))


# ==================== 回收站 ====================
@app.route("/students/recycle")
def recycle_bin():
    """查看回收站中的学生"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM students WHERE is_deleted=1 ORDER BY deleted_at DESC")
            students = cursor.fetchall()
    finally:
        conn.close()
    return render_template("recycle.html", students=students)


# ==================== 恢复学生 ====================
@app.route("/students/restore/<int:student_id>", methods=["POST"])
def restore_student(student_id):
    """从回收站恢复学生"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE students SET is_deleted=0, deleted_at=NULL WHERE id=%s AND is_deleted=1",
                (student_id,)
            )
        conn.commit()
        flash("学生已恢复！", "success")
    except Exception as e:
        conn.rollback()
        flash("恢复失败：{}".format(str(e)), "error")
    finally:
        conn.close()
    return redirect(url_for("recycle_bin"))


# ==================== 永久删除 ====================
@app.route("/students/permanent_delete/<int:student_id>", methods=["POST"])
def permanent_delete(student_id):
    """永久删除学生（不可恢复）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM students WHERE id=%s AND is_deleted=1", (student_id,))
        conn.commit()
        flash("学生已永久删除！", "success")
    except Exception as e:
        conn.rollback()
        flash("永久删除失败：{}".format(str(e)), "error")
    finally:
        conn.close()
    return redirect(url_for("recycle_bin"))


# ==================== 清空回收站 ====================
@app.route("/students/clear_recycle", methods=["POST"])
def clear_recycle():
    """清空回收站"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM students WHERE is_deleted=1")
        conn.commit()
        flash("回收站已清空！", "success")
    except Exception as e:
        conn.rollback()
        flash("清空失败：{}".format(str(e)), "error")
    finally:
        conn.close()
    return redirect(url_for("recycle_bin"))


if __name__ == "__main__":
    print("=" * 50)
    print("  学生管理系统启动成功！")
    print("  访问地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)
