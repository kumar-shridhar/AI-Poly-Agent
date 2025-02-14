from whoosh.index import open_dir
from whoosh.qparser import QueryParser
from whoosh.scoring import BM25F
from whoosh.query import Or, Term

def search_markets(query_str, filter_tags=None, index_dir="indexdir"):
    """
    Search the Whoosh index using BM25F ranking over the "text" field.
    
    If filter_tags is provided and non-empty, only documents that contain
    at least one of the specified tags (in the 'tags' field) are returned.
    """
    ix = open_dir(index_dir)
    with ix.searcher(weighting=BM25F()) as searcher:
        # Parse the main query over the "text" field.
        parser = QueryParser("text", schema=ix.schema)
        parsed_query = parser.parse(query_str)
        
        # If filter_tags is non-empty, create a filter query.
        if filter_tags:
            tag_queries = [Term("tags", tag.lower()) for tag in filter_tags]
            # Use OR: document must have at least one matching tag.
            filter_query = Or(tag_queries)
        else:
            filter_query = None
        
        results = searcher.search(parsed_query, filter=filter_query, limit=None)
        return [dict(hit) for hit in results]

# -------------------------
# Main: Execute a search query.
# -------------------------
def main():

    user_query = "Calvin"  # Modify as needed.
    matched_markets = search_markets(user_query, filter_tags=["Sports"])
    print("search results")
    
    for market in matched_markets:
        print("Market URL:", market["market_url"])
        print("Question:", market["question"])
        print("Tags:", market["tags"])
        print("-" * 40)

if __name__ == "__main__":
    main()
