# -*- coding: utf-8 -*-
import pymysql

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "student_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}


def get_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def init_db():
    """初始化数据库和数据表"""
    # 先创建数据库
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="root",
        charset="utf8mb4"
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS student_db DEFAULT CHARSET utf8mb4"
            )
        conn.commit()
    finally:
        conn.close()

    # 再创建数据表
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL COMMENT '姓名',
                    age INT NOT NULL COMMENT '年龄',
                    gender VARCHAR(10) NOT NULL COMMENT '性别',
                    student_no VARCHAR(30) NOT NULL UNIQUE COMMENT '学号',
                    phone VARCHAR(20) DEFAULT NULL COMMENT '电话',
                    address VARCHAR(200) DEFAULT NULL COMMENT '地址',
                    is_deleted TINYINT DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
                    deleted_at TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生信息表'
            """)
            # 检查并添加软删除字段（兼容已存在的表）
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA='student_db' AND TABLE_NAME='students' AND COLUMN_NAME='is_deleted'
            """)
            if cursor.fetchone()["COUNT(*)"] == 0:
                cursor.execute("ALTER TABLE students ADD COLUMN is_deleted TINYINT DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除'")
                cursor.execute("ALTER TABLE students ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间'")
        conn.commit()
    finally:
        conn.close()
