import os
import shutil
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from dotenv import load_dotenv
from py_clob_client.constants import AMOY
from key import key

# Whoosh imports
from whoosh.fields import Schema, TEXT, ID, KEYWORD
from whoosh.index import create_in
from whoosh.analysis import Tokenizer, Token, StopFilter

# Import spaCy and load the English model
import spacy
nlp = spacy.load('en_core_web_sm')

# -------------------------
# Custom spaCy Tokenizer for Whoosh
# -------------------------
class SpacyTokenizer(Tokenizer):
    def __call__(self, value, **kwargs):
        # Ensure value is a string.
        if not isinstance(value, str):
            value = str(value, "utf-8")
        doc = nlp(value)
        for token in doc:
            # Skip spaces and punctuation.
            if token.is_space or token.is_punct:
                continue
            t = Token()
            t.text = token.lemma_.lower()
            t.pos = token.i  # Use token's index in the doc as its position.
            yield t

# Create a custom analyzer using our spaCy tokenizer and a stopword filter.
custom_analyzer = SpacyTokenizer() | StopFilter()

# -------------------------
# Fetch Open Markets from the API
# -------------------------
def get_open_markets():
    host = "https://clob.polymarket.com"

    chain_id = AMOY
    client = ClobClient(host, key=key, chain_id=chain_id)

    all_markets = []
    next_cur = ""
    while next_cur != "LTE=":
        markets = client.get_markets(next_cur)
        next_cur = markets["next_cursor"]
        all_markets.extend(markets["data"])

    # Filter for open markets.
    open_markets = [
        market for market in all_markets
        if not market.get("closed", False)
           and market.get("active", False)
           and market.get("accepting_orders", False)
    ]
    print(f"Retrieved {len(open_markets)} open markets out of {len(all_markets)} total.")
    return open_markets

# -------------------------
# Build/Rebuild the Whoosh Index (written to disk)
# -------------------------
def build_index(markets, index_dir="indexdir"):
    # Delete old index directory if it exists.
    if os.path.exists(index_dir):
        shutil.rmtree(index_dir)
    os.mkdir(index_dir)
    
    # Define the schema.
    schema = Schema(
        question=TEXT(stored=True),  # Original question for display.
        text=TEXT(stored=True, analyzer=custom_analyzer),  # Combined and lemmatized (question + description).
        tags=KEYWORD(stored=True, commas=True, lowercase=True),
        market_url=ID(stored=True)
    )
    
    ix = create_in(index_dir, schema)
    writer = ix.writer()
    
    for market in markets:
        # Extract the original question.
        question = market.get("question", "")
        # Get description (won't be stored separately).
        description = market.get("description", "")
        # Combine question and description for the searchable text
        
        tags_list = market.get("tags", [])
        weighted_tags = " ".join(tag for tag in tags_list for _ in range(3))
        tags_str = ",".join(tags_list) if tags_list else ""
        
        # Create combined text with extra weight on tags.
        combined_text = f"{question} {description} {weighted_tags}"
        
        
        market_slug = market.get("market_slug", "")
        market_url = f"https://polymarket.com/market/{market_slug}" if market_slug else ""
        
        writer.add_document(
            question=question,
            text=combined_text,
            tags=tags_str,
            market_url=market_url
        )
    writer.commit()
    print("Index built successfully and written to disk.")

# -------------------------
# Main: Fetch markets and build the index.
# -------------------------
def main():
    open_markets = get_open_markets()
    build_index(open_markets)

if __name__ == "__main__":
    main()
