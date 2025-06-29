import logging
from typing import Optional, List
import requests

from open_webui.retrieval.web.main import SearchResult, get_filtered_results
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


def search_perplexity(
    api_key: str,
    query: str,
    count: int,
    filter_list: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Search using Perplexity API and return the results as a list of SearchResult objects.

    Args:
      api_key (str): A Perplexity API key
      query (str): The query to search for
      count (int): Maximum number of results to return

    """

    # Handle PersistentConfig object
    if hasattr(api_key, "__str__"):
        api_key = str(api_key)

    try:
        url = "https://api.perplexity.ai/chat/completions"

        # Create payload for the API call
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a search assistant. Provide factual information with citations.",
                },
                {"role": "user", "content": query},
            ],
            "temperature": 0.2,  # Lower temperature for more factual responses
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Make the API request
        response = requests.request("POST", url, json=payload, headers=headers, timeout=30)

        # Parse the JSON response
        json_response = response.json()

        # Extract citations from the response
        citations = json_response.get("citations", [])

        # Create search results from citations
        results = []
        for i, citation in enumerate(citations[:count]):
            # Extract content from the response to use as snippet
            content = ""
            if "choices" in json_response and json_response["choices"]:
                if i == 0:
                    content = json_response["choices"][0]["message"]["content"]

            result = {"link": citation, "title": f"Source {i+1}", "snippet": content}
            results.append(result)

        if filter_list:

            results = get_filtered_results(results, filter_list)

        return [
            SearchResult(
                link=result["link"], title=result["title"], snippet=result["snippet"]
            )
            for result in results[:count]
        ]

    except Exception as e:
        log.error(f"Error searching with Perplexity API: {e}")
        return []
