import json
import os
import requests
import string
import time
from bs4 import BeautifulSoup

base = "http://cah.frustratednerd.com/"  # Url to scrape from. Do not change
foldername = "defaultpacks"  # Folder where default packs are stored
packs = []
start = time.time()


def fix(name):
    if not name.translate(str.maketrans('', '', string.punctuation)).strip():
        print("Found a blank card")
        return "", True
    while "__" in name:
        name = name.replace("__", "_")
    return name, False


try:
    with requests.get(base) as resp:
        soup = BeautifulSoup(resp.text, "html.parser")
        menu = soup.findAll(id="text-2")[0]
        links = menu.findAll("a")
        for link in links:
            packs.append([link.attrs.get('href'), link.text])
except:
    packs = []

for number, (link, name) in enumerate(packs):
    filename = name.lower().replace(" ", "_") + ".json"
    filepath = os.path.join(foldername, filename)

    if not os.path.exists(filepath):
        try:
            with requests.get(link) as resp:
                soup = BeautifulSoup(resp.text, "html.parser")
                cardlist = soup.findAll("div", {"class": "entry-content"})
                if len(cardlist) > 0:
                    cardlist = cardlist[0]
                    titles = cardlist.findAll("h3")
                    if len(titles) == 0:
                        titles = cardlist.findAll("h2")
                    if len(titles) == 0:
                        print(f"Skipping {name} as could not find any suitable titles")
                        continue
                    types = cardlist.findAll("ul")

                    empty_cards = 0
                    white = []
                    black = []

                    for index, title in enumerate(titles):
                        if index < len(types):
                            if "white" in title.text.lower():
                                for e in types[index].findAll("li"):
                                    text, empty = fix(e.text)
                                    if empty:
                                        empty_cards += 1
                                    else:
                                        white.append(text)
                            elif "black" in title.text.lower():
                                for e in types[index].findAll("li"):
                                    text, empty = fix(e.text)
                                    if empty:
                                        empty_cards += 1
                                    else:
                                        black.append(text)
                            else:
                                print(f"Unexpected title: {title.text}")
                                os._exit()
                        else:
                            print("For some reason they have just a title and no card list :/")
                    data = {
                        "name": name,
                        "white": white,
                        "black": black,
                        "empty": empty_cards,
                        "id": name.lower().replace(" ", "_"),
                    }
                    with open(filepath, "w") as f:
                        json.dump(data, f)
                    print(f"[{number+1}/{len(packs)}] Dumped data to {filepath}. black={len(black)} white={len(white)} blank={empty_cards}")
        except BaseException as e:
            print(f"{e}")
    else:
        print(f"[{number+1}/{len(packs)}] Ignoring {name} as file already exists")

print("Checking files")
total_white, total_black, total_blank = 0, 0, 0
_list = os.listdir(foldername)
names = []
for filename in _list:
    path = os.path.join(foldername, filename)
    with open(path, "r") as f:
        try:
            data = json.load(f)
            names.append(data['name'])
            total_white += len(data['white'])
            total_black += len(data['black'])
            total_blank += data['empty']
            if len(data['white']) + len(data['black']) + data['empty'] == 0:
                print(f"{path} is an empty deck!")
        except Exception as e:
            print(f"Gotten exception with {path}! {e}")

print(f"Total Decks: {len(_list)} ({', '.join(names)})")
print(f"Total White Cards: {total_white}")
print(f"Total Black Cards: {total_black}")
print(f"Total Blank Cards: {total_blank}\n\n")
print(f"Completed in {time.time()-start} s")
