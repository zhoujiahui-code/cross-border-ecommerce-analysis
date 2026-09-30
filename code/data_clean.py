import pandas as pd

# ========== 1. 读取原始数据 ==========
# 原始数据集为Online Retail.xlsx，此处读取后做标准化清洗
df = pd.read_excel("Online Retail.xlsx")

# 英文列名替换为中文，统一业务字段命名
df.columns = ["订单号","商品编码","商品描述","购买数量","下单时间","单价","客户ID","国家"]

# ========== 2. 数据预处理 ==========
# 时间格式转换，支撑后续时间维度分析
df["下单时间"] = pd.to_datetime(df["下单时间"])

# 缺失值处理：剔除无客户ID、无商品描述的无效订单
df_clean = df.dropna(subset=["客户ID", "商品描述"])

# 无效订单过滤：剔除退货订单（负数量）、单价≤0的异常记录
df_clean = df_clean[(df_clean["购买数量"] > 0) & (df_clean["单价"] > 0)]

# 异常值处理：3σ原则剔除单价极端值，避免干扰整体统计
price_mean = df_clean["单价"].mean()
price_std = df_clean["单价"].std()
price_upper = price_mean + 3 * price_std
df_clean = df_clean[df_clean["单价"] <= price_upper]

# 衍生核心业务字段：订单金额
df_clean["订单金额"] = df_clean["购买数量"] * df_clean["单价"]

# ========== 3. 核心指标校验（与FineBI看板对应） ==========
total_sales = df_clean["订单金额"].sum()
total_orders = df_clean["订单号"].nunique()
total_customers = df_clean["客户ID"].nunique()
avg_order_value = total_sales / total_orders

print("===== 核心运营指标 =====")
print(f"总销售额：{round(total_sales/10000,2)} 万英镑")
print(f"总订单数：{total_orders} 单")
print(f"客户总数：{total_customers} 人")
print(f"客单价：{round(avg_order_value,2)} 英镑")

# ========== 4. RFM客户价值分层 ==========
# 以数据集最晚下单时间为基准计算Recency
latest_date = df_clean["下单时间"].max()
rfm = df_clean.groupby("客户ID").agg(
    Recency=("下单时间", lambda x: (latest_date - x.max()).days),
    Frequency=("订单号", "nunique"),
    Monetary=("订单金额", "sum")
).reset_index()
rfm.columns = ["客户ID","最近购买天数R","购买频次F","消费总金额M"]

# 5分制打分（分位数法）
rfm["R得分"] = pd.qcut(rfm["最近购买天数R"], 5, labels=[5,4,3,2,1]).astype(int)
rfm["F得分"] = pd.qcut(rfm["购买频次F"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
rfm["M得分"] = pd.qcut(rfm["消费总金额M"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
rfm["RFM总分"] = rfm["R得分"] + rfm["F得分"] + rfm["M得分"]

# 8类客户分群（电商行业标准分层）
def rfm_segment(row):
    r, f, m = row["R得分"], row["F得分"], row["M得分"]
    if r >= 4 and f >= 4 and m >= 4:
        return "重要价值客户"
    elif r >= 4 and f <= 2 and m >= 4:
        return "重要发展客户"
    elif r <= 2 and f >= 4 and m >= 4:
        return "重要保持客户"
    elif r <= 2 and f <= 2 and m >= 4:
        return "重要挽留客户"
    elif r >= 4 and f >= 4 and m <= 2:
        return "一般价值客户"
    elif r >= 4 and f <= 2 and m <= 2:
        return "一般发展客户"
    elif r <= 2 and f >= 4 and m <= 2:
        return "一般保持客户"
    else:
        return "流失客户"

rfm["客户分层"] = rfm.apply(rfm_segment, axis=1)

# ========== 5. ABC商品分类 ==========
product_stats = df_clean.groupby("商品描述").agg(
    总销量=("购买数量", "sum"),
    总销售额=("订单金额", "sum")
).reset_index()
product_stats = product_stats.sort_values("总销售额", ascending=False).reset_index(drop=True)

# 累计销售额占比（帕累托法则）
total_sales_all = product_stats["总销售额"].sum()
product_stats["累计销售额占比"] = product_stats["总销售额"].cumsum() / total_sales_all

# ABC三类划分（70%/90%/100% 行业通用标准）
def abc_classify(ratio):
    if ratio <= 0.7:
        return "A类（核心商品）"
    elif ratio <= 0.9:
        return "B类（重要商品）"
    else:
        return "C类（长尾商品）"

product_stats["ABC分类"] = product_stats["累计销售额占比"].apply(abc_classify)

# ========== 6. 导出结果 ==========
# 导出FineBI看板用的三份基础数据
df_clean[["订单号","客户ID","国家","商品描述","购买数量","单价","订单金额","下单时间"]].to_csv(
    "BI用_清洗后明细数据.csv", index=False, encoding="utf-8-sig"
)
rfm.to_csv("BI用_RFM客户分层.csv", index=False, encoding="utf-8-sig")
product_stats.to_csv("BI用_ABC商品分类.csv", index=False, encoding="utf-8-sig")

# 导出100条脱敏样例数据（用于GitHub展示）
df_clean.sample(100, random_state=42).to_csv(
    "sample_orders.csv", index=False, encoding="utf-8-sig"
)


