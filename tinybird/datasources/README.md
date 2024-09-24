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

This allows flexibility with the dynamic nature of the `product` attribute, which has a `price` attribute for `purchase` actions. 

An example `view` event: 

```json
{
    "customer_id": "customer_464",
    "product": {
        "product_id": "product_17"
    },
    "action": "view",
    "timestamp": "2024-09-19T16:33:11"
}
```

An example `purchase` event. These events add a `price` attribute: 

```json
{
    "customer_id": "customer_27",
    "product": {
        "product_id": "product_499",
        "price": 23.99
    },
    "action": "purchase",
    "timestamp": "2024-09-19T16:31:13"
}
```
