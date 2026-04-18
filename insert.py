import asyncio
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

import httpx


async def index_chunks(
    data: Dict[str, Any],
    base_url: str = "http://localhost:8001"
) -> Optional[Dict[str, Any]]:
    """
    Send chunks to the /index endpoint and return the formatted response.

    Args:
        data: The loaded JSON data (expected to contain chunks).
        base_url: Base URL of the indexing service.

    Returns:
        Formatted dictionary suitable for /insert_chunks, or None on failure.
    """
    url = f"{base_url}/index"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)

    if response.status_code == 200:
        response_data = response.json()
        print("Chunks successfully sent to /index")

        # Format response as expected by /insert_chunks
        formatted_response = {
            "chunks": response_data.get("results", []),
            "chat_metadata": {}
        }
        return formatted_response
    else:
        print(f"Error sending chunks to /index: {response.status_code}, {response.text}")
        return None


async def insert_chunks(
    data: Dict[str, Any],
    base_url: str = "http://localhost:8002",
    timeout: float = 180.0
) -> None:
    """
    Send formatted chunks to the /insert_chunks endpoint.

    Args:
        data: The formatted dictionary (must contain "chunks" and "chat_metadata").
        base_url: Base URL of the Qdrant insert service.
        timeout: Request timeout in seconds.
    """
    url = f"{base_url}/insert_chunks"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=data)

    if response.status_code == 200:
        print("Chunks successfully sent to /insert_chunks:", response.json())
    else:
        print(f"Error sending chunks to /insert_chunks: {response.status_code}, {response.text}")


def save_intermediate_file(data: Dict[str, Any], file_path: str = "response.json") -> None:
    """Save intermediate data to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Intermediate data saved to {file_path}")


def load_intermediate_file(file_path: str = "response.json") -> Dict[str, Any]:
    """Load intermediate data from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def main(
    data_file_path: str = "./data/Go Nova.json",
    index_base_url: str = "http://localhost:8001",
    insert_base_url: str = "http://localhost:8002",
    save_intermediate: bool = False,
    intermediate_file_path: str = "response.json"
) -> None:
    """
    Main orchestration function.

    Args:
        data_file_path: Path to the input JSON file containing chunks.
        index_base_url: Base URL for the /index endpoint.
        insert_base_url: Base URL for the /insert_chunks endpoint.
        save_intermediate: If True, save the formatted response to a file
                           before sending to /insert_chunks.
        intermediate_file_path: Path to use when saving/reading the intermediate file.
    """
    # Load input data
    try:
        with open(data_file_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        print(f"Loaded data from {data_file_path}")
    except Exception as e:
        print(f"Failed to load input file: {e}")
        return

    # Step 1: Send to /index and get formatted response
    formatted_response = await index_chunks(input_data, base_url=index_base_url)
    if formatted_response is None:
        print("Aborting: /index step failed.")
        return

    # Step 2: Either save to file or directly insert
    if save_intermediate:
        save_intermediate_file(formatted_response, intermediate_file_path)
        # Reload from file to simulate original behaviour (optional)
        data_to_insert = load_intermediate_file(intermediate_file_path)
    else:
        data_to_insert = formatted_response

    # Step 3: Send to /insert_chunks
    await insert_chunks(data_to_insert, base_url=insert_base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Send chunks to indexing and Qdrant insertion services."
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="./Go_Nova.json",
        help="Path to the input JSON file containing chunks (default: ./Go_Nova.json)"
    )
    parser.add_argument(
        "--index-url",
        type=str,
        default="http://localhost:8001",
        help="Base URL for the /index endpoint (default: http://localhost:8001)"
    )
    parser.add_argument(
        "--insert-url",
        type=str,
        default="http://localhost:8002",
        help="Base URL for the /insert_chunks endpoint (default: http://localhost:8002)"
    )
    parser.add_argument(
        "--save-intermediate",
        action="store_true",
        help="Save the formatted response to a JSON file before insertion (disabled by default)"
    )
    parser.add_argument(
        "--intermediate-file",
        type=str,
        default="response.json",
        help="Path for the intermediate file (default: response.json)"
    )

    args = parser.parse_args()

    asyncio.run(main(
        data_file_path=args.data_file,
        index_base_url=args.index_url,
        insert_base_url=args.insert_url,
        save_intermediate=args.save_intermediate,
        intermediate_file_path=args.intermediate_file
    ))