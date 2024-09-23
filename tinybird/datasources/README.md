


## AggregatingMergeTree 

Landing aggregations into an **AggregatingMergeTree** table named `hourly_revenue_mv`. 


```bash
# Data Source created from Pipe 'feed_hourly_revenue_mv'

SCHEMA >
    `timestamp` DateTime,
    `revenue` AggregateFunction(sum, Float64)

ENGINE "AggregatingMergeTree"
ENGINE_PARTITION_KEY "toYYYYMM(timestamp)"
ENGINE_SORTING_KEY "timestamp"
```
And here is the SQL query that manages the state of intermediate data that gets merged. 

This query pulls from the `purchases_mv` and writes to a `hourly_revenue_mv` table:
```sql
SELECT
    toStartOfHour(timestamp) AS timestamp,
    sumState(price) AS revenue
FROM purchases_mv
GROUP BY timestamp
```

```sql
SELECT
    toStartOfHour(timestamp) AS timestamp,
    ROUND(sumMerge(revenue),2) AS revenue
FROM feed_hourly_revenue_mv
GROUP BY timestamp
```
