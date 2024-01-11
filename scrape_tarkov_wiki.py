import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from openai import OpenAI
import html2text
import concurrent.futures

# Set your OpenAI API key
client = OpenAI()

# Define the maximum chunk size (in characters)
MAX_CHUNK_SIZE = 8192

def get_all_page_links(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        return [urljoin(url, link) for link in links if link.startswith('/')]
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return []

def split_into_chunks(text):
    # Split the text into chunks of a maximum size
    chunks = []
    for i in range(0, len(text), MAX_CHUNK_SIZE):
        chunk = text[i:i+MAX_CHUNK_SIZE]
        chunks.append(chunk)
    return chunks

def convert_html_to_markdown(html_content):
    # Use html2text library to convert HTML to Markdown
    markdown_text = html2text.html2text(html_content)
    return markdown_text

def format_chunk_with_gpt(chunk):
    # Send a chunk of Markdown content to GPT-3.5 for formatting
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "user", "content": f"Simplify the following content into Markdown format. Remove redundant content. Remove advertisements. \n\n{chunk}\n\n"},
        ]
    )
    formatted_chunk = response.choices[0].message.content
    return formatted_chunk

def format_markdown_with_gpt(markdown_chunks):
    formatted_chunks = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        formatted_chunks = list(executor.map(format_chunk_with_gpt, markdown_chunks))
    return formatted_chunks

def save_file(url, directory):
    try:
        response = requests.get(url)
        html_content = response.text
        markdown_content = convert_html_to_markdown(html_content)  # Convert HTML to Markdown
        markdown_chunks = split_into_chunks(markdown_content)  # Split Markdown into chunks
        formatted_chunks = format_markdown_with_gpt(markdown_chunks)  # Format the Markdown chunks using GPT-3.5
        file_name = os.path.join(directory, url.split('/')[-1] + '.md')

        with open(file_name, 'w', encoding='utf-8') as file:
            # Combine the formatted chunks and write to the file
            file.write('\n'.join(formatted_chunks))
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while saving {url}: {e}")

def main():
    sitemap_url = 'https://escapefromtarkov.fandom.com/wiki/Local_Sitemap'
    output_dir = 'downloaded_pages'
    os.makedirs(output_dir, exist_ok=True)

    all_links = get_all_page_links(sitemap_url)
    for link in all_links:
        save_file(link, output_dir)
        print(f'Saved {link}')

if __name__ == "__main__":
    main()
