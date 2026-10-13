import os
import pandas as pd
import pymysql

# ===================== 配置项 =====================
FILE_PATH = "Online Retail.xlsx"
MYSQL_CFG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "***********",
    "database": "cross_border_ecommerce"
}
BATCH_SIZE = 5000

# ===================== 1. 数据读取与清洗 =====================
print("=== 1. 数据读取与基础清洗 ===")
# 读取原始数据
df_raw = pd.read_excel(FILE_PATH, engine="openpyxl")
df_raw.columns = ["订单号", "商品编码", "商品描述", "购买数量", "下单时间", "单价", "客户ID", "国家"]
df_clean = df_raw.copy()
print(f"原始数据量：{len(df_raw)} 条")

# 1.1 空值过滤：三个核心维度字段为空则删除
df_clean = df_clean.dropna(subset=["客户ID", "商品描述","商品编码","订单号","下单时间" ,"国家"])

# 1.2 过滤取消订单：订单号以C开头（Cancel）
df_clean = df_clean[~df_clean["订单号"].astype(str).str.startswith("C")]

# 1.3 过滤负向异常订单：数量≤0、单价≤0
df_clean = df_clean[(df_clean["购买数量"] > 0) & (df_clean["单价"] > 0)]

# 1.4 完全重复行去重：按核心业务字段去重，保留第一条
before_dup = len(df_clean)
df_clean = df_clean.drop_duplicates(
    subset=["订单号", "商品编码", "购买数量", "单价", "下单时间"],
    keep="first"
)
print(f"删除重复行：{before_dup - len(df_clean)} 条")

# 1.5 字段格式标准化
df_clean["客户ID"] = df_clean["客户ID"].astype(int).astype(str)
df_clean["下单时间"] = pd.to_datetime(df_clean["下单时间"])

# 1.6 衍生字段：计算单笔商品总价
df_clean["订单金额"] = df_clean["购买数量"] * df_clean["单价"]

print(f"清洗后有效明细：{len(df_clean)} 条")

# ===================== 2. IQR异常值标记 =====================
print("\n=== 2. IQR异常值标记 ===")
Q1 = df_clean["订单金额"].quantile(0.25)
Q3 = df_clean["订单金额"].quantile(0.75)
IQR = Q3 - Q1
abnormal_upper = Q3 + 1.5 * IQR
# 只标记不删除：1=高值异常，0=正常
df_clean["订单异常标记"] = df_clean["订单金额"].apply(lambda x: 1 if x > abnormal_upper else 0)
abnormal_count = df_clean["订单异常标记"].sum()
print(f"高值异常订单：{abnormal_count} 单，占比：{round(abnormal_count/len(df_clean)*100, 2)}%")

# ===================== 3. ABC商品分类 =====================
print("\n=== 3. ABC商品分类计算 ===")
# 按SKU聚合，兼容多描述场景取第一个
def get_first_mode(x):
    modes = x.mode()
    return modes.iloc[0] if not modes.empty else x.iloc[0]

product_stats = df_clean.groupby("商品编码").agg(
    商品描述=("商品描述", get_first_mode),
    total_quantity=("购买数量", "sum"),
    total_sales=("订单金额", "sum")
).reset_index()

# 销售额降序，计算累计占比
product_stats = product_stats.sort_values("total_sales", ascending=False).reset_index(drop=True)
total_sales = product_stats["total_sales"].sum()
product_stats["cum_ratio"] = product_stats["total_sales"].cumsum() / total_sales

# ABC分类规则
def abc_classify(ratio):
    if ratio <= 0.7:
        return "A类（核心商品）"
    elif ratio <= 0.9:
        return "B类（重要商品）"
    else:
        return "C类（长尾商品）"

product_stats["abc_level"] = product_stats["cum_ratio"].apply(abc_classify)

# 对齐数据库表字段：保留商品编码主键
abc_result = product_stats[["商品编码", "商品描述", "total_quantity", "total_sales", "cum_ratio", "abc_level"]]
abc_result.columns = ["product_code", "category", "total_quantity", "total_sales", "cum_ratio", "abc_level"]

print(f"商品SKU总数：{len(product_stats)}")
print(f"A类商品数量：{len(product_stats[product_stats['abc_level'].str.startswith('A')])}")

# 4. 计算 RFM 基础指标
# =============================================
print("=== 4. RFM客户分层计算 ===")
latest_date = df_clean["下单时间"].max()

rfm = df_clean.groupby("客户ID").agg(
    recency=("下单时间", lambda x: (latest_date - x.max()).days),
    frequency=("订单号", "nunique"),
    monetary=("订单金额", "sum")
).reset_index()

rfm.columns = ["customer_id", "recency", "frequency", "monetary"]
rfm_result = rfm.copy()

# =============================================
# 2. 排名法打分（1-5分，彻底解决重复值报错）
# =============================================
# R：最近消费间隔，天数越小排名越高，得分越高
rfm_result["r_score"] = pd.cut(
    rfm_result["recency"].rank(method="first"),
    5, labels=[5,4,3,2,1]
).astype(int)

# F：消费频次，次数越多排名越高，得分越高
rfm_result["f_score"] = pd.cut(
    rfm_result["frequency"].rank(method="first"),
    5, labels=[1,2,3,4,5]
).astype(int)

# M：消费金额，金额越高排名越高，得分越高
rfm_result["m_score"] = pd.cut(
    rfm_result["monetary"].rank(method="first"),
    5, labels=[1,2,3,4,5]
).astype(int)

# =============================================
# 3. 业务版8层客户分层（80分位阈值，符合业务分布）
# =============================================
r_high_thres = rfm_result["r_score"].quantile(0.8)
f_high_thres = rfm_result["f_score"].quantile(0.8)
m_high_thres = rfm_result["m_score"].quantile(0.8)

def rfm_classify(row):
    r_high = row["r_score"] >= r_high_thres
    f_high = row["f_score"] >= f_high_thres
    m_high = row["m_score"] >= m_high_thres
    
    if r_high and f_high and m_high:
        return "核心价值客户"
    elif r_high and f_high and not m_high:
        return "潜力发展客户"
    elif r_high and not f_high and m_high:
        return "重要深耕客户"
    elif r_high and not f_high and not m_high:
        return "新活跃客户"
    elif not r_high and f_high and m_high:
        return "重要召回客户"
    elif not r_high and f_high and not m_high:
        return "一般召回客户"
    elif not r_high and not f_high and m_high:
        return "流失高价值客户"
    else:
        return "流失客户"

rfm_result["rfm_level"] = rfm_result.apply(rfm_classify, axis=1)
print(f"有效客户总数：{len(rfm_result)} 人")

# ===================== 5. MySQL事务写入 =====================
print("\n=== 5. 连接MySQL并写入数据 ===")
conn = pymysql.connect(**MYSQL_CFG)
cursor = conn.cursor()

# 空值转换函数
def nan_to_none(df):
    data = df.values.tolist()
    return [[None if pd.isna(item) else item for item in row] for row in data]

try:
    # 写入前清空表，避免重复数据
    cursor.execute("TRUNCATE TABLE order_detail")
    cursor.execute("TRUNCATE TABLE abc_result")
    cursor.execute("TRUNCATE TABLE rfm_result")

    # 5.1 写入订单明细表（分批）
    order_df = df_clean[[
        "订单号", "客户ID", "国家", "商品描述",
        "购买数量", "单价", "订单金额", "下单时间", "订单异常标记"
    ]]
    order_df.columns = [
        "order_id", "customer_id", "country", "product_name",
        "quantity", "unit_price", "amount", "order_date", "is_outlier"
    ]
    order_data = nan_to_none(order_df)
    sql_order = """
        INSERT INTO order_detail 
        (order_id, customer_id, country, product_name, quantity, unit_price, amount, order_date, is_outlier)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for i in range(0, len(order_data), BATCH_SIZE):
        batch = order_data[i:i+BATCH_SIZE]
        cursor.executemany(sql_order, batch)
        print(f"订单明细进度：{min(i+BATCH_SIZE, len(order_data))} / {len(order_data)}")

    # 5.2 写入ABC分类表
    abc_data = nan_to_none(abc_result)
    sql_abc = """
        INSERT INTO abc_result 
        (product_code, category, total_quantity, total_sales, cum_ratio, abc_level)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.executemany(sql_abc, abc_data)
    print(f"✅ ABC分类表写入 {cursor.rowcount} 行")

    # 5.3 写入RFM分层表
    write_df = rfm_result[[
        "customer_id", "recency", "frequency", "monetary",
        "r_score", "f_score", "m_score", "rfm_level"
    ]]
    write_data = nan_to_none(write_df)
    insert_sql = """
        INSERT INTO rfm_result 
        (customer_id, recency, frequency, monetary, r_score, f_score, m_score, rfm_level)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.executemany(insert_sql, write_data)
    print(f"✅ RFM分层表写入 {cursor.rowcount} 行")

    # 统一提交事务
    conn.commit()
    print("\n✅ 全部数据写入成功，事务已提交")

except Exception as e:
    conn.rollback()
    print(f"\n❌ 写入失败，事务已回滚，错误信息：{e}")

finally:
    # 统一关闭连接
    cursor.close()
    conn.close()

# ===================== 6. 落库结果校验 =====================
print("\n=== 6. 落库结果校验 ===")

try:
    # 重新建立连接做只读校验
    conn = pymysql.connect(**MYSQL_CFG)
    cursor = conn.cursor()

    # 6.1 三张表行数校验
    cursor.execute("SELECT COUNT(*) FROM order_detail")
    order_count = cursor.fetchone()[0]
    print(f"订单明细表：{order_count} 行")

    cursor.execute("SELECT COUNT(*) FROM abc_result")
    abc_count = cursor.fetchone()[0]
    print(f"ABC分类表：{abc_count} 行")

    cursor.execute("SELECT COUNT(*) FROM rfm_result")
    rfm_count = cursor.fetchone()[0]
    print(f"RFM分层表：{rfm_count} 行")

    # 6.2 核心指标交叉校验（Python计算值 vs 数据库落库值）
    cursor.execute("SELECT SUM(amount), COUNT(DISTINCT customer_id) FROM order_detail")
    sql_total, sql_cust = cursor.fetchone()
    # 修复：Decimal转float，解决类型不兼容问题
    sql_total = float(sql_total)
    
    py_total = round(df_clean["订单金额"].sum(), 2)
    py_cust = df_clean["客户ID"].nunique()

    print(f"\n-------- 核心指标交叉校验 --------")
    print(f"订单总金额：Python计算值 = {py_total} | 数据库落库值 = {round(sql_total, 2)}")
    print(f"客户总数：Python计算值 = {py_cust} | 数据库落库值 = {sql_cust}")

    if abs(py_total - sql_total) < 0.01 and py_cust == sql_cust:
        print("✅ 核心指标完全一致，落库准确")
    else:
        print("⚠️ 指标存在差异，请检查数据写入逻辑")

except Exception as e:
    print(f"❌ 校验执行出错：{e}")

finally:
    # 兜底关闭资源，无论成功失败都执行
    cursor.close()
    conn.close()

print("\n=== 全流程执行完成 ===")

