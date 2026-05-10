import requests
import inspect
from pydantic import TypeAdapter, BaseModel, Field
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from typing import Any

# Constants
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
with open("secrets.json", "r") as f: 
    API_KEYS = json.load(f)

FMP = API_KEYS['apis']['fmp'] #Financial Modeling Prep API

# Create a JSON of the form {"apis": {"api_name/acronym": "api_key"}} called secrets.json. 
# Then replace the above line with the appropriate naems
# This is the financial Modeling Prep (FMP) api

def fetch_stock_quote(stock_symbol: str) -> dict:
    '''
    Fetches a summary of stock data

    :param stock_symbol: Desired companies stock symbol
    :output: JSON formatted summary of stock information
    '''  
    response = requests.get(f"https://financialmodelingprep.com/stable/quote?symbol={stock_symbol}&apikey={FMP}") #API Call
    if str(response) == '<Response [402]>': 
        return 'Error 402, insufficient credits or invalid stock symbol'
    else:
        data = response.json()
        return json.dumps(data, indent=2) # Formatted 


FUNC_MAP = {'Stock Quote': fetch_stock_quote}

FUNC_LLM = [ # Provides LLM the function descriptions
    {
        'name': 'Stock Quote',
        'description': inspect.getdoc(fetch_stock_quote),
        'parameters':TypeAdapter(fetch_stock_quote).json_schema()
    }
]

class LlmResponse(BaseModel): # Structured response. Message is for the user, while function and arguments are passed to the function chosen.
    message: str | None = Field(
        description=(
            "Message sent to user. Can be none if a " \
            "function call is provided."
        ),
        default=None,
    )
    function: str | None = Field(
        description=(
            "The name of the function to call. Can be "  
            "none if no function call is required and " 
            "response is valid"
        ), 
        default = None
    )
    arguments: dict[str, Any] | None = Field(
        description=(
            "The key is the name of the parameter. The value is the argument " \
            "to pass to it. This can be none if no function call is required " \
            "and a response is provided. All parameters must be provided"
        ), 
        default = None
    )

# Ensuring the model knows what functions are available, how to format the output in json
# and any needed context. 

PROMPT = inspect.cleandoc(""" 
        You are a stock analysis agent that has access to a function.
        This function provides robust data about the stock. Check the input
        that you receive from the user, extract any key entities you need.
                              
        If you do not have enough information in the prompt, DO NOT make up an answer.
        Instead, loook at the list of functions you can call to provide the information 
        you need to answer the users question.
                              
        You have access to the following list of functions
        {functions}
                              
        You MUST provide your response in the following JSON Schema below. You MUST
        take the types of the OUTPUT SCHEMA into account and adjust your provided text to fit
        the required types.
                              
        Here is the OUTPUT SCHEMA:
        {response_model_json}
        
        If you have enough information to answer the question, then provide the answer
        in the above JSON Schema, omitting the function name and arguments. DO NOT make up
        any answers. Your answers must come from the information provided in this prompt.
        
        {context}  
        """)

# Model Set up
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map='auto', low_cpu_mem_usage=True)
tokenizer = AutoTokenizer.from_pretrained(MODEL)
generator = pipeline('text-generation', model=model, tokenizer=tokenizer, return_full_text=False)

# Used for filling in PROMPT. Gives functions as a JSON dict and shows the JSON output expected
# of the model
prompt_values = {
    'functions':json.dumps(FUNC_LLM),
    'response_model_json':json.dumps(LlmResponse.model_json_schema())
}


# Ensuring infinite loops do not occur
turn = 0
while turn <=10:
    turn+=1
    context = None
    prompt_values['context'] = '' # Reset context while ensuring it is in the prompt formatted later
    user_input = input('Ask a question about stocks: ')

    while True:
        if context:
            prompt_values['context'] = context
        
        prompts = [
            {
                "role":"system", "content": PROMPT.format(**prompt_values) 
                # Guess we just returned from vacation because we are unpacking!!!!
            },
            {
                'role':'user', 'content':user_input
            }
        ]

        response = generator(prompts, truncation=True, max_new_tokens = 300)
        raw = response[0]['generated_text']
        parsed = LlmResponse.model_validate_json(raw)

        if parsed.function:
            result = FUNC_MAP[parsed.function](**parsed.arguments)
            context = f'Function executed successfully. Use this information to summarize the stock {result}'
        else:
            print(parsed.message)
            break
