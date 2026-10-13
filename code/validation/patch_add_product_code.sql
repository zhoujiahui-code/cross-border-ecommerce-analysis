ALTER TABLE order_detail 
ADD COLUMN product_code VARCHAR(32) COMMENT '商品编码(SKU)' 
AFTER order_id;
