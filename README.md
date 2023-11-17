# OpenAI Assistant that serves knowledge about Apache Camel

## Setup (Mac OS)

It's best served through a dedicated conda environment:

```
conda create --name camel python=3.11
conda activate camel
pip install -r requirements.txt
```

## Usage

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

Once the process completes, you should have a text-only representation of the documentation under `data/text`.