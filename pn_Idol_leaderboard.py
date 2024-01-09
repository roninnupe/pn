import json
import requests
from collections import Counter
from termcolor import colored

# URL of your GraphQL API
URL_PIRATE_NATION_GRAPH_API = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api"


# Function to get the game items data from the GraphQL API
def fetch_game_items_data(item_id):

    query_str = f'''
        {{
          gameItems(first: 1000, where: {{id: "{item_id}"}}) {{
            id
            name
            events(first: 1000) {{
              id
              to {{
                address
              }}
              amount
            }}
          }}
        }}
        '''

    query = {
        "query": query_str
    }

    print(query_str)
    input()

    response = requests.post(URL_PIRATE_NATION_GRAPH_API, json=query)
    if response.status_code == 200:
        data = response.json()
        return data['data']['gameItems']
    else:
        print(colored(f"Failed to get data: {response.status_code}", 'red'))
        return None


# Function to find the top 10 addresses that minted the most number of a particular idol
def find_top_minters(game_items_data, item_name):
    address_counter = Counter()

    for gameItem in game_items_data:
        for event in gameItem['events']:
            if event['to']:
                address = event['to']['address']
                amount = int(event['amount'])
                address_counter[address] += amount

    top_10_minters = address_counter.most_common(10)

    # Making the item name cyan and bold
    bright_item_name = colored(item_name, 'cyan', attrs=['bold'])
    print(colored(f"\n🏆 Top 10 Minters of {bright_item_name} 🏆", 'green'))

    medals = ["🥇", "🥈", "🥉"] + [""] * 7
    rank_colors = ['yellow', 'white', 'red'] + ['blue'] * 7
    for i, (address, count) in enumerate(top_10_minters):
        rank = colored(f"{i + 1}. ", rank_colors[i])
        minted_text = colored(f"Minted: {count} times {medals[i]}", 'cyan')
        address_text = colored(address, rank_colors[i])
        print(f"{rank}{address_text} - {minted_text}")


# Main function
def main():
    items_ids = [
        "0x3b4cdb27641bc76214a0cb6cae3560a468d9ad4a-316"
    ]

    for item_id in items_ids:
        game_items_data = fetch_game_items_data(item_id)
        if game_items_data:
            item_name = game_items_data[0]['name']
            find_top_minters(game_items_data, item_name)


# Execute the main function
if __name__ == "__main__":
    main()
