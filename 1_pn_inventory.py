import argparse
import os
import json
import math
import time
import pandas as pd
from web3 import Web3
import pn_helper as pn
from concurrent.futures import ThreadPoolExecutor
from ratelimit import limits, sleep_and_retry

# Global boolean variables
GET_ETH_BALANCE = True
GET_SHIP_COUNT = True
GET_ENERGY_BALANCE = True
# Maximum number of threads you want to run in parallel.
MAX_THREADS = 2


def fetch_user_inputs():
    global GET_ETH_BALANCE, GET_ENERGY_BALANCE
    
    # Take inputs from the user
    print("Note: Temporarily getting rate limited on arbitrum nova calls...")
    get_eth_balance_input = input("Do you want to fetch the Nova Eth balance? (y/n): ")
    get_energy_input = input("Do you want to get the latest energy? (y/n): ")

    # Convert user inputs to global booleans
    GET_ETH_BALANCE = True if get_eth_balance_input.lower() == 'y' else False
    GET_ENERGY_BALANCE = True if get_energy_input.lower() == 'y' else False

def merge_data(data_list):
    merged_data = {"data": {"accounts": []}}
    for data in data_list:
        merged_data["data"]["accounts"].extend(data["data"]["accounts"])
    return merged_data

def excel_sheet(json_string, ordered_addresses, file_name_start, max_thread_count=MAX_THREADS):
    print(f"Beginning to construct Excel({max_thread_count} threads)")
    
    # Parse JSON data
    data = json.loads(json_string)

    # Load up the inventory mapping, which is a file that has data_name and friendly display name mappings.
    # this is uded to help set the display order of columns, and their friendly name version. 
    # all additional items not listed will appear as their traditional name loaded from the jsaon and after the specified items
    df_data_mappings = pd.read_csv(pn.data_path('InventoryMapping.csv')) 
    data_name_to_display_name = df_data_mappings.set_index('data_name')['display_name'].to_dict()    

    # Define initial columns in the order we want
    columns = df_data_mappings['data_name'].tolist()

    # Initialize empty DataFrame with initial columns
    df = pd.DataFrame(columns=columns)
    df = df.dropna(axis=1, how='all')    

    eth_to_usd_price = 0
    if GET_ETH_BALANCE:
        # Get the ETH-to-USD exchange rate
        start_time = time.time()   
        eth_to_usd_price = pn.get_eth_to_usd_price()
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Fetching Eth-to-USD - execution time: {execution_time:.2f} seconds")      

    # Set execution tume for the loop
    number_of_accounts = len(data['data']['accounts'])
    start_time = time.time() 

    # Convert the 'accounts' list to a DataFrame
    df_accounts = pd.DataFrame(data['data']['accounts'])
    df_accounts['address'] = pd.Categorical(df_accounts['address'], categories=ordered_addresses, ordered=True)
    df_accounts = df_accounts.sort_values('address').reset_index(drop=True)

    start_time = time.time() 

    pn.Web3Singleton.get_EnergySystem() # Lets preload this 

    print(f"Iterating over {number_of_accounts} accounts to build the Excel output:")

    # Using ThreadPoolExecutor to process the wallets.
    with ThreadPoolExecutor(max_workers=max_thread_count) as executor:
        # Map each account to a thread.
        futures = [executor.submit(handle_wallet, index+1, eth_to_usd_price, row) for index, row in df_accounts.iterrows()]

    # Collect results as they come in.
    results = [future.result() for future in futures]

    # Append each result to the main DataFrame.
    for result in results:
        df = df._append(result, sort=False)

    end_time = time.time()
    avg_execution_time = (end_time - start_time) / number_of_accounts
    print(f"\nAverage execution time per account ({number_of_accounts}x): {avg_execution_time:.2f} seconds") 

    # Replace NaN values with zeros
    df.fillna(0, inplace=True)

    # Rename columns to be more friendly, and then order them properly
    df.rename(columns=data_name_to_display_name, inplace=True)
    specific_order = list(data_name_to_display_name.values())
    additional_columns = [col for col in df.columns if col not in specific_order]
    final_order = specific_order + additional_columns
    df = df.reindex(columns=final_order)

    # Convert DataFrame to Excel
    # Versions of Pandas >= 1.3.0:

    # smart logic to create filename based on parameter, 
    # and we will put the file in a subdirectory called inventory if it exists
    # otherwise it goes into the base directory
    excel_file_name = pn.add_inventory_data_path(f"{file_name_start}.xlsx")

    xlWriter = pd.ExcelWriter(excel_file_name,engine='xlsxwriter',engine_kwargs={'options': {'strings_to_numbers': True}})

    # Export to Excel
    df.to_excel(xlWriter, index=False)

    # Get the xlsxwriter workbook and worksheet objects
    workbook  = xlWriter.book
    worksheet = xlWriter.sheets['Sheet1']

    # Freeze the first row (row 1, column 0)
    worksheet.freeze_panes(1, 0)

    #create a vuewabke table dusokat
    worksheet.add_table(0, 0, df.shape[0], df.shape[1]-1, {'columns': [{'header': col} for col in df.columns]})

    # Calculate column sums
    column_sums = df.iloc[:, 2:].sum().tolist()  # Sum columns from 3rd column (index 2) to the last

    # Define the row number where you want to insert the sums (e.g., after the last row of the DataFrame)
    row_number = df.shape[0] + 2  # Adjust the row number as needed

    # Write the sums to the Excel worksheet outside of the table
    for col_num, value in enumerate(column_sums):
        worksheet.write(row_number, col_num + 2, value)  # Offset by 2 columns to match the DataFrame

    # Autofit column width to fit the content
    for i, col in enumerate(df.columns):
        column_len = max(df[col].astype(str).str.len().max(), len(col) + 2)  # Get the length of the longest content in the column or column name
        worksheet.set_column(i, i, column_len)  # Set the column width to fit        

    xlWriter._save()

    # Code to export a CSV copy to a directory called inventory only if you have that directory
    if os.path.exists("inventory"):
        
        sums_df = pd.DataFrame([[None, None] + column_sums], columns=df.columns)

        # Drop columns that are all NA from sums_df
        sums_df = sums_df.dropna(axis=1, how='all')

        df = df._append(sums_df, ignore_index=True)

        df.to_csv(f"inventory/{file_name_start}.csv", index=False)


def handle_wallet(walletID, eth_to_usd_price, row):
    global GET_ETH_BALANCE, GET_ENERGY_BALANCE

    address = row['address']
    currencies = row['currencies']
    gameItems = row['gameItems']
    nfts = row['nfts']

    ship_types_count = {}

    # Initialize a dictionary to store data for the current wallet
    wallet_data = {
        'walletID': walletID,
        'address': address,
        'Nova $': None,
        'Energy': None,
        'PGLD': 0
    }

    # Get the ETH balance
    if GET_ETH_BALANCE:
        eth_balance_eth = rate_limited_get_nova_eth_balance(address)
        # if we get no nova eth back, stop trying to get future energy for accounts
        if (eth_balance_eth is None):
            GET_ETH_BALANCE = False
        else:
            wallet_data['Nova $'] = round(eth_balance_eth * eth_to_usd_price, 2)

    # read the active energy for the address
    if GET_ENERGY_BALANCE:
        energy = rate_limited_get_energy_balance(address)
        # if we get no energy back, stop trying to get future energy for accounts
        if (energy is None):
            GET_ENERGY_BALANCE = False
        else:
            wallet_data['Energy'] = energy

    try:
        pgld = float(currencies[0]['amount'])
    except IndexError:
        print("The currencies list is empty.")
        pgld = 0.0  # or some default value

    if pgld > 0:
        pgld = pgld / (10 ** 18)

    wallet_data['PGLD'] = math.floor(pgld)

    # get the ship counts for the account
    if GET_SHIP_COUNT:
        for nft in nfts:
            ship_type = nft['name']
            if ship_type not in ship_types_count:
                ship_types_count[ship_type] = 0
            ship_types_count[ship_type] += 1

        for ship_type in ship_types_count:
            wallet_data[ship_type] = ship_types_count[ship_type]

    # Iterate over game items
    for game_item in gameItems:
        name = game_item['gameItem']['name']
        amount = int(game_item['amount'])

        # Add the item to the wallet_data dictionary
        wallet_data[name] = amount

    # Create a DataFrame from the wallet_data dictionary
    local_df = pd.DataFrame([wallet_data])

    return local_df


@limits(calls=10, period=1)
def rate_limited_get_energy_balance(address):
    energy = pn.get_energy(address)
    return energy


@limits(calls=10, period=1)
def rate_limited_get_nova_eth_balance(address):
    eth_balance_eth = pn.get_nova_eth_balance(address)
    return eth_balance_eth


def main():
    # Create an argument parser
    parser = argparse.ArgumentParser(description="This script fetches all the inventory for a specific set of wallets and outputs it into a pretty excel sheet")

    # Add the --max_threads argument with a default value of 3
    parser.add_argument("--max_threads", type=int, default=MAX_THREADS, help=f"Maximum number of threads (default: {MAX_THREADS})")

    # Parse the command-line arguments
    args = parser.parse_args()

    file_path = pn.select_file(prefix="addresses_",file_extension=".txt")
    addresses = pn.read_addresses(file_path)
    user_name = file_path.split('_')[1].split('.')[0]
    formatted_output = pn.format_addresses_for_query(addresses)

    # Call the function to fetch user inputs and set global variables
    fetch_user_inputs()

    start_time = time.time()

    query = f"""
        {{
            accounts(where: {{address_in: {formatted_output}}}){{
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
                nfts(where:{{nftType: "ship"}}){{
                    name
                }}        
            }}
        }}
        """
    data = pn.get_data(query)

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Building Data - execution time: {execution_time:.2f} seconds")

    start_time = time.time()
    excel_sheet(json.dumps(data, indent=4), addresses, f"inventory_{user_name}", args.max_threads)
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Creating excel from data - execution time: {execution_time:.2f} seconds") 

if __name__ == "__main__":
    main()