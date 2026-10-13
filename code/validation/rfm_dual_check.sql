USE cross_border_ecommerce;

-- ========== 链路二：SQL独立计算RFM ==========
DROP TEMPORARY TABLE IF EXISTS sql_rfm_temp;

CREATE TEMPORARY TABLE sql_rfm_temp
WITH 
base_rfm AS (
    SELECT 
        customer_id,
        DATEDIFF((SELECT MAX(order_date) FROM order_detail), MAX(order_date)) AS recency,
        COUNT(DISTINCT order_id) AS frequency,
        SUM(amount) AS monetary
    FROM order_detail
    GROUP BY customer_id
),
rfm_score AS (
    SELECT 
        customer_id,
        recency,
        frequency,
        monetary,
        -- R：间隔越小分数越高
        6 - NTILE(5) OVER (ORDER BY recency ASC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM base_rfm
),
-- 统计总客户数
total_cnt AS (
    SELECT COUNT(*) AS cnt FROM rfm_score
),
-- 分别计算三个维度的80分位阈值
r_thres AS (
    SELECT r_score AS r_high
    FROM (
        SELECT r_score, ROW_NUMBER() OVER (ORDER BY r_score) AS rn
        FROM rfm_score
    ) t, total_cnt
    WHERE rn = FLOOR(cnt * 0.8)
),
f_thres AS (
    SELECT f_score AS f_high
    FROM (
        SELECT f_score, ROW_NUMBER() OVER (ORDER BY f_score) AS rn
        FROM rfm_score
    ) t, total_cnt
    WHERE rn = FLOOR(cnt * 0.8)
),
m_thres AS (
    SELECT m_score AS m_high
    FROM (
        SELECT m_score, ROW_NUMBER() OVER (ORDER BY m_score) AS rn
        FROM rfm_score
    ) t, total_cnt
    WHERE rn = FLOOR(cnt * 0.8)
),
-- 合并三个阈值为一行
thresholds AS (
    SELECT r_high, f_high, m_high
    FROM r_thres, f_thres, m_thres
)
-- 8层客户分层
SELECT 
    s.*,
    CASE 
        WHEN s.r_score >= t.r_high AND s.f_score >= t.f_high AND s.m_score >= t.m_high THEN '核心价值客户'
        WHEN s.r_score >= t.r_high AND s.f_score >= t.f_high AND s.m_score < t.m_high THEN '潜力发展客户'
        WHEN s.r_score >= t.r_high AND s.f_score < t.f_high AND s.m_score >= t.m_high THEN '重要深耕客户'
        WHEN s.r_score >= t.r_high AND s.f_score < t.f_high AND s.m_score < t.m_high THEN '新活跃客户'
        WHEN s.r_score < t.r_high AND s.f_score >= t.f_high AND s.m_score >= t.m_high THEN '重要召回客户'
        WHEN s.r_score < t.r_high AND s.f_score >= t.f_high AND s.m_score < t.m_high THEN '一般召回客户'
        WHEN s.r_score < t.r_high AND s.f_score < t.f_high AND s.m_score >= t.m_high THEN '流失高价值客户'
        ELSE '流失客户'
    END AS rfm_level
FROM rfm_score s
CROSS JOIN thresholds t;

-- ========== 双链路三项校验 ==========
-- 校验1：客户总数核对
SELECT 'SQL独立计算' AS 链路, COUNT(*) AS 客户总数 FROM sql_rfm_temp
UNION ALL
SELECT 'Python计算写入' AS 链路, COUNT(*) AS 客户总数 FROM rfm_result;

-- 校验2：核心指标汇总核对
SELECT 
    'SQL独立计算' AS 链路,
    ROUND(AVG(recency), 2) AS 平均R值,
    ROUND(AVG(frequency), 2) AS 平均F值,
    ROUND(SUM(monetary), 2) AS 总营收
FROM sql_rfm_temp
UNION ALL
SELECT 
    'Python计算写入' AS 链路,
    ROUND(AVG(recency), 2) AS 平均R值,
    ROUND(AVG(frequency), 2) AS 平均F值,
    ROUND(SUM(monetary), 2) AS 总营收
FROM rfm_result;

-- 校验3：各分层客户数分布核对
SELECT 'SQL独立计算' AS 链路, rfm_level, COUNT(*) AS 客户数
FROM sql_rfm_temp 
GROUP BY rfm_level 
ORDER BY 客户数 DESC;

SELECT 'Python计算写入' AS 链路, rfm_level, COUNT(*) AS 客户数
FROM rfm_result 
GROUP BY rfm_level 
ORDER BY 客户数 DESC;
