-- 基于清洗后订单明细表 order_detail
-- 字段：订单号, 客户ID, 国家, 商品描述, 购买数量, 单价, 订单金额, 下单时间

-- ========== 1. 全局核心KPI指标 ==========
SELECT
  COUNT(DISTINCT 订单号) AS 总订单数,
  SUM(订单金额) AS 总销售额,
  COUNT(DISTINCT 客户ID) AS 客户总数,
  SUM(订单金额) / COUNT(DISTINCT 订单号) AS 平均客单价
FROM order_detail;

-- ========== 2. 各国市场营收占比 ==========
SELECT
  国家,
  SUM(订单金额) AS 市场营收,
  ROUND(SUM(订单金额) / (SELECT SUM(订单金额) FROM order_detail) * 100, 2) AS 营收占比
FROM order_detail
GROUP BY 国家
ORDER BY 市场营收 DESC;

-- ========== 3. RFM客户价值分层 ==========
WITH rfm_calc AS (
  SELECT
    客户ID,
    -- R：最近一次购买距数据最晚日期的天数
    DATEDIFF((SELECT MAX(下单时间) FROM order_detail), MAX(下单时间)) AS 最近购买天数R,
    -- F：累计下单次数
    COUNT(DISTINCT 订单号) AS 购买频次F,
    -- M：累计消费金额
    SUM(订单金额) AS 消费总金额M
  FROM order_detail
  GROUP BY 客户ID
),
rfm_score AS (
  SELECT
    *,
    -- R反向打分：天数越少得分越高
    NTILE(5) OVER (ORDER BY 最近购买天数R DESC) AS R得分,
    -- F、M正向打分
    NTILE(5) OVER (ORDER BY 购买频次F ASC) AS F得分,
    NTILE(5) OVER (ORDER BY 消费总金额M ASC) AS M得分
  FROM rfm_calc
)
SELECT
  客户ID,
  最近购买天数R,
  购买频次F,
  消费总金额M,
  CASE
    WHEN R得分 >= 4 AND F得分 >= 4 AND M得分 >= 4 THEN '重要价值客户'
    WHEN R得分 >= 4 AND F得分 <= 2 AND M得分 >= 4 THEN '重要发展客户'
    WHEN R得分 <= 2 AND F得分 >= 4 AND M得分 >= 4 THEN '重要保持客户'
    WHEN R得分 <= 2 AND F得分 <= 2 AND M得分 >= 4 THEN '重要挽留客户'
    WHEN R得分 >= 4 AND F得分 >= 4 AND M得分 <= 2 THEN '一般价值客户'
    WHEN R得分 >= 4 AND F得分 <= 2 AND M得分 <= 2 THEN '一般发展客户'
    WHEN R得分 <= 2 AND F得分 >= 4 AND M得分 <= 2 THEN '一般保持客户'
    ELSE '流失客户'
  END AS 客户分层
FROM rfm_score;

-- ========== 4. ABC商品营收分类 ==========
WITH product_sales AS (
  SELECT
    商品描述,
    SUM(购买数量) AS 总销量,
    SUM(订单金额) AS 总销售额
  FROM order_detail
  GROUP BY 商品描述
  ORDER BY 总销售额 DESC
),
cumulative AS (
  SELECT
    *,
    SUM(总销售额) OVER (ORDER BY 总销售额 DESC) / SUM(总销售额) OVER () AS 累计销售额占比
  FROM product_sales
)
SELECT
  商品描述,
  总销量,
  总销售额,
  累计销售额占比,
  CASE
    WHEN 累计销售额占比 <= 0.7 THEN 'A类（核心商品）'
    WHEN 累计销售额占比 <= 0.9 THEN 'B类（重要商品）'
    ELSE 'C类（长尾商品）'
  END AS ABC分类
FROM cumulative;

