# Camel Quickstart Assistant

## Setup (Mac OS)

It's best served through a dedicated conda environment:

```
conda create --name camel python=3.11
conda activate camel
pip install -r requirements.txt
```
### Prerequisites

#### API Keys

All the tools and the assistant leverage 3rd party services for which you need API keys.

Make sure these are present in your environment:

```
export OPENAI_API_KEY="..."
export QDRANT_KEY="..."
export QDRANT_URL="..."
export COHERE_KEY="..."
export PG_URL="..."
```

## Data Preparation

### Step 1: Prepare the local data

The current impl serves the main knowledge through local files that have been scraped from the camel documentation.

As a first step you need to prepare the local data using the `crawl` and `upsert` tools available.

Once the process completes, you should have a text-only representation of the documentation under `./data/text/*.*`.

> Typically this is a one-time step

### Step 2: Upsert the data

The data prepared, needs to be indexed and will be kept in a vector DB to enable semantic search for the agent.

In a second step you need to upsert data using the `upsert` tools available:

```
python upsert_pdf.py 

usage: upsert_pdf.py [-h] -c COLLECTION [-s START] [-b BATCHSIZE] [-p PROCESSES] [-m MODE] [-f FILE]

```

Once the process completes, you should have a meta data and vector embeddings in QDrant (http://qdrant.tech/).

> Typically this is a one-time step


## Using the assistant

```
streamlit run agent-ui.py
```

[...]

#### Results

`user:` How do I perform content filtering in Camel? Show me an example.

`assistant:` To perform content filtering in Apache Camel, you can use various mechanisms in the routing logic to transform content from the inbound message. Here are some examples:

1. Using a Processor with the filtering programmed in Java:
```java
from("direct:start")
    .process(new Processor() {
        public void process(Exchange exchange) {
            String body = exchange.getMessage().getBody(String.class);
            // do something with the body
            // and replace it back
            exchange.getMessage().setBody(body);
        }
    })
    .to("mock:result");
```

2. Using a Bean EIP to use any Java method on any bean as a content filter:
```java
from("activemq:My.Queue")
    .bean("myBeanName", "doFilter")
    .to("activemq:Another.Queue");
```
  
3. Using an Expression to filter content from messages. For example, using XPath to filter an XML message to select all the `<foo><bar>` elements:
```java
from("activemq:Input")
    .setBody().xpath("//foo:bar")
    .to("activemq:Output");
```

These examples demonstrate how to perform content filtering in Apache Camel using different mechanisms in the routing logic, such as Processor, Bean EIP, and Expression.
