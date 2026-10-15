# 🤖 Multi-Agent Text-to-SQL Analytics System

## Overview

This project is an intelligent analytics assistant that accepts business questions in natural language, translates them into SQL, validates and executes the generated query, and returns a natural-language answer based on the query result.

The system uses a **multi-agent architecture**. Specialized agents handle different stages of the analytics workflow, while a central workflow orchestrates execution and passes structured context between stages.

Example questions include:

- How many customers do we have?
- What is our total revenue from delivered orders?
- How many product views happened?
- Show customer events by type.

The goal is to let business users ask questions without needing to know SQL syntax, database schemas, table relationships, or the technical definitions of business metrics.

---

## Database Overview

The Lunato dataset is a synthetic e-commerce database designed for developing
and evaluating a Text-to-SQL agent.

The database contains 13 tables covering customers, products, orders,
inventory, customer behavior, and benchmark data.

### Tables and Row Counts

| Table | Rows | Description |
|---|---:|---|
| `customers` | 200,000 | Customer information |
| `products` | 20,000 | Product catalog |
| `product_variants` | 39,957 | Product variants |
| `orders` | 1,000,000 | Customer orders |
| `order_items` | 2,760,580 | Individual items within orders |
| `customer_events` | 10,000,000 | Customer behavior and interaction events |
| `reviews` | 278,263 | Product reviews |
| `wishlist` | 500,000 | Customer wishlist entries |
| `carts` | 400,000 | Shopping carts |
| `cart_items` | 799,840 | Items within shopping carts |
| `inventory_events` | 139,836 | Inventory changes and events |

### Dataset Statistics

- **Total tables:** 13
- **Total rows:** 16,139,476
- **Customers:** 200,000
- **Products:** 20,000
- **Orders:** 1,000,000
- **Customer events:** 10,000,000
- **Benchmark questions:** 1,000

---

# 🎯 Problem Statement

Organizations store business data across many related tables. Getting reliable answers from that data often requires:

- SQL expertise.
- Knowledge of database schemas and relationships.
- Familiarity with business definitions and metric rules.
- Careful handling of filters, joins, and aggregations.

Business users tend to ask questions in business language, while the database stores information in technical structures such as:

```text
customers.customer_id
orders.total_amount
order_items.product_id
customer_events.event_type
```

This creates a gap between **business language and database language**.

Traditional approaches have limitations:

- Static dashboards cannot answer every new question.
- Rule-based natural-language interfaces are difficult to extend to complex queries.
- A single LLM call can generate plausible but incorrect SQL.
- Incorrect joins, filters, or metric definitions can lead to misleading results.
- Generated queries must be checked before they are allowed to run against a database.

The project aims to build an analytics workflow that can:

1. Understand the user's business intent.
2. Identify a suitable metric and relevant dimensions or filters.
3. Retrieve schema and semantic context.
4. Generate SQL.
5. Review and validate the query.
6. Apply security, permission, and query-cost checks.
7. Execute the query against the database.
8. Reflect on the execution result.
9. Produce a natural-language answer.
10. Record traces and evaluation data for debugging and improvement.

---

# 🏗️ System Architecture

The system follows a **multi-agent architecture**. Specialized agents have distinct responsibilities, while the workflow remains responsible for orchestration and state transitions.

### High-level flow

```text
                       User Question
                             |
                             v
                    +------------------+
                    |   SQL Workflow   |
                    +------------------+
                             |
                             v
                 +--------------------------+
                 | Query Spec Generator     |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Semantic Metadata        |
                 | Retrieval                |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | SQL Generator Agent      |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | SQL Review Agent         |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | SQL Validation           |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | SQL Firewall             |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Permission Check         |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Query Cost Check         |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Database Execution       |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Result Policy            |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Reflection Agent         |
                 +--------------------------+
                             |
                             v
                 +--------------------------+
                 | Answer Agent             |
                 +--------------------------+
                             |
                             v
                       Final Answer
```

The exact execution path depends on the workflow status. For example, clarification requests, validation failures, permission denials, cost rejections, and other error states may stop the workflow before database execution or answer generation.

---

# 🔄 Execution Flow

### 1. User Request

The user sends a natural-language question, for example:

```text
How many customers do we have?
```

The application creates a request context and trace identifier. The context is passed through the workflow and used to associate stages and logs with the same request.

### 2. Query Understanding

**Agent:** `query_spec_generator`

Responsibilities:

- Interpret the user's intent.
- Identify the requested business metric.
- Detect dimensions and filters.
- Determine whether the question needs clarification.
- Provide structured information to subsequent stages.

Example output:

```json
{
  "request_type": "query",
  "metric": "customer_count",
  "dimension_count": 0,
  "filter_count": 0,
  "needs_clarification": false
}
```

### 3. Semantic Metadata Retrieval

The workflow retrieves relevant semantic and database context before SQL generation. Depending on the question, this can include:

- Metric definitions.
- Business glossary entries.
- Relevant schema tables and columns.
- Table relationships.
- Relevant business context.
- Semantic seed tables and the final selected schema tables.

Example metadata:

```json
{
  "metric": "customer_count",
  "semantic_seed_tables": [
    "customers",
    "order_items"
  ],
  "final_schema_tables": [
    "customers",
    "orders",
    "order_items"
  ]
}
```

The retrieved context is supplied to the agents so that SQL generation can use known database structures and business definitions instead of relying only on model assumptions.

### 4. SQL Generation

**Agent:** `sql_generator`

The SQL generator uses the query specification and retrieved context to produce SQL and any required parameters.

Example:

```sql
SELECT COUNT(customer_id)
FROM customers;
```

### 5. SQL Review

**Agent:** `sql_review`

The SQL review agent checks the generated query against the question, query specification, schema, and business context. Depending on the review result, the workflow may continue, request clarification, reject the candidate, or attempt repair where supported by the workflow.

Example review result:

```json
{
  "verdict": "pass",
  "confidence": 1.0,
  "issue_count": 0
}
```

### 6. SQL Validation and Security Checks

Before execution, the workflow applies database query controls. These include:

- **SQL validation:** checks whether the SQL and parameters satisfy the validator's requirements.
- **SQL firewall:** applies query safety rules.
- **Permission checks:** verifies whether the request is permitted.
- **Query cost checks:** estimates query cost and rejects queries that exceed configured limits.

These layers reduce the risk of executing invalid, unsafe, unauthorized, or excessively expensive queries. They do not guarantee that every accepted query expresses the user's intent correctly; result correctness must also be evaluated.

### 7. Database Execution

The approved SQL is executed against the configured database. The execution layer records execution status, latency, row count, truncation information, and errors when available.

Database execution is configured with safety limits, including a statement timeout and a maximum number of returned rows. Evaluation comparisons must take truncation into account because truncated output cannot establish full result equality.

### 8. Result Policy

The workflow applies its result policy to the database output. Depending on configuration and result content, this stage can apply output restrictions or redaction and prepare result metadata for subsequent stages.

### 9. Reflection

**Agent:** `reflection`

After execution, the reflection agent reviews the question, query context, SQL, and execution result. It produces a structured verdict used by the workflow to determine whether the result is acceptable or needs further handling.

Example:

```json
{
  "verdict": "pass",
  "confidence": 0.99
}
```

Reflection provides an additional verification step; it should not be interpreted as a formal proof that the query result is correct.

### 10. Answer Generation

**Agent:** `answer`

The answer agent converts the result and its context into a natural-language response that addresses the user's question.

---

# 🧠 Multi-Agent Design

The system separates responsibilities into specialized components rather than relying on one model call to perform every task.

### Query Spec Generator

Converts the natural-language request into a structured representation of the desired analytics operation.

### SQL Generator Agent

Generates SQL using the query specification, schema, relationships, and business definitions provided by the workflow.

### SQL Review Agent

Reviews the generated SQL and identifies issues that may require rejection, clarification, or repair.

### Reflection Agent

Evaluates the generated query and execution result in the context of the original request and produces a structured reflection result.

### Answer Agent

Formats the result into a natural-language answer.

### Workflow Orchestrator

The workflow controls the order of operations, maintains request state, applies validation and safety checks, and determines which status or result should be returned. Agents exchange information through structured inputs and outputs rather than calling each other directly.

---

# 🧩 Design Patterns Used

### 1. Multi-Agent Pattern

Each agent owns a focused responsibility. This makes the workflow easier to inspect and allows stage-level failures to be distinguished from failures in other stages.

### 2. Tool Use Pattern

The workflow and agents use external capabilities such as schema retrieval and database execution. Tool outputs are fed back into the orchestrated request flow.

### 3. Reflection Pattern

The result is reviewed after query execution rather than relying solely on the generated SQL. Reflection is an additional safeguard, not a substitute for benchmark-based correctness evaluation.

### 4. Structured Workflow State

The workflow passes a request context and structured results between components. Trace identifiers and stage-level events support debugging across a full request lifecycle.

---

## 🤝 Agent Communication Model

The workflow is the central orchestrator. Agents do not directly coordinate with one another; the workflow passes structured context and outputs between stages.

Conceptually, the request context contains information such as:

```json
{
  "trace_id": "...",
  "user_query": "...",
  "metadata": {},
  "state": {}
}
```

Observability events record stage names, trace IDs, status, timing, model information, prompt versions, token usage metadata, and safe input/output summaries when available.

---

# 📊 Benchmark Evaluation

The project includes a benchmark evaluator for measuring the behavior of the Text-to-SQL workflow against a dataset of questions and reference SQL queries.

### Evaluation Dataset

The benchmark dataset is configured through the application configuration and is currently expected at:

`evaluation/benchmark_questions.csv`

Each benchmark row includes fields such as:

- `question_id`: unique question identifier.
- `category`: benchmark question category.
- `difficulty`: difficulty label.
- `question`: natural-language question.
- `expected_sql`: reference SQL query.
- `tables_required`: tables expected to be relevant, where provided.

### Evaluation Procedure

For each question, the evaluator:

1. Sends the question to the Text-to-SQL agent.
2. Records whether SQL was generated and captures the generated SQL.
3. Records the workflow status and end-to-end latency.
4. Executes the reference SQL against the configured database.
5. Executes the generated SQL against the same database when available.
6. Compares the two query results when both executions succeed and the results are complete.
7. Saves per-question details and aggregates benchmark metrics.

The comparison evaluates the **results returned by the SQL queries**, not whether the SQL strings are textually identical. Different SQL statements can be considered equivalent when their returned values match according to the evaluator's result-comparison rules.

The result comparison should account for:

- The number of returned rows.
- The values and positions of returned columns, while ignoring column aliases when configured to do so.
- Row ordering when the reference SQL includes `ORDER BY`.
- Whether either query failed or returned truncated results.

If execution fails or the output is truncated, a definitive result match may be unavailable. Such cases should be reported separately rather than counted automatically as mismatches.

### Core Evaluation Metrics

The generated JSON report includes metrics such as:

| Metric | Meaning |
|---|---|
| `total_questions` | Number of benchmark questions evaluated. |
| `generation_success_rate` | Fraction of questions for which the evaluator considers SQL generation successful. |
| `execution_success_rate` | Fraction of questions whose workflow reaches a configured execution-success status. |
| `result_sql_match_rate` | Fraction of comparable questions whose generated and reference SQL results match. |
| `result_sql_match_evaluated_questions` | Number of questions for which a definitive match or mismatch was established. |
| `result_sql_match_unavailable_questions` | Number of questions for which a definitive result comparison was unavailable. |
| `average_latency_ms` | Average end-to-end evaluation latency per question. |
| `status_counts` | Count of questions grouped by final workflow status. |

#### Result SQL Match Rate

The primary query-correctness metric is `result_sql_match_rate`:

```text
result_sql_match_rate = matching comparable questions / all comparable questions
```

A comparable question is one where the evaluator can determine whether the two outputs match. The metric does not measure textual similarity between SQL statements.

A matching result is evidence that the generated query returns the same output for the current database state and comparison rules. It does not, by itself, prove that the queries are equivalent for all possible database states.

### Token Usage

The report is designed to capture token consumption per question and as aggregate statistics across the benchmark. Where provider usage metadata is available and correctly parsed, the tracked values include:

- `input_tokens`: input tokens consumed by model requests.
- `output_tokens`: output tokens generated by model requests.
- `total_tokens`: total tokens consumed across model requests.

Token usage can be aggregated for the full benchmark and for category and difficulty breakdowns. It can also be recorded for individual questions.

Token fields depend on the usage metadata returned by the configured model provider. Missing or unparsed usage values must not be treated as reliable zero consumption. Verify that the provider's actual usage fields are mapped correctly before using input/output token totals for cost or efficiency conclusions.

### Category and Difficulty Analysis

The report provides breakdowns by question category and difficulty so performance can be analyzed in more detail than through the overall success rate alone.

The category breakdown can help identify strengths and weaknesses in areas such as:

- Aggregation.
- Basic queries.
- Behavioral analytics.
- Customer analytics.
- Filtering.
- Inventory queries.
- Joins.
- Reviews.
- Time-series queries.
- Complex queries.

The actual category names and their counts are derived from the benchmark dataset. The report can include:

- The number of distinct categories.
- The number of questions in each category.
- The percentage of the dataset represented by each category.
- Result SQL match rate by category.
- Result SQL match rate by difficulty.
- Counts of comparable and unavailable result comparisons.

These distribution metrics help reveal whether the dataset is broad or dominated by a few categories. Aggregate scores should be interpreted alongside category-level results because an overall score can hide weaknesses in categories with fewer questions.

### Per-Question Details

The `results` section of the JSON report stores the outcome of each question. Depending on what is available during evaluation, a record can include:

- Question ID, category, difficulty, and question text.
- Generated SQL and reference SQL.
- Generation and execution status.
- `result_sql_match`.
- End-to-end latency.
- Generated SQL execution details and returned rows.
- Reference SQL execution details and returned rows.
- Token usage metadata.
- Errors or reasons why comparison was unavailable.

Per-question details make it possible to investigate mismatches and failures without relying only on aggregate metrics.

### Evaluation Report

The benchmark report is written to:

`reports/benchmark_report.json`

The report contains benchmark execution metadata, aggregate metrics, category and difficulty breakdowns, and per-question results. A live benchmark run should be distinguished from any report reconstructed from historical logs; the report mode and matching method should describe how its results were obtained.

---

# 🔭 Observability and Instrumentation

The project records structured events for request and agent lifecycles. Depending on the event type, the logs can include:

- `trace_id` and request-level `question_id`, when propagated.
- Event type, stage name, agent name, and timestamp.
- Latency and workflow status.
- Model name and prompt version.
- Token usage metadata.
- Safe summaries of inputs and outputs.
- SQL validation, firewall, permission, cost-check, and execution outcomes.
- Error type and error message when a stage fails.

Example event:

```json
{
  "event_type": "agent_completed",
  "trace_id": "...",
  "agent_name": "sql_generator",
  "latency_ms": 2273,
  "status": "success",
  "token_usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 3834
  }
}
```

The numbers above are illustrative. In particular, token counts should be validated against the actual usage object returned by the provider before the input and output totals are treated as accurate. Structured logs are useful for debugging, but logs that lack complete result data cannot be used to reconstruct execution-result matching reliably.

---

# 🛠️ Technology Stack

The project is built around the following technology areas; exact versions and enabled components are defined by the repository configuration and dependencies.

### AI and LLM

- LLM-powered agents.
- Prompt engineering.
- Structured output generation.
- Model tool calling where configured.
- Workflow-level agent orchestration.

### Backend

- Python.
- Request and workflow orchestration.
- Configuration-driven behavior.
- Structured logging and error handling.

### Database

- SQL database connectivity.
- Schema and relationship metadata.
- Query validation and execution.
- Statement timeouts and maximum returned-row limits.

### AI and Software Patterns

- Multi-Agent Systems.
- Tool Use.
- Reflection.
- Semantic retrieval.
- Structured workflow state.

### Observability and Evaluation

- Structured logs.
- Request tracing.
- Latency tracking.
- Token usage metadata.
- CSV-based benchmark evaluation.
- JSON evaluation reports.

---

# 🚀 Future Improvements

Potential directions for further work include:

- Improving token usage parsing and validating provider-specific usage metadata.
- Improving metric disambiguation for ambiguous business questions.
- Measuring schema retrieval accuracy against explicit ground truth.
- Measuring metric-selection accuracy against labeled benchmark specifications.
- Improving SQL repair policies and tracking repair success rates.
- Adding benchmark versioning and storing the configuration used for each run.
- Comparing model and prompt versions across repeated benchmark runs.
- Adding latency percentiles, such as p50 and p95, rather than relying only on average latency.
- Tracking category and difficulty coverage over time.
- Learning from user feedback.
- Improving cost reporting and model efficiency analysis.
- Adding approval steps for high-risk or expensive queries where appropriate.
- Building an evaluation dashboard for comparing benchmark runs.

---

# 🎯 Conclusion

This project demonstrates how an LLM-based system can support analytical questions through a structured Text-to-SQL workflow rather than a single unconstrained generation step.

Its main components combine:

- Multi-agent orchestration.
- Semantic metadata retrieval.
- SQL generation and review.
- SQL validation and safety checks.
- Controlled database execution.
- Result reflection and answer generation.
- Structured observability.
- Benchmark evaluation based on generated-versus-reference query results.

The benchmark framework provides a practical way to measure end-to-end behavior, inspect individual failures, analyze category coverage, and guide future improvements. Its metrics should be interpreted in light of the dataset, comparison rules, execution limits, and availability of reliable provider usage metadata.
