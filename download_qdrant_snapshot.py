import argparse
import sys
import requests
import os
from conf.constants import QDRANT_URL, QDRANT_KEY
from qdrant_client import QdrantClient

"""
Helper class to interact with Qdrant collections
"""


class QdrantCollectionsAgent:
    def __init__(self, url, key):
        self.key = key
        self.qdrant_client = QdrantClient(url, api_key=key)

    def get_collection_names(self):
        collections = self.qdrant_client.get_collections()
        return [collection.name for collection in collections.collections]

    def create_snapshot(self, collection_name):
        snapshot_info = self.qdrant_client.create_snapshot(
            collection_name=collection_name, wait=True)

        return f"{QDRANT_URL}/collections/{collection_name}/snapshots/{snapshot_info.name}"

    def download_snapshots(self, snapshot_url=None, local_snapshot_name=None):
        os.makedirs("snapshots", exist_ok=True)

        local_snapshot_path = os.path.join("snapshots", local_snapshot_name)

        response = requests.get(snapshot_url, headers={"api-key": self.key})
        try:
            with open(local_snapshot_path, "wb") as file:
                response.raise_for_status()
                file.write(response.content)
        except Exception as e:
            print(f"Unable to download snapshot: {e}")
        else:
            print(f"Snapshot downloaded to {local_snapshot_path}")


"""
Usage:
    # List all collections in the cluster

    python -m download_qdrant_snapshot.py -l
    python -m download_qdrant_snapshot.py --list

    # Create a snapshot for a collection and download it
    python download_qdrant_snapshot.py -d -c <collection_name>
    python download_qdrant_snapshot.py --download --collection <collection_name>
"""
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Qdrant collections operations')
    parser.add_argument(
        '-l', '--list', help='List collections', action='store_true', required=False)
    parser.add_argument('-d', '--download', help='Download snapshot',
                        action='store_true', required=False)
    parser.add_argument(
        '-c', '--collection', help='The collection name', required=False)
    args = parser.parse_args()

    # Validate arguments
    if args.download and not args.collection or args.collection and not args.download:
        parser.error(
            "the following arguments are required: -c/--collection when -d/--download is used")

    # Create a QdrantCollectionsAgent and fetch the collection names
    qdrant_collections_agent = QdrantCollectionsAgent(QDRANT_URL, QDRANT_KEY)
    collection_names = qdrant_collections_agent.get_collection_names()

    if args.list:
        print("Collection Names:")
        for name in collection_names:
            print(f'\t• {name}')

        sys.exit(0)

    if args.collection not in collection_names:
        print(f"Collection {args.collection} not found")
        sys.exit(1)
    else:
        print(f"Creating snapshot for collection {args.collection}")
        snapshot_url = qdrant_collections_agent.create_snapshot(
            args.collection)
        print(f"Snapshot created: {snapshot_url}")

        qdrant_collections_agent.download_snapshots(
            snapshot_url=snapshot_url, local_snapshot_name=f"{args.collection}.snapshot")
        sys.exit(0)
