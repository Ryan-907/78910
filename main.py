import requests
import inspect
from pydantic import TypeAdapter, BaseModel, Field
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from typing import Any
#MODEL = "meta-llama/Llama-3.1-8B-Instruct"

with open("secrets.json", "r") as f:
    api_keys = json.load(f)

fmp = api_keys['apis']['fmp']

print(fmp)
input()

'''
Market simulation tool. This tool will do the following:
Enable users to create theoretical users that employ various strategies for
investing. This will enable them to project future earnings for stable strategies. 
'''

def fetch_stock_data(stock_symbol: str, api:str=fmp) -> dict:
    '''
    Fetches a summary of stock data

    :param stock_symbol: Desired companies stock symbol
    :output: JSON formatted summary of stock information
    '''
    
    url = f"https://financialmodelingprep.com/stable/quote?symbol={stock_symbol}&apikey={api}" 
    response = requests.get(url)
    if str(response) == '<Response [402]>':
        return 'Error 402, insufficient credits or invalid stock symbol'
    else:
        data = response.json()
        return json.dumps(data, indent=2)


FUNC_MAP = {'Stock Data': fetch_stock_data}

FUNC_LLM = [
    {
        'name': 'Stock Data',
        'description': inspect.getdoc(fetch_stock_data),
        'parameters':TypeAdapter(fetch_stock_data).json_schema()
    }
]

class LlmResponse(BaseModel):
    message: str | None = Field(
        description=(
            "Message sent to user. Can be none if a" \
            "function call is provided."
        ),
        default=None,
    )
    function: str | None = Field(
        description=(
            "The name of the function to call. Can be"  
            "none if no function call is required and" 
            "response is valid"
        )
    )
    arguments: dict[str, Any] | None = Field(
        description=(
            "The key is the name of the parameter. The value is thee argument" \
            "to pass to it. This can be none if no function call is required" \
            "and a response is provided. All parameters must be provided"
        )
    )

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
    
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map='auto', low_cpu_mem_usage=True)
tokenizer = AutoTokenizer.from_pretrained(MODEL)

generator = pipeline('text-generation', model=model, tokenizer=tokenizer, return_full_text=False)
prompt_values = {
    'functions':json.dumps(FUNC_LLM),
    'response_model_json':json.dumps(LlmResponse.model_json_schema())
}
turn = 0

while turn <=10:
    turn+=1
    context = None
    prompt_values['context'] = ''
    user_input = input('Ask a question about stocks: ')
    while True:
        if context:
            prompt_values['context'] = context
        
        prompts = [
            {
                "role":"system", "content": PROMPT.format(**prompt_values)
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
            context = f'You got the function results! Use this information to summarize the stock {result}'
        else:
            print(parsed.message)
            break
