import requests, json, time, sys, os
from urllib.parse import urlparse

MAL_CACHE_FILE = "mal_links.json"

class metadata:
    def __init__(self):
        self.status = ""
        self.summary = ""
        self.publisher = ""
        self.genres = "[]"
        self.tags = "[]"
        self.cover_url = ""
        self.mal_url = ""
        self.isvalid = False

def load_mal_cache():
    if os.path.exists(MAL_CACHE_FILE):
        with open(MAL_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_mal_cache(cache):
    with open(MAL_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def promptMangaSelection(results):
    print("\nSelect a manga:")
    for i, manga in enumerate(results[:3]):
        print(f"[{i+1}] {manga['title']} ({manga.get('status', 'Unknown')}) - {manga.get('url')}")
    print("[4] Enter your own MAL link")
    print("[0] Skip this entry")

    while True:
        try:
            choice = int(input("Enter number (0-4): ").strip())
            if 0 <= choice <= 4:
                return choice
        except:
            pass
        print("Invalid input. Please enter 0, 1, 2, 3, or 4.")

def getMangaMetadataFromMAL(query, cache):
    if query in cache:
        try:
            mal_id = int(urlparse(cache[query]).path.strip("/").split("/")[1])
            print(f"🔁 Using cached MAL link for {query}: {cache[query]}")
            return getMetadataFromMALId(mal_id), True  # Added `from_cache = True`
        except:
            print("⚠️ Invalid cached MAL link. Proceeding with fresh search.")

    print(f"Searching MAL for: {query}")
    url = f"https://api.jikan.moe/v4/manga?q={query}&limit=5&type=manga"
    resp = requests.get(url)

    if resp.status_code != 200:
        print(f"Jikan request failed with status {resp.status_code}")
        return None, False

    data = resp.json()
    if "data" not in data or len(data["data"]) == 0:
        print("No results found on MAL.")
        return None, False

    choice = promptMangaSelection(data["data"])
    if choice == 0:
        return None, False
    elif choice == 4:
        user_url = input("Paste your MAL manga URL: ").strip()
        try:
            mal_id = int(urlparse(user_url).path.strip("/").split("/")[1])
            cache[query] = user_url
            save_mal_cache(cache)
            return getMetadataFromMALId(mal_id), True
        except:
            print("Invalid URL or ID. Skipping.")
            return None, False
    else:
        selected = data["data"][choice - 1]
        cache[query] = selected["url"]
        save_mal_cache(cache)
        return parseMangaToMetadata(selected), False


def getMetadataFromMALId(mal_id):
    url = f"https://api.jikan.moe/v4/manga/{mal_id}"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Failed to fetch by ID. Status: {resp.status_code}")
        return None
    data = resp.json()
    if "data" not in data:
        return None
    return parseMangaToMetadata(data["data"])

def parseMangaToMetadata(manga):
    md = metadata()
    score = manga.get("score")
    summary = (manga.get("synopsis") or "").replace('\n', ' ').replace('"', '\\"')
    if score:
        summary = f"⭐ {score}\n{summary}"
    md.summary = summary

    md.publisher = manga.get("serializations", [{}])[0].get("name", "")
    md.cover_url = manga.get("images", {}).get("jpg", {}).get("large_image_url", "")
    md.mal_url = manga.get("url", "")

    status = manga.get("status", "").lower()
    if "publishing" in status:
        md.status = "\"ONGOING\""
    elif "finished" in status:
        md.status = "\"ENDED\""
    else:
        md.status = "\"ABANDONED\""

    genres = [g["name"] for g in manga.get("genres", [])]
    md.genres = json.dumps(genres)

    themes = [t["name"] for t in manga.get("themes", [])]
    md.tags = json.dumps(themes)

    md.isvalid = True
    return md

# Config load
try:
    ENV_URL = os.environ['KOMGAURL']
    ENV_EMAIL = os.environ['KOMGAEMAIL']
    ENV_PASS = os.environ['KOMGAPASSWORD']
    ENV_PROGRESS = os.environ['KEEPPROGRESS'].lower() == "true"
    ENV_MANGAS = os.environ.get('MANGAS', "")
    mangas = [m.strip() for m in ENV_MANGAS.split(",")] if ENV_MANGAS else []
    komgaurl, komgaemail, komgapassword, keepProgress = ENV_URL, ENV_EMAIL, ENV_PASS, ENV_PROGRESS
except:
    try:
        from config import komgaurl, komgaemail, komgapassword, keepProgress, mangas
    except ImportError:
        print("❌ Failed to find config.py.")
        sys.exit(1)

print(f"🔐 Using user {komgaemail}")
x = requests.get(f"{komgaurl}/api/v1/series?size=50000", auth=(komgaemail, komgapassword))
try:
    series_data = x.json()
    expected = series_data['numberOfElements']
except:
    print("❌ Failed to get series list.")
    sys.exit(1)

print(f"📚 Series to update: {expected}")

progressfilename = "mangas.progress"
progresslist = []
if keepProgress:
    try:
        with open(progressfilename) as f:
            progresslist = [line.strip() for line in f.readlines()]
    except:
        print("⚠️ No progress file found. Starting fresh.")

mal_cache = load_mal_cache()

class FailedTry:
    def __init__(self, id, name):
        self.id = id
        self.name = name

failed = []

def addMangaProgress(seriesID):
    if keepProgress:
        with open(progressfilename, "a") as f:
            f.write(f"{seriesID}\n")

def updateCover(seriesID, md):
    if not md.cover_url:
        return
    try:
        cover_resp = requests.get(md.cover_url)
        if cover_resp.status_code != 200:
            print("⚠️ Failed to download cover.")
            return
        files = {'file': ('cover.jpg', cover_resp.content, 'image/jpeg')}
        response = requests.post(
            f"{komgaurl}/api/v1/series/{seriesID}/thumbnails",
            auth=(komgaemail, komgapassword),
            files=files
        )
        if response.status_code == 200:
            print("🖼️ Cover updated.")
        else:
            print(f"⚠️ Cover update failed. Status: {response.status_code}")
    except Exception as e:
        print("⚠️ Cover upload error:", e)

# Main update loop
for idx, series in enumerate(series_data['content']):
    print(f"\n[{idx+1}/{expected}] {series['name']}")
    seriesID = series['id']
    if mangas and series['name'] not in mangas:
        continue

    md, from_cache = getMangaMetadataFromMAL(series['name'], mal_cache)
    if not md or not md.isvalid:
        print("❌ No valid metadata.")
        failed.append(FailedTry(seriesID, series['name']))
        continue

    print("📄 Metadata preview:")
    print(f"Status: {md.status}")
    print(f"Summary: {md.summary[:200]}...")
    print(f"Publisher: {md.publisher}")
    print(f"Genres: {md.genres}")
    print(f"Tags: {md.tags}")
    print(f"🔗 MAL Link: {md.mal_url}")

    if not from_cache:
        confirm = input("Use this metadata? (y/n): ").strip().lower()
        if confirm != 'y':
            print("⏭️ Skipped.")
            continue
    else:
        print("✅ Using cached MAL metadata without prompt.")

    payload = {
        "status": json.loads(md.status),
        "statusLock": True,
        "summary": md.summary,
        "summaryLock": True,
        "publisher": md.publisher,
        "publisherLock": True,
        "genres": json.loads(md.genres),
        "genresLock": True,
        "tags": json.loads(md.tags),
        "tagsLock": True
    }

    response = requests.patch(
        f"{komgaurl}/api/v1/series/{seriesID}/metadata",
        headers={'Content-Type': 'application/json'},
        auth=(komgaemail, komgapassword),
        data=json.dumps(payload)
    )

    if response.status_code == 204:
        print("✅ Metadata updated.")
        addMangaProgress(seriesID)
        updateCover(seriesID, md)
    else:
        print("❌ Metadata update failed.")
        failed.append(FailedTry(seriesID, series['name']))
    time.sleep(1)

# Retry loop
print("\n🔁 Retrying failed updates...")
for f in failed:
    md = getMangaMetadataFromMAL(f.name, mal_cache)
    if not md or not md.isvalid:
        print(f"❌ Still failed for {f.name}")
        continue

    payload = {
        "status": json.loads(md.status),
        "statusLock": True,
        "summary": md.summary,
        "summaryLock": True,
        "publisher": md.publisher,
        "publisherLock": True,
        "genres": json.loads(md.genres),
        "genresLock": True,
        "tags": json.loads(md.tags),
        "tagsLock": True
    }

    response = requests.patch(
        f"{komgaurl}/api/v1/series/{f.id}/metadata",
        headers={'Content-Type': 'application/json'},
        auth=(komgaemail, komgapassword),
        data=json.dumps(payload)
    )

    if response.status_code == 204:
        print(f"✅ Retry successful: {f.name}")
        addMangaProgress(f.id)
        updateCover(f.id, md)
    else:
        print(f"❌ Retry failed for {f.name}")
    time.sleep(1)
