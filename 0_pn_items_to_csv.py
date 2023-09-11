import requests
import json
import pandas as pd
import pn_helper as pn
from concurrent.futures import ThreadPoolExecutor

def read_addresses(file_path):
    with open(file_path, 'r') as f:
        return [line.strip().lower() for line in f]

def make_query(address):
    return f"""
    {{
      accounts(where: {{address: "{address}"}}){{
        address
        currencies{{
            amount
        }}
        gameItems(where: {{amount_gt:0}}){{
          amount
          gameItem{{
            name
          }}
        }}
      }}
    }}
    """

def merge_data(data_list):
    merged_data = {"data": {"accounts": []}}
    for data in data_list:
        merged_data["data"]["accounts"].extend(data["data"]["accounts"])
    return merged_data

def to_csv(json_string):
    # Parse JSON data
    data = json.loads(json_string)

    # Initialize a list to store data as dictionaries
    data_list = []

    # Iterate over accounts
    for account in data['data']['accounts']:
        address = account['address']
        account_data = {'wallet': address}

        # Set PGLD value
        pgld = '0'
        if 'currencies' in account and len(account['currencies']) > 0:
            pgld = str(account['currencies'][0]['amount'])
        account_data['PGLD'] = pgld

        # Iterate over game items
        for game_item in account['gameItems']:
            name = game_item['gameItem']['name']
            amount = int(game_item['amount'])
            account_data[name] = amount

        data_list.append(account_data)

    # Convert the list of dictionaries to a DataFrame
    df = pd.DataFrame(data_list)

    # Replace NaN values with zeros
    df.fillna(0, inplace=True)

    # Convert the DataFrame to CSV
    df.to_csv(pn.data_path('game_items.csv'), index=False)

def fetch_data(address, url):
    query = make_query(address)
    response = requests.post(url, json={'query': query})
    return response.json()

def main():
    file_path = pn.data_path('addresses.txt')  
    addresses = pn.read_addresses(file_path)
    url = pn.URL_PIRATE_NATION_GRAPH_API

    ############################################################################################################################
    # NOTE: We are running multiple concurrent queries over the graph and we should refactor this to do a single aggregated call
    ############################################################################################################################

    # Use ThreadPoolExecutor to parallelize requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        data_list = list(executor.map(lambda addr: fetch_data(addr, url), addresses))

    # Handle failed requests if needed
    failed_requests = [i for i, data in enumerate(data_list) if 'errors' in data]
    if failed_requests:
        print(f"Failed requests for addresses: {', '.join(addresses[i] for i in failed_requests)}")

    # Remove failed requests from the data_list
    data_list = [data for i, data in enumerate(data_list) if i not in failed_requests]

    if data_list:
        merged_data = merge_data(data_list)
        to_csv(json.dumps(merged_data, indent=4))
    else:
        print("No valid data to process.")

if __name__ == "__main__":
    main()
