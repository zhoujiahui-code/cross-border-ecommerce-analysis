-- 创建数据库
CREATE DATABASE IF NOT EXISTS cross_border_ecommerce 
DEFAULT CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE cross_border_ecommerce;

-- =============================================
-- 1. 订单明细表
-- =============================================
DROP TABLE IF EXISTS order_detail;
CREATE TABLE order_detail (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    order_id VARCHAR(64) COMMENT '订单号',
    customer_id VARCHAR(64) COMMENT '客户ID',
    country VARCHAR(50) COMMENT '国家',
    product_name TEXT COMMENT '商品描述',
    quantity INT COMMENT '购买数量',
    unit_price DECIMAL(10,2) COMMENT '单价',
    amount DECIMAL(12,2) COMMENT '订单金额',
    order_date DATE COMMENT '下单时间',
    is_outlier TINYINT COMMENT '订单异常标记：0-正常，1-异常',
    -- 常用查询维度索引
    INDEX idx_order_id (order_id),
    INDEX idx_customer_id (customer_id),
    INDEX idx_country (country),
    INDEX idx_order_date (order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细数据表';

-- =============================================
-- 2. ABC 商品分类结果表
-- =============================================
DROP TABLE IF EXISTS abc_result;
CREATE TABLE abc_result (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    product_code VARCHAR(32) COMMENT '商品编码(SKU)',
    category TEXT COMMENT '商品描述',
    total_quantity INT COMMENT '总销量',
    total_sales DECIMAL(12,2) COMMENT '总销售额',
    cum_ratio DECIMAL(10,6) COMMENT '累计销售额占比',
    abc_level VARCHAR(20) COMMENT 'ABC分类标签',
    INDEX idx_abc_level (abc_level),
    INDEX idx_product_code (product_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品ABC分类结果表';

-- =============================================
-- 3. RFM 客户分层结果表
DROP TABLE IF EXISTS rfm_result;
CREATE TABLE rfm_result (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    customer_id VARCHAR(50) COMMENT '客户ID',
    recency INT COMMENT '最近消费间隔天数',
    frequency INT COMMENT '累计购买频次',
    monetary DECIMAL(12,2) COMMENT '累计消费金额',
    r_score TINYINT COMMENT 'R维度得分(1-5)',
    f_score TINYINT COMMENT 'F维度得分(1-5)',
    m_score TINYINT COMMENT 'M维度得分(1-5)',
    rfm_level VARCHAR(20) COMMENT 'RFM客户分层',
    INDEX idx_customer_id (customer_id),
    INDEX idx_recency (recency),
    INDEX idx_rfm_level (rfm_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户RFM分层结果表';
