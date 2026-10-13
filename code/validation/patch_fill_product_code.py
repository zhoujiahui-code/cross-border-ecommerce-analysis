import pymysql

# 准备匹配数据：商品编码 + 唯一匹配条件
update_data = df_clean[["商品编码", "订单号", "商品描述", "购买数量"]].values.tolist()

try:
    conn = pymysql.connect(**MYSQL_CFG)
    cursor = conn.cursor()

    # 1. 创建临时表存储匹配数据
    cursor.execute("""
        CREATE TEMPORARY TABLE temp_product_code (
            product_code VARCHAR(32),
            order_id VARCHAR(64),
            product_name VARCHAR(255),
            quantity INT
        )
    """)

    # 2. 批量插入临时表（仅插入操作，速度极快）
    insert_sql = "INSERT INTO temp_product_code VALUES (%s, %s, %s, %s)"
    cursor.executemany(insert_sql, update_data)
    print(f"临时表插入完成，共 {len(update_data)} 行")

    # 3. 一次关联更新全表（核心优化，仅执行一次UPDATE）
    cursor.execute("""
        UPDATE order_detail od
        JOIN temp_product_code t 
            ON od.order_id = t.order_id 
            AND od.product_name = t.product_name 
            AND od.quantity = t.quantity
        SET od.product_code = t.product_code
    """)
    conn.commit()
    print(f"✅ 商品编码补写完成，共更新 {cursor.rowcount} 行")

except Exception as e:
    conn.rollback()
    print(f"❌ 补写失败：{e}")

finally:
    cursor.close()
    conn.close()
