from flask import Flask, render_template
import pandas as pd
import pn_helper as pn

app = Flask(__name__)

# Load data from the Excel file and extract the 'imageUrl' and 'tokenId' columns
data = pd.read_excel(pn.data_path("pn_pirates.xlsx"))

# Transform the image URLs to the IPFS gateway format
def transform_url(url):
    if url.startswith('ipfs://'):
        return 'https://ipfs.io/ipfs/' + url[7:]  # Remove 'ipfs://' and add 'https://ipfs.io'
    else:
        return url  # If not 'ipfs://', leave it as is

# Apply the URL transformation to the 'imageUrl' column and create a new 'imageUrl' column
data['imageUrl'] = data['imageUrl'].apply(transform_url)

# Get the image data as a list of dictionaries
image_data = data.to_dict(orient='records')

@app.route('/')
def index():
    html_content = render_template('index.html', image_data=image_data)

    # Save the HTML content to a file named 'pirate.html'
    with open(pn.data_path('pirate.html'), 'w', encoding='utf-8') as file:
        file.write(html_content)

    return html_content

if __name__ == '__main__':
    app.run()
