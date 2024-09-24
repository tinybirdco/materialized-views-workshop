# Working with Materialized Views

## Creating action-specific tables

A common use case for Materialized Views (MVs) is cleaning up data by dropping columns, parsing nested JSON, promoting child attributes to 'top level' schema attributes, and building object-specific tables.  

Here Materialized Views are used to create separate tables with collections of these events:

* View
* Cart
* Uncart
* Purchase
* Return

Here is the query that creates a view-specific Data Source and feeds it data:

Data Source `estore_stream` --> Pipe [`feed_views_mv`] --> Data Source `views_mv`

```sql
SELECT timestamp, 
customer_id, 
product_id
FROM estore_stream
WHERE action = 'view'
```

Here we are loading into a MergeTree as we plan on building aggregations on this data.

```bash
SCHEMA >
    `timestamp` DateTime,
    `customer_id` String,
    `product_id` String

ENGINE "MergeTree"
ENGINE_PARTITION_KEY "toYYYYMM(timestamp)"
ENGINE_SORTING_KEY "timestamp, product_id, customer_id"
```
Similarly, we have:
* Data Source `estore_stream` --> Pipe [`feed_carts_mv`] --> Data Source `carts_mv`
* Data Source `estore_stream` --> Pipe [`feed_uncarts_mv`] --> Data Source `uncarts_mv`
* Data Source `estore_stream` --> Pipe [`feed_purchases mv`] --> Data Source `purchases_mv`
* Data Source `estore_stream` --> Pipe [`feed_returns mv`] --> Data Source `returns_mv`

### JSOnExtract functions

As we build the `purchases_mv` table, we parse nested JSON and and extract the `price` attribute:

```sql
SELECT timestamp, 
customer_id, 
product_id,
JSONExtractFloat(product_info, 'price') AS price
FROM estore_stream
WHERE action = 'purchase'
```

### Materializing JOINs

As we build the `returns_mv` table, we JOIN the action event stream with a product table:

```sql
SELECT timestamp, product_id, customer_id, p.brand, p.model, p.price
FROM estore_stream es JOIN products p
ON es.product_id = p.product_id
WHERE action = 'return'
```
The materialization process is driven by new data arriving in the Data Source on the LEFT side of the JOIN. 

The user story here is preparing data for another group that needs product metadata for their processing. We are using a ReplacingMergeTree table engine for the `return` actions to eliminate duplicates. We do not anticipate performing aggregating on this data and instead are preparing the de-duplicated by using a ReplacingMergeTree engine. 


## Another deduplication example using the ReplacingMergeTree engine

Deduplicating a `duplicates` table into a `dedupped_rmt` table.

```bash
SCHEMA >
    `action` String,
    `customer_id` String,
    `product_id` String,
    `product_info` String,
    `timestamp` DateTime

ENGINE "ReplacingMergeTree"
ENGINE_PARTITION_KEY "toYYYYMM(timestamp)"
ENGINE_SORTING_KEY "timestamp, product_id, customer_id, product_info"
```

A simple query writes all data to the `dedupp3d_rmt` table

```sql
SELECT * FROM duplicates
```

Now, count the duplicates in the original `duplicates` table:

```sql
SELECT SUM(duplicate_count) as total_duplicates
    FROM (
        SELECT timestamp, product_id, COUNT(*) -1 as duplicate_count 
        FROM duplicates 
        WHERE timestamp > NOW() - INTERVAL 10 MINUTES
        GROUP BY timestamp, product_id
        HAVING COUNT(*) > 1
    ) AS subquery
```

And compare with duplicates in the `dedupped_rmt` table. Try the query with and without the `FINAL` keyword.

```sql

SELECT SUM(duplicate_count) as total_duplicates
    FROM (
        SELECT timestamp, product_id, COUNT(*) -1 as duplicate_count 
        FROM dedupped_rmt FINAL
        WHERE timestamp > NOW() - INTERVAL 10 MINUTES
        GROUP BY timestamp, product_id
        HAVING COUNT(*) > 1
    ) AS subquery
```


## AggregatingMergeTree 

Landing aggregations into an **AggregatingMergeTree** table named `hourly_revenue_mv`. 

Here is the SQL query that manages the state of intermediate data as it gets ingested and prepares it for merging. It uses the `countState` and `sumState` functions:

This query pulls from the `purchases_mv` and writes to a `hourly_revenue_mv` table:
```sql
SELECT
    toStartOfHour(timestamp) AS timestamp,
    countState(price) AS sales,
    sumState(price) AS revenue
FROM purchases_mv
GROUP BY timestamp
```
This query is configured to write to an AggregatingMergeTree `hourly_revenue_mv` table with this .datasource definition: 

```bash
# Data Source created from Pipe 'feed_hourly_revenue_mv'

SCHEMA >
    `timestamp` DateTime,
    `sales` AggregateFunction(count, Float64),
    `revenue` AggregateFunction(sum, Float64)

ENGINE "AggregatingMergeTree"
ENGINE_PARTITION_KEY "toYYYYMM(timestamp)"
ENGINE_SORTING_KEY "timestamp"
```
And here is a query that reads from the `hourly_revenue_mv` table and uses the `-Merge` functions to trigger the merge process and get the real-time aggregations:

```sql
SELECT
    toStartOfHour(timestamp) AS timestamp,
    countMerge(sales) AS sales,
    ROUND(sumMerge(revenue),2) AS revenue
FROM hourly_revenue_mv 
WHERE timestamp > NOW() - INTERVAL 7 DAYS
GROUP BY timestamp
ORDER BY timestamp DESC
```