from flask import Flask, render_template, request, jsonify
import os
import json
import requests
from datetime import datetime, timedelta
import re  # Added to support regex extraction

app = Flask(__name__)


def extract_question_from_url(url):
    # Extract the question part from the URL
    match = re.search(r'polymarket\.com/event/([^?]+)', url)
    if match:
        question = match.group(1)
        # Replace hyphens with spaces and make it more readable
        question = question.replace('-', ' ').replace('/', ': ')
        return question
    return None

def process_market_data(market_data, price_data, trades_data):
    if not all([market_data, price_data, trades_data]):
        return None
    
    try:
        # Get current market price from price data
        yes_price = float(price_data.get('midpoint', 0.5))  # Using midpoint price
        no_price = 1 - yes_price
        
        # Generate dummy data for demonstration
        timestamps = [(datetime.now() - timedelta(days=i)).strftime('%m/%d') for i in range(5)]
        yes_values = [round(yes_price * 100 + (i * 2)) for i in range(5)]
        no_values = [round(no_price * 100 - (i * 2)) for i in range(5)]
        volumes = [round(1000 * (1 + i * 0.2)) for i in range(5)]
        
        # Get market details
        market_name = market_data.get('name', 'Unknown Market')
        market_description = market_data.get('description', '')
        
        # Extract question from market name or use default
        question = market_name if market_name != 'Unknown Market' else 'Market Question Not Available'
        
        return {
            'market_info': {
                'name': market_name,
                'description': market_description,
                'question': question
            },
            'market_sentiment': {
                'yes': round(yes_price * 100),
                'no': round(no_price * 100)
            },
            'historical_data': {
                'labels': timestamps,
                'yes_values': yes_values,
                'no_values': no_values
            },
            'volume_data': {
                'labels': timestamps,
                'values': volumes
            },
            'prediction': 'YES' if yes_price > 0.5 else 'NO',
            'confidence': round(max(yes_price, no_price) * 100)
        }
        
    except Exception as e:
        print(f"Error processing market data: {str(e)}")
        return None

def query_perplexity(question, api_key):
    url = "https://api.perplexity.ai/chat/completions"
    
    prompt = """You are an advanced research assistant with access to reliable online sources. For each query you receive, please follow these steps:
1. **Question:** Analyze the text and form a well-structured question out of it.
2. **Search:** Perform a thorough search using credible sources to gather all relevant information regarding the query.
3. **Answer:** Based on the evidence you collected, determine whether the answer to the query is 'YES' or 'NO'
4. **Confidence Rating:** Provide a confidence level for your answer on a scale from 0 to 100, where 0 means no confidence and 100 means absolute confidence.
5. **Explanation:** Write a brief explanation detailing your reasoning and summarizing the key findings from your search.
5. **Citations:** List the citations (including source names, publication dates, and URLs if applicable) that you used to support your answer.
6. Return in **JSON Format:** Format your response as valid JSON with the following fields:
    - `question`
    - `answer`
    - `confidence`
    - `explanation`
    - `citations`"""
    
    payload = {
        "model": "sonar-reasoning-pro",
        "messages": [
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "max_tokens": 5000,
        "temperature": 0.7,
        "top_p": 0.9,
        "search_domain_filter": None,
        "return_images": False,
        "return_related_questions": False,
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1,
        "response_format": None
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        full_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        print("Full response:", full_response)
        
        try:
            # Extract JSON part from the response
            import json
            import re
            
            # Find JSON block in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', full_response, re.DOTALL)
            if not json_match:
                print("No JSON block found in response")
                return None, None, None
                
            json_str = json_match.group(1)
            parsed_json = json.loads(json_str)
            
            # Extract the required fields
            question = parsed_json.get('question', '')
            answer = parsed_json.get('answer', '').upper()
            confidence = parsed_json.get('confidence')
            explanation = parsed_json.get('explanation', '')
            citations = parsed_json.get('citations', [])
            
            # Format citations into strings
            formatted_citations = []
            for citation in citations:
                if isinstance(citation, dict):
                    citation_str = f"{citation.get('source', '')} "
                    if 'date' in citation:
                        citation_str += f"({citation.get('date', '')}) "
                    if 'url' in citation:
                        citation_str += f"{citation.get('url', '')}"
                    formatted_citations.append(citation_str.strip())
                else:
                    formatted_citations.append(str(citation))
            
            # Validate the parsed data
            if not answer or confidence is None:
                print("Failed to parse essential information from JSON response:", json_str)
                return None, None, None
                
            formatted_response = {
                'question': question,
                'prediction': answer,
                'confidence': confidence,
                'explanation': explanation,
                'sources': formatted_citations
            }
            
            return answer, formatted_response, formatted_citations
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            print("Raw JSON string:", json_str if 'json_str' in locals() else "No JSON found")
            return None, None, None
            
    except Exception as e:
        print(f"Error querying Perplexity API: {str(e)}")
        return None, None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        polymarket_link = data.get('polymarket_link')
        perplexity_api_key = data.get('api_key')
        
        if not perplexity_api_key:
            return jsonify({'error': 'Perplexity API key is required'}), 400
        
        question = extract_question_from_url(polymarket_link)
        if not question:
            return jsonify({'error': 'Invalid Polymarket URL'}), 400

        prediction, response_data, sources = query_perplexity(question, perplexity_api_key)
        if not prediction:
            return jsonify({'error': 'Failed to get prediction from Perplexity'}), 500
        
        analysis_data = {
            'market_info': {
                'name': response_data['question'],
                'description': 'Analysis based on Perplexity AI prediction'
            },
            'prediction': prediction,
            'confidence': response_data['confidence'],
            'explanation': response_data['explanation'],
            'sources': response_data['sources']
        }
        
        return jsonify(analysis_data)
        
    except Exception as e:
        print(f"Error in analyze endpoint: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True)
