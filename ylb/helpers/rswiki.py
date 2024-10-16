import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin
import openai

from ylb import utils
from ylb import config
from ylb import openai_client as client

@utils.function_info
def search_runescape_wiki(search_phrase: str) -> list:
    """
    Searches the Old School RuneScape Wiki for a given query and returns the body content of the top 3 relevant search results.
    The body content is processed using OpenAI's GPT-3.5 to clean and optimize the content.

    :param search_phrase: The search query to look up on the RuneScape Wiki.
    :type search_phrase: string
    :return: A list of cleaned body content of the top 3 relevant pages.
    :rtype: list
    """
    base_url = "https://oldschool.runescape.wiki/"
    search_url = base_url + "w/Special:Search?" + urlencode({
        'search': search_phrase,
        'title': 'Special:Search',
        'profile': 'advanced',
        'fulltext': '1',
    })

    def fetch_page(url):
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def get_body_content(html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        main_body = soup.find(id='bodyContent')
        return main_body.get_text(separator='\n') if main_body else ''

    def clean_content_with_gpt(content):
        # Perform a one-time chat completion
        completion = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
            {"role": "system", "content": (
                "You are an assistant that cleans and optimizes text content from RuneScape wiki articles. "
                "Remove redundant information. Reduce the content to a concise summary without sacrificing details. "
                "Return the cleaned content in Markdown format."
            )},
            {"role": "user", "content": content}
        ],
            temperature=config.OPENAI_MODEL_TEMPERATURE,
        )

        # Extract the assistant's response
        cleaned_content = completion.choices[0].message.content

        return cleaned_content.strip()

    # Fetch the initial search results page
    initial_html = fetch_page(search_url)

    # Parse the top 3 result links
    initial_soup = BeautifulSoup(initial_html, 'html.parser')
    search_results = initial_soup.find_all('li', class_='mw-search-result')

    top_3_links = []
    for result in search_results[:3]:
        link_tag = result.find('a', href=True)
        if link_tag:
            link = urljoin(base_url, link_tag['href'])
            top_3_links.append(link)

    all_contents = []

    for link in top_3_links:
        html_content = fetch_page(link)
        body_content_text = get_body_content(html_content)
        if not body_content_text:
            continue

        cleaned_content = clean_content_with_gpt(body_content_text)
        all_contents.append(cleaned_content)

    return all_contents

if __name__ == "__main__":
    search_results = search_runescape_wiki("dragon scimitar")
    for i, result in enumerate(search_results, start=1):
        with open(f"search_result_{i}.txt", "w", encoding="utf-8") as f:
            f.write(result)
