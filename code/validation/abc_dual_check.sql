USE cross_border_ecommerce;

-- ========== 链路二：SQL独立计算ABC分类 ==========
DROP TEMPORARY TABLE IF EXISTS sql_abc_temp;

CREATE TEMPORARY TABLE sql_abc_temp
WITH 
-- 1. 按商品编码聚合销量、销售额
product_agg AS (
    SELECT 
        product_code,
        MAX(product_name) AS category,
        SUM(quantity) AS total_quantity,
        SUM(amount) AS total_sales
    FROM order_detail
    GROUP BY product_code
),
-- 2. 按销售额降序计算累计占比
product_rank AS (
    SELECT 
        *,
        -- 累计销售额 / 总销售额 = 累计占比
        SUM(total_sales) OVER (ORDER BY total_sales DESC) 
        / SUM(total_sales) OVER () 
        AS cum_ratio
    FROM product_agg
)
-- 3. ABC分类（70%/90%/100%，和Python规则完全一致）
SELECT 
    product_code,
    category,
    total_quantity,
    total_sales,
    cum_ratio,
    CASE 
        WHEN cum_ratio <= 0.7 THEN 'A类（核心商品）'
        WHEN cum_ratio <= 0.9 THEN 'B类（重要商品）'
        ELSE 'C类（长尾商品）'
    END AS abc_level
FROM product_rank
ORDER BY total_sales DESC;

-- ========== 双链路三项校验 ==========
-- 校验1：SKU总数核对
SELECT 'SQL独立计算' AS 链路, COUNT(*) AS SKU总数 FROM sql_abc_temp
UNION ALL
SELECT 'Python计算写入' AS 链路, COUNT(*) AS SKU总数 FROM abc_result;

-- 校验2：总销售额核对
SELECT 'SQL独立计算' AS 链路, SUM(total_sales) AS 总销售额 FROM sql_abc_temp
UNION ALL
SELECT 'Python计算写入' AS 链路, SUM(total_sales) AS 总销售额 FROM abc_result;

-- 校验3：各分类SKU数量核对
SELECT 'SQL独立计算' AS 链路, abc_level, COUNT(*) AS SKU数量
FROM sql_abc_temp 
GROUP BY abc_level 
ORDER BY abc_level;

SELECT 'Python计算写入' AS 链路, abc_level, COUNT(*) AS SKU数量
FROM abc_result 
GROUP BY abc_level 
ORDER BY abc_level;
