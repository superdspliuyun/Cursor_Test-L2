"""
种子数据脚本
在空 SQLite 中建演示用业务表 + 示例数据
运行：python scripts/seed_db.py

数据范围：2024-09 ~ 2025-02 共 6 个月，覆盖完整的销售"趋势"
"""
import os
import sys
import sqlite3

# 允许从 backend/ 根目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings


def main():
    s = get_settings()
    db_path = s.DATABASE_URL.split("///")[-1]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 检查是否已有业务表
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    existing = [r[0] for r in cur.fetchall()]
    if existing:
        print(f"[seed] 数据库已有表 {existing}，跳过 seed")
        conn.close()
        return

    print("[seed] 初始化演示数据 (6 个月销售)...")

    # === users: 12 个 ===
    users = [
        (1,  '张三', '北京', '2024-01-15', 28),
        (2,  '李四', '上海', '2024-03-22', 35),
        (3,  '王五', '北京', '2024-06-10', 42),
        (4,  '赵六', '深圳', '2024-08-05', 30),
        (5,  '钱七', '广州', '2024-11-20', 25),
        (6,  '孙八', '上海', '2024-09-12', 31),
        (7,  '周九', '深圳', '2024-10-08', 29),
        (8,  '吴十', '杭州', '2024-10-25', 38),
        (9,  '郑十一', '北京', '2024-12-01', 26),
        (10, '冯十二', '成都', '2025-01-10', 33),
        (11, '陈十三', '上海', '2025-01-22', 40),
        (12, '褚十四', '广州', '2025-02-14', 24),
    ]

    # === products: 10 个（覆盖 5 个类别） ===
    products = [
        (1,  'iPhone 15',       '电子产品', 7999.0, 100),
        (2,  '华为 Mate60',     '电子产品', 6999.0, 80),
        (3,  '小米 14',         '电子产品', 3999.0, 120),
        (4,  'Nike 跑鞋',       '服装',     899.0,  200),
        (5,  '优衣库 T 恤',     '服装',     199.0,  500),
        (6,  '美的电饭煲',      '家居',     399.0,  150),
        (7,  '小米空气净化器',  '家居',     1299.0, 90),
        (8,  'SK-II 神仙水',    '美妆',     1899.0, 60),
        (9,  '雅诗兰黛小棕瓶',  '美妆',     1299.0, 70),
        (10, '农夫山泉 24 瓶',  '食品',     39.9,   1000),
    ]

    # === orders: 6 个月 × 多用户 × 多产品（按月分布） ===
    # 每月 8~12 单，覆盖 5 个类别；amount 复用 products.price × quantity
    orders = []
    oid = 1
    monthly_orders = [
        # (month_label, [(user_id, product_id, quantity, status), ...])
        ("2024-09", [
            (1, 1, 1, 'completed'), (2, 4, 2, 'completed'), (3, 8, 1, 'completed'),
            (4, 6, 1, 'completed'), (5, 5, 3, 'completed'), (6, 10, 5, 'completed'),
            (7, 1, 1, 'completed'), (8, 3, 1, 'completed'),
        ]),
        ("2024-10", [
            (1, 2, 1, 'completed'), (2, 7, 1, 'completed'), (3, 4, 2, 'completed'),
            (6, 8, 2, 'completed'), (7, 1, 1, 'completed'), (8, 5, 4, 'completed'),
            (9, 10, 6, 'completed'), (10, 3, 1, 'completed'),
        ]),
        ("2024-11", [
            (1, 1, 1, 'completed'), (2, 4, 3, 'completed'), (3, 8, 1, 'completed'),
            (4, 9, 1, 'completed'), (5, 2, 1, 'completed'), (6, 7, 1, 'completed'),
            (7, 3, 1, 'completed'), (8, 1, 1, 'completed'), (9, 5, 2, 'completed'),
            (10, 10, 4, 'completed'),
        ]),
        ("2024-12", [
            (1, 1, 1, 'completed'), (1, 3, 1, 'completed'), (2, 2, 1, 'completed'),
            (3, 1, 1, 'completed'), (3, 8, 2, 'completed'), (4, 6, 3, 'pending'),
            (5, 1, 1, 'completed'), (6, 9, 1, 'completed'), (7, 4, 2, 'completed'),
            (8, 7, 1, 'completed'), (9, 5, 3, 'completed'),
        ]),
        ("2025-01", [
            (2, 1, 1, 'completed'), (2, 4, 1, 'completed'), (3, 3, 1, 'completed'),
            (5, 1, 1, 'completed'), (7, 1, 1, 'completed'), (8, 8, 1, 'completed'),
            (9, 2, 1, 'completed'), (10, 5, 2, 'completed'), (11, 7, 1, 'completed'),
            (12, 1, 1, 'completed'),
        ]),
        ("2025-02", [
            (1, 1, 1, 'completed'), (3, 4, 2, 'completed'), (4, 3, 1, 'completed'),
            (5, 7, 1, 'completed'), (6, 1, 1, 'completed'), (7, 2, 1, 'completed'),
            (8, 8, 1, 'completed'), (9, 5, 2, 'completed'), (10, 4, 1, 'completed'),
            (11, 1, 1, 'completed'), (12, 9, 1, 'completed'),
        ]),
    ]

    for month_label, month_orders in monthly_orders:
        for (uid, pid, qty, status) in month_orders:
            # 找价格
            price = next(p[3] for p in products if p[0] == pid)
            amount = price * qty
            order_date = f"{month_label}-{((oid - 1) % 28) + 1:02d}"
            orders.append((oid, uid, pid, qty, amount, order_date, status))
            oid += 1

    cur.executescript("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        city TEXT,
        signup_date TEXT,
        age INTEGER
    );

    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        price REAL,
        stock INTEGER
    );

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        product_id INTEGER REFERENCES products(id),
        quantity INTEGER,
        amount REAL,
        order_date TEXT,
        status TEXT
    );
    """)

    cur.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", users)
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", orders)

    conn.commit()
    conn.close()
    print(f"[seed] 完成：{db_path}")
    print(f"  - users:  {len(users)}")
    print(f"  - products: {len(products)}")
    print(f"  - orders: {len(orders)} (跨 6 个月: 2024-09 ~ 2025-02)")


if __name__ == "__main__":
    main()
