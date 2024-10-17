from ylb.helpers.rswiki import search_runescape_wiki, search_runescape_item_value

# search_results = search_runescape_wiki("dragon scimitar")
# for i, result in enumerate(search_results, start=1):
#     print(f"---- Result {i} ------------------------------------")
#     print(f"{result}")

search_results = search_runescape_item_value("dragon scimitar")

print(search_results)