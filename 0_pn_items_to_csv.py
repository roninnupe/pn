import requests
import json
import pandas as pd

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

def get_data(url, query):
    response = requests.post(url, json={'query': query})
    return response.json()

def merge_data(data_list):
    merged_data = {"data": {"accounts": []}}
    for data in data_list:
        merged_data["data"]["accounts"].extend(data["data"]["accounts"])
    return merged_data

def to_csv(json_string):
    # Parse JSON data
    data = json.loads(json_string)

    # Initialize empty DataFrame
    df = pd.DataFrame()

    # Iterate over accounts
    for account in data['data']['accounts']:
        address = account['address']

        # Set PGLD value
        pgld = '0'
        if 'currencies' in account and len(account['currencies']) > 0:
            pgld = str(account['currencies'][0]['amount'])

        # If PGLD is not a column in the DataFrame, add it
        if 'PGLD' not in df.columns:
            df['PGLD'] = '0'

        # Add the PGLD value to the appropriate cell in the DataFrame
        df.loc[address, 'PGLD'] = pgld

        # Iterate over game items
        for game_item in account['gameItems']:
            name = game_item['gameItem']['name']
            amount = int(game_item['amount'])

            # If the item name is not a column in the DataFrame, add it
            if name not in df.columns:
                df[name] = 0

            # Add the item amount to the appropriate cell in the DataFrame
            df.loc[address, name] = amount

    # Replace NaN values with zeros
    df.fillna(0, inplace=True)

    # Rename the index to "wallet"
    df.index.name = "wallet"

    # Convert DataFrame to CSV
    df.to_csv('game_items.csv')

def main():
    file_path = 'addresses.txt'  # replace with your file path
    url = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api"
    addresses = read_addresses(file_path)
    data_list = []
    for address in addresses:
        query = make_query(address)
        data = get_data(url, query)
        data_list.append(data)
    merged_data = merge_data(data_list)
    to_csv(json.dumps(merged_data, indent=4))

if __name__ == "__main__":
    main()
