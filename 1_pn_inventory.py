import requests
import json
import math
import time
import pandas as pd
from web3 import Web3
import pn_helper as pn

# Global boolean variables
GET_ETH_BALANCE = False
GET_SHIP_COUNT = True
GET_ENERGY_BALANCE = False

def fetch_user_inputs():
    global GET_ETH_BALANCE, GET_ENERGY_BALANCE
    
    # Take inputs from the user
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

def excel_sheet(json_string, ordered_addresses):
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

    # Initialize walletID
    walletID = 1

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

    # Iterate over accounts
    print(f"Iterating over {number_of_accounts} accounts to build the Excel output:")
    for index, row in df_accounts.iterrows():

        print(f"{walletID}", end='...', flush=True)
        if walletID % 10 == 0:  # Check if it's the 10th, 20th, 30th, etc. iteration
            print()  # Add a line break        
               
        address = row['address']
        currencies = row['currencies']
        gameItems = row['gameItems']
        nfts = row['nfts']

        ship_types_count = {}

        # Assign walletID
        df.loc[address, 'walletID'] = walletID
        df.loc[address, 'address'] = address

        # Get the ETH balance
        if GET_ETH_BALANCE:
            eth_balance_eth = pn.get_nova_eth_balance(address)       
            df.loc[address,'Nova $'] =  round(eth_balance_eth * eth_to_usd_price, 2)

        # read the acrive energy for the address
        if GET_ENERGY_BALANCE:
            df.loc[address,'Energy'] =  pn.get_energy(address)
        
        pgld = float(currencies[0]['amount'])
        if pgld > 0 : pgld = pgld / (10 ** 18)

        if 'PGLD' not in df.columns:
            df['PGLD'] = 0

        # Add the PGLD value to the appropriate cell in the DataFrame
        df.loc[address, 'PGLD'] = math.floor(pgld)

        # get the ship counts for the account
        if GET_SHIP_COUNT:
            for nft in nfts:
                ship_type = nft['name']
                if ship_type not in ship_types_count:
                    ship_types_count[ship_type] = 0
                ship_types_count[ship_type] += 1

            for ship_type in ship_types_count:
                if ship_type not in df.columns:
                    df[ship_type] = 0
                df.loc[address, ship_type] = ship_types_count[ship_type]

        # Iterate over game items
        for game_item in gameItems:
            name = game_item['gameItem']['name']
            amount = int(game_item['amount'])

            # If the item name is not a column in the DataFrame, add it
            if name not in df.columns:
                df[name] = 0

            # Add the item amount to the appropriate cell in the DataFrame
            df.loc[address, name] = amount
        
        walletID += 1

    end_time = time.time()
    avg_execution_time = (end_time - start_time) / number_of_accounts
    print(f"\nAverage execution time per account ({number_of_accounts}x): {avg_execution_time:.2f} seconds") 

    # Replace NaN values with zeros
    df.fillna(0, inplace=True)

    # Rename columns to be more friendly
    df.rename(columns=data_name_to_display_name, inplace=True)

    # Convert DataFrame to Excel
    # Versions of Pandas >= 1.3.0:
    file_name = pn.data_path("pn_inventory.xlsx")
    xlWriter = pd.ExcelWriter(file_name,engine='xlsxwriter',engine_kwargs={'options': {'strings_to_numbers': True}})

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

    # Also export to a same directory the csv to be stored in github
    df.to_csv("pn_inventory.csv", index=False)

def main():
    file_path = pn.data_path('addresses.txt')  
    addresses = pn.read_addresses(file_path)
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
    excel_sheet(json.dumps(data, indent=4), addresses)
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Creating excel from data - execution time: {execution_time:.2f} seconds") 

if __name__ == "__main__":
    main()