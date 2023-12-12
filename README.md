# pn

## Prerequisites:
1. Install python3
`npm install -g python3`
2. Install pip
`python3 -m ensurepip`
3. Install requirements
`python3 -m pip install -r requirements.txt --user`

## Usage:
1. Place the python script and address file in same directory lets say "pn"
2. Open terminal and cd till you are in "pn" directory
3. Create an addresses.txt file in the directory with 1 wallet address per line
4. Run a script using following command

python3 <scriptname>

### Exampels

python3 pgld_items.py

"Lists for each wallet the PGLD + all game items (and totals) from the 'Pirate Nation - Items' items collection. This is useful for seeing imbalances, total number of resources, and  more. Perfect for planning your multi-wallet strategy"

python3 pirate.py

"Lists for each wallet the Pirates and all their respective metadata so you can easily sort, and strategize. It also shows you which pirates are upgradeable to the next level, how much xp they need for the next level, and even the claim data for their next chest (in EST)"

python3 ships.py

"Lists each wallet and the ship counts of each type in those wallets. Perfect for managing your fleet, or studying your competition"



