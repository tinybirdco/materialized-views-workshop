# Data Sources

With this schema definition, the `product` object is loaded into a `product_info` string. 

```bash

SCHEMA >
    `action` String `json:$.action`,
    `customer_id` String `json:$.customer_id`,
    `product_id` String `json:$.product.product_id`,
    `product_info` String `json:$.product`,
    `timestamp` DateTime `json:$.timestamp`

ENGINE "MergeTree"
ENGINE_PARTITION_KEY "toYear(timestamp)"
ENGINE_SORTING_KEY "timestamp, action, customer_id, product_id"
```



