from ylb.helpers.rswiki import search_runescape_wiki

search_results = search_runescape_wiki("dragon scimitar")
for i, result in enumerate(search_results, start=1):
    with open(f"search_result_{i}.txt", "w", encoding="utf-8") as f:
        f.write(result)
