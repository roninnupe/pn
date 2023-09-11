import time
import pandas as pd
from datetime import datetime, timedelta
import pytz
import pn_helper as pn

start_time = time.time() 
print("Starting Script...")

#-------- FUNCTIONS -----------------------------------------

# expertise mapping of number to actual readable name
expertise_id_mapping = {
    "1": "Attack",
    "2": "Evasion",
    "3": "Speed",
    "4": "Accuracy",
    "5": "Health"
}

# FUNCTION: Maps expertise IDs to their respective names
def map_expertise(nft):
    for trait in nft['traits']:
        if trait['metadata']['name'] == 'expertise_id':
            trait['metadata']['name'] = 'Expertise'
            trait['value'] = expertise_id_mapping[trait['value']]

# Read data from a CSV file and create a dictionary mapping token IDs to rarity ranks.
df = pd.read_csv('../pn data/rarity_scores_final.csv')

df.tokenId = df.tokenId.astype(str)  # Ensure all token IDs are strings.
tokenId_rarity_dict = dict(zip(df.tokenId, df.RarityRank))

# FUNCTION: Add Rarity Rank to the traits
def add_rarity_rank(nft):
    tokenId_str = str(nft['tokenId'])  # Convert tokenId to a string before accessing the dictionary.
    rarity_rank = tokenId_rarity_dict.get(tokenId_str, 'No data')
    nft['traits'].append({'metadata': {'name': 'Rarity Rank'}, 'value': rarity_rank})

# FUNCTION: calculate the next chest claim date and add related traits
def add_next_claim_date(nft):
    max_milestone_index = max([milestone['milestoneIndex'] for milestone in nft['claimedMilestones']], default=-1)
    next_milestone_index = max_milestone_index + 1
    if next_milestone_index == 0:
        next_claim_date = int(nft['lastTransfer']) + 7 * 24 * 60 * 60
    elif next_milestone_index in [1, 2]:
        next_claim_date = int(nft['lastTransfer']) + next_milestone_index * 30 * 24 * 60 * 60
    elif next_milestone_index in [3, 4, 5]:
        next_claim_date = int(nft['lastTransfer']) + 3 * 30 * 24 * 60 * 60
    elif next_milestone_index == 6:
        next_claim_date = int(nft['lastTransfer']) + 135 * 24 * 60 * 60
    else:
        next_claim_date = "All claimed"
    if next_claim_date != "All claimed":
        next_claim_date = datetime.fromtimestamp(next_claim_date, pytz.timezone('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S')
    nft['traits'].append({'metadata': {'name': 'Next Claim Date'}, 'value': next_claim_date})
    nft['traits'].append({'metadata': {'name': 'ClaimedChests'}, 'value': max_milestone_index+1})    

# Read the level_chart into a data frame once for use 
df_level_chart = pd.read_csv("../pn data/LevelChart.csv")

# FUNCTION: Calculates the level based on XP and returns the amount of xp to the next level as well
def get_potential_level(xp_value):
    try:
        level = None
        xp_to_next_level = None

        # Iterate through the level_chart and find the level
        for index, row in df_level_chart.iterrows():
            if xp_value >= row['XP Needed']:
                level = row['Level']
            else:
                xp_to_next_level = row['XP Needed'] - xp_value
                break

        return level, xp_to_next_level

    except Exception as e:
        return f"Error: {str(e)}"

# Calculate the upgradable level and add related traits
def calculate_upgradable_level(nft):
    xp = next((int(trait['value']) for trait in nft['traits'] if trait['metadata']['name'] == 'xp'), 0)
    current_level = next((int(trait['value']) for trait in nft['traits'] if trait['metadata']['name'] == 'level'), 0)
    potential_level, xp_needed = get_potential_level(xp)
    
    if potential_level > current_level :
        nft['traits'].append({'metadata': {'name': 'potential'}, 'value': potential_level}) 
    else:
        nft['traits'].append({'metadata': {'name': 'to next'}, 'value': xp_needed})

#---------------------------------------------------------

# Step 1: Read addresses from a text file and create a dictionary mapping addresses to IDs.
file_path = pn.data_path('addresses.txt')  
addresses = pn.read_addresses(file_path)
formatted_output = pn.format_addresses_for_query(addresses)
address_id_dict = {address: i+1 for i, address in enumerate(addresses)}

# GraphQL Query to get all the pirate data based off of all the addresses in the text file
query = f"""
{{
    accounts(where: {{address_in: {formatted_output}}} ) {{
        address
        nfts(first: 1000, where: {{nftType: "pirate"}}) {{
            tokenId
            claimedMilestones {{
                milestoneIndex
            }}
            lastTransfer
            traits {{ 
                value
                metadata {{
                    name
                }}
            }}
        }}
    }}
}}
"""

# Step 2: Fetch the Data using the query from the PN Graph API 
data = pn.get_data(query)

# Prepare data to export 
data_to_export = []

# Step 3: if data returned iterate over each account, and annote the proper data to be exported
if 'data' in data and 'accounts' in data['data']:
    accounts = data['data']['accounts']

    # Iterate over each account
    for account in accounts:
        address = account['address']
        nfts = account['nfts']

        # Check if 'nfts' is not empty
        if nfts:
            for nft in nfts:
                nft['address'] = address

                # map the named expertise on to the Pirate NFT data
                map_expertise(nft)

                # add the rarity rank on to the Pirate NFT data
                add_rarity_rank(nft)

                # add data around chest claims to the Pirate NFT data
                add_next_claim_date(nft)

                # add data about what it takes to get to the next level, and if the NFT can already be leveled up to the next level
                calculate_upgradable_level(nft)

                # create a row with data, and then iterate over additional traits to finalize the final data row
                row = {'address': nft['address'], 'tokenId': nft['tokenId'], 'lastTransfer': nft['lastTransfer']}
                for trait in nft['traits']:
                    row[trait['metadata']['name']] = trait['value']

                # append the row to the data
                data_to_export.append(row)
        else:
            print(f"No NFTs found for account: {address}")
else:
    print("Invalid or empty response.")

# Step 4: Add # identifier to each row
for row in data_to_export:
    row["#"] = address_id_dict[row["address"]]

# Step 5: Sort data_to_export by this number since it comes out of the graph out of order
data_to_export_sorted = sorted(data_to_export, key=lambda x: x['#'])


# Step 6: Define the desired column order, note some have been commented out because I don't want to display it
column_order = [
    "#",
    "address",
    "tokenId",
    "Character Type",
    "level",
    "potential",
    "xp",
    "to next",    
    "Elemental Affinity",
    "Expertise",
    "Background",
    "Headwear",
    #"Rarity Rank",
    "Dice Roll 1",
    "Dice Roll 2",
    #"lastTransfer",
    "ClaimedChests",
    "Next Claim Date",
    #"affinity_id",
    "Skin",
    "Star Sign",
    "Eyes",
    "Earring",
    "Coat",
    "Eye Covering",
]

# Step 7: Prepare and Format the Excel File

# Load the Excel file
file_name = '../pn data/pn_pirates.xlsx'
xlWriter = pd.ExcelWriter(file_name,
                        engine='xlsxwriter',
                        engine_kwargs={'options': {'strings_to_numbers': True}})

# Create the DataFrame and reorder the columns
df_to_export = pd.DataFrame(data_to_export_sorted)
df_to_export = df_to_export.reindex(columns=column_order)
df_to_export = df_to_export.rename(columns={'xp': ' xp ', 'Elemental Affinity': 'Affinity', 'Dice Roll 1': 'D1 ', 'Dice Roll 2': 'D2 '})

# Cast certain columns to numeric (assuming it contains valid numeric values)
df_to_export['level'] = pd.to_numeric(df_to_export['level'], errors='coerce')
df_to_export['tokenId'] = pd.to_numeric(df_to_export['tokenId'], errors='coerce')
df_to_export['#'] = pd.to_numeric(df_to_export['#'], errors='coerce')

# Sort the values into wallet order by #, and tokenId order within those wallets
df_to_export.sort_values(by='tokenId', ascending=True, inplace=True)
df_to_export.sort_values(by='#', ascending=True, inplace=True)

# Calculate the average of the "level" column
average_level = df_to_export['level'].mean()
average_level_rounded = round(average_level, 2)
num_rows_used = df_to_export['level'].count()

print("------------------------------------------------------")
print(f"The average level of {num_rows_used} pirates analyzed is {average_level_rounded:.2f}")
print("------------------------------------------------------")

# Export to Excel
df_to_export.to_excel(xlWriter, index=False)

# Get the xlsxwriter workbook and worksheet objects
workbook = xlWriter.book
worksheet = xlWriter.sheets['Sheet1']

# Freeze the first row (row 1, column 0)
worksheet.freeze_panes(1, 0)
worksheet.add_table(0, 0, df_to_export.shape[0], df_to_export.shape[1] - 1, {'columns': [{'header': col} for col in df_to_export.columns]})

# Autofit column width to fit the content
for i, col in enumerate(df_to_export.columns):
    column_len = max(df_to_export[col].astype(str).str.len().max(), len(col) + 2)  # Get the length of the longest content in the column or column name
    worksheet.set_column(i, i, column_len)  # Set the column width to fit

#worksheet.write(df_to_export.shape[0] + 1, 2, average_level) 

xlWriter._save()

end_time = time.time()
execution_time = end_time - start_time
print(f"Created {file_name} in {execution_time:.2f} seconds")    