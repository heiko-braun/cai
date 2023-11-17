# OpenAI Assistant that serves knowledge about Apache Camel

## Setup (Mac OS)

It's best served through a dedicated conda environment:

```
conda create --name camel python=3.11
conda activate camel
pip install -r requirements.txt
```
### Prerequisites

#### OPENAI_API_KEY

Make sure you have set the `OPENAI_API_KEY` environment variable (https://platform.openai.com/api-keys).

#### ASSISTANT_ID

Make sure you have set the `ASSISTANT_ID` environment variable, pointing to the assistant that leverages the right function (below).

The assistant shpould be prepared with some instruction-tuning:

```
You are an assistant helping software developers create integrations with third-party systems using the Apache Camel framework. 

You should only answer based on the files found or any function provided. 
```

But more importantly it needs the following custom function:

```
{
  "name": "fetch_camel_docs",
  "description": "Retrieve additional documentation about Apache Camel",
  "parameters": {
    "type": "object",
    "properties": {
      "component": {
        "type": "string",
        "description": "The name of a Camel component"
      }
    },
    "required": [
      "component"
    ]
  }
}
```


## Usage

### Step 1: Prepapre the local data

The current impl serves the main knowledge through local files that have been scraped from the camel documentation.

As a first step you need to prepare the local data:

```
python crawl.py   
Found 539 links to relevant content

Parsing ...  https://camel.apache.org/components/4.0.x//index.html
Parsing ...  https://camel.apache.org/components/4.0.x//index.html
Parsing ...  https://camel.apache.org/components/4.0.x//activemq-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//amqp-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//arangodb-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//as2-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//asterisk-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//atmosphere-websocket-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//atom-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//avro-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//aws-summary.html
Parsing ...  https://camel.apache.org/components/4.0.x//aws2-athena-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//aws-cloudtrail-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//aws2-cw-component.html
Parsing ...  https://camel.apache.org/components/4.0.x//aws2-ddb-component.html

[...]

```

Once the process completes, you should have a text-only representation of the documentation under `./data/text/*.*`.

### Step 2: Invoke the assistant

```
python assistant.py

Prompt: How do I perform content filtering in Camel? Show me an example.

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
