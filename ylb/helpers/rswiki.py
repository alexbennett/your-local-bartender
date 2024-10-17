import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin, quote_plus
import concurrent.futures

from ylb import utils
from ylb import config
from ylb import openai_client as client

# A list of all valid RuneScape item names to assist with fuzzy matching.
# This list would ideally be populated dynamically or cached, but for simplicity,
# we'll just assume this is predefined for now.
VALID_ITEM_NAMES = [
    "Rune_scimitar",
    "Dragon_dagger",
    "Abyssal_whip",
    "Bandos_chestplate",
    "Tetsu_helm",
    "Armadyl_godsword",
    "Saradomin_sword",
    "Zamorakian_spear",
    "Dragon_claws",
    "Dragon_scimitar",
    "Dragon_long_sword",
    "Dragon_mace",
    "Dragon_battleaxe",
    "Dragon_2h_sword",
    "Dragon_halberd",
    "Dragon_pickaxe",
    "Dragon_hatchet",
    "Dragon_crossbow",
    "Dragon_bolts",
    "Dragon_dart",
    "Dragon_javelin",
    "Dragon_throwing_axe",
    "Dragon_knife",
    "Dragon_harpoon",
    "Dragon_spear",
    "Dragon_warhammer",
    "Dragonfire_shield",
    "Dragonfire_ward",
    "Dragonfire_deflector",
    "Dragonfire_buckler",
    # Additional Weapons
    "Abyssal_dagger",
    "Abyssal_bludgeon",
    "Abyssal_orb",
    "Staff_of_the_dead",
    "Ancient_wand",
    "Twisted_bow",
    "Guthixian_sword",
    "Saradomin_blessed_sword",
    "Trident_of_the_seas",
    "Trident_of_the_swamp",
    "Trident_of_the_flood",
    "Salve_king_crystal",
    "Sanguinesti_staff",
    "Elder_maul",
    "Kodai_insignia",
    "Master_cannon",
    "Dragonfire_staff",
    "Blighted_ancient_staff",
    "Blighted_staff_of_the_dead",
    # Additional Armor
    "Karil_coif",
    "Veracs_helm",
    "Torags_platebody",
    "Guthans_warhammer",
    "Dharoks_greataxe",
    "Ahrims_staff",
    "Void_knight_helmet",
    "Void_knight_robe",
    "Void_knight_mage",
    "Void_knight_melee",
    "Void_ranger",
    "Rune_platebody",
    "Rune_platelegs",
    "Rune_full_helm",
    "Rune_kiteshield",
    "Bandos_tassets",
    "Ancestral_hat",
    "Ancestral_longbow",
    "Ancestral_robe_top",
    "Ancestral_robe_bottom",
    "Dragon_boots",
    "Pegasian_boots",
    "Primordial_boots",
    "Infinity_boots",
    "Barrows_gloves",
    "Fighter_harness",
    # Additional Miscellaneous Items
    "Spectral_hat",
    "Spectral_robe_top",
    "Spectral_robe_bottom",
    "Guthix_claws",
    "Saradomin_claws",
    "Zamorak_claws",
    "Armadyl_crossbow",
    "Bandos_torso",
    "Saradomin_claymore",
    "Zamorak_hastily_sword",
    "Ancient_crossbow",
    # Basic Items
    "Gold_bar",
    "Iron_bar",
    "Silver_bar",
    "Mithril_bar",
    "Adamantite_bar",
    "Runite_bar",
    "Bronze_bar",
    "Steel_bar",
    "Coal",
    "Copper_bar",
    "Tin_bar",
    "Mithril_pickaxe",
    "Adamantite_pickaxe",
    "Rune_pickaxe",
    "Bronze_axe",
    "Iron_axe",
    "Steel_axe",
    "Mithril_axe",
    "Adamant_axe",
    "Rune_axe",
    "Oak_log",
    "Willow_log",
    "Maple_log",
    "Yew_log",
    "Magic_log",
    "Mahogany_log",
    "Teak_log",
    "Nature_rune",
    "Fire_rune",
    "Air_rune",
    "Water_rune",
    "Earth_rune",
    "Mind_rune",
    "Body_rune",
    "Cosmic_rune",
    "Chaos_rune",
    "Law_rune",
    "Blood_rune",
    "Soul_rune",
    "Death_rune",
    "Lava_rune",
    "Astral_rune",
    # Food Items
    "Lobster",
    "Shark",
    "Monkfish",
    "Swordfish",
    "Tuna",
    "Sardine",
    "Trout",
    "Salmon",
    "Anchovies",
    "Bass",
    "Swamp_eel",
    "Rocktail",
    "Sea_turtle",
    "Manta_ray",
    "Shark_pie",
    "Anchovy_pizza",
    # Crafting Materials
    "Leather",
    "Hard_leather",
    "Snape_grass",
    "Silverleaf",
    "Redberry",
    "Cadantine",
    "Lantadyme",
    "Dwarf_weeds",
    "Toadflax",
    "White_lily",
    "Blue_d'hide",
    "Green_d'hide",
    "Red_d'hide",
    "Black_d'hide",
    "Rune_jewellery",
    # Potions and Herbs
    "Super_strength_potion",
    "Super_defence_potion",
    "Prayer_potion",
    "Ranging_potion",
    "Magic_potion",
    "Antipoison_potion",
    "Saradomin_brew",
    "Zamorak_brew",
    "Restore_potion",
    "Energy_potion",
    "Stamina_potion",
    # Add more items as needed
]


def search_item_value(base_url: str, fuzzy_item_name: str) -> str:
    # Function to match a fuzzy item name to the closest valid item name using GPT-3.5
    def match_fuzzy_item_name(fuzzy_name: str, valid_item_names: list) -> str:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Given the list of valid RuneScape item names: {', '.join(valid_item_names)}, "
                        f"find the best match for the item name requested by the user. Return only the exact name."
                    ),
                },
                {"role": "user", "content": fuzzy_name},
            ],
            temperature=0.5,
        )
        matched_name = completion.choices[0].message.content
        return matched_name


    # Function to retrieve the exact item name URL
    def construct_item_url(base_url: str, item_name: str) -> str:
        exact_item_name = quote_plus(item_name.replace(" ", "_"))
        return f"{base_url}{exact_item_name}"


    # Function to fetch the HTML content of the item exchange page
    def fetch_item_exchange_page(item_url: str) -> str:
        response = requests.get(item_url)
        response.raise_for_status()
        return response.text

    # Try to find the exchange value; adjust the CSS selectors based on the page structure
    def extract_item_value(html_content: str) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        price_tag = soup.find("span", class_="gemw-price")
        if price_tag:
            return price_tag.get_text(strip=True)
        return "Price not found"

    # Step 1: Match the fuzzy item name to the exact item name using GPT-3.5
    exact_item_name = match_fuzzy_item_name(fuzzy_item_name, VALID_ITEM_NAMES)

    # Step 2: Construct the URL for the item's exchange page
    item_url = construct_item_url(base_url, exact_item_name)
    
    # Step 3: Fetch the exchange page HTML content
    html_content = fetch_item_exchange_page(item_url)

    # Step 4: Extract the item value from the HTML content
    item_value = extract_item_value(html_content)

    return item_value


@utils.function_info
def search_rs3_item_value(fuzzy_item_name: str) -> str:
    """Searches the RuneScape 3 (NOT OLD SCHOOL) Exchange for the value of a given item.

    :param fuzzy_item_name: The fuzzy name of the item to search for.
    :type fuzzy_item_name: string
    :return: The value of the item on the RuneScape Exchange or "Price not found".
    :rtype: string
    """
    return search_item_value("https://runescape.wiki/w/Exchange:", fuzzy_item_name)


@utils.function_info
def search_osrs_item_value(fuzzy_item_name: str) -> str:
    """Searches the Old School RuneScape Exchange for the value of a given item.

    :param fuzzy_item_name: The fuzzy name of the item to search for.
    :type fuzzy_item_name: string
    :return: The value of the item on the RuneScape Exchange or "Price not found".
    :rtype: string
    """
    return search_item_value("https://oldschool.runescape.wiki/w/Exchange:", fuzzy_item_name)


def search_runescape_wiki(base_url: str, search_phrase: str, num_results: int = 1) -> list:
    search_url = (
        base_url
        + "w/Special:Search?"
        + urlencode(
            {
                "search": search_phrase,
                "title": "Special:Search",
                "profile": "advanced",
                "fulltext": "1",
                "ns4": "1",  # 'RuneScape' namespace
                "ns12": "1",  # 'Help' namespace
            }
        )
    )

    def fetch_page(url):
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def get_body_content(html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        main_body = soup.find(id="bodyContent")
        return main_body.get_text(separator="\n") if main_body else ""

    def clean_content_with_gpt(content):
        # Perform a one-time chat completion
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that cleans and optimizes text content from RuneScape wiki articles. "
                        "Remove redundant information. Reduce the content to a concise summary without sacrificing statistics."
                        "Return the cleaned content in Markdown format."
                    ),
                },
                {"role": "user", "content": content},
            ],
            temperature=1.0,
            n=1,
        )

        # Extract the assistant's response
        cleaned_content = completion.choices[0].message.content

        return cleaned_content.strip()

    # Fetch the initial search results page
    initial_html = fetch_page(search_url)

    # Parse the search results
    initial_soup = BeautifulSoup(initial_html, "html.parser")
    search_results = initial_soup.find_all("li", class_="mw-search-result")

    top_results = []
    for result in search_results[:num_results]:
        link_tag = result.find("a", href=True)
        if link_tag:
            link = urljoin(base_url, link_tag["href"])
            top_results.append(link)

    all_contents = []

    def process_link(link):
        html_content = fetch_page(link)
        body_content_text = get_body_content(html_content)
        if not body_content_text:
            return None

        cleaned_content = clean_content_with_gpt(body_content_text)
        return cleaned_content

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_link = {
            executor.submit(process_link, link): link for link in top_results
        }
        for future in concurrent.futures.as_completed(future_to_link):
            result = future.result()
            if result:
                all_contents.append(result)

    return all_contents


@utils.function_info
def search_rs3_wiki(search_phrase: str, num_results: int = 1) -> list:
    """
    Searches the RuneScape 3 (NOT OLD SCHOOL) Wiki for a given query and returns the summarized
    body content of the top `num_results` results.

    :param search_phrase: The search query to look up on the RuneScape Wiki.
    :type search_phrase: string
    :param num_results: The number of top search results to return. Defaults to 1.
    :type num_results: integer
    :return: A list of cleaned body content of the top search results.
    :rtype: list
    """
    return search_runescape_wiki("https://runescape.wiki/", search_phrase, num_results)

@utils.function_info
def search_osrs_wiki(search_phrase: str, num_results: int = 1) -> list:
    """
    Searches the Old School Runescape Wiki for a given query and returns the summarized
    body content of the top `num_results` results.

    :param search_phrase: The search query to look up on the RuneScape Wiki.
    :type search_phrase: string
    :param num_results: The number of top search results to return. Defaults to 1.
    :type num_results: integer
    :return: A list of cleaned body content of the top search results.
    :rtype: list
    """
    return search_runescape_wiki("https://oldschool.runescape.wiki/", search_phrase, num_results)
