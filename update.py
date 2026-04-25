import os
import json
import datetime
import google.generativeai as genai

# Configurazione API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# --- RICERCA DINAMICA DEL MODELLO ---
modello_scelto = None
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            if 'flash' in m.name or 'pro' in m.name:
                modello_scelto = m.name.replace("models/", "")
                break
    if not modello_scelto:
        modello_scelto = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods][0]
except Exception:
    modello_scelto = "gemini-1.5-flash" # Fallback di sicurezza

print(f"Modello AI selezionato in automatico: {modello_scelto}")
model = genai.GenerativeModel(modello_scelto)
# ------------------------------------

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

def get_real_estate_data():
    # Simulazione di un annuncio. Quando userai uno scraper reale, 
    # dovrai assicurarti che estragga 'location' e 'image_url'.
    return [
        {
            "title": "Villetta bifamiliare con piccolo giardino",
            "price": "135.000 €",
            "location": "Vailate (CR)",
            "description": "Porzione di bifamiliare di 95mq. Soggiorno, cucina, due camere, balcone e giardinetto privato. Box auto singolo.",
            "link": "https://www.google.it", # Link di prova
            "image_url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&q=80" # Foto di prova
        }
    ]

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f).get("houses", [])
            except json.JSONDecodeError:
                return []
    return []

def analyze_house_with_ai(house, config):
    prompt = f"""
    Sei un consulente immobiliare. Valuta questo annuncio:
    Titolo: {house['title']}
    Prezzo: {house['price']}
    Posizione: {house['location']}
    Descrizione: {house['description']}

    I parametri del cliente sono:
    {json.dumps(config, ensure_ascii=False, indent=2)}

    Fornisci la risposta SOLO in JSON valido:
    {{
        "commento_ai": "Il tuo giudizio critico.",
        "valutazione_prezzo": 8,
        "valutazione_match": 9,
        "prezzo_numerico": 135000,
        "consiglio_ribasso": "Consiglio un'offerta a..."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        testo_pulito = response.text.replace("```json", "").replace("```", "").strip()
        analisi = json.loads(testo_pulito)
        analisi["data_inserimento"] = datetime.datetime.now().strftime("%Y-%m-%d")
        return {**house, **analisi}
    except Exception as e:
        print(f"Errore AI: {e}")
        return None

def main():
    config = load_config()
    existing_houses = load_existing_data()
    existing_links = {h["link"] for h in existing_houses}
    
    new_scraped_houses = get_real_estate_data()
    houses_to_analyze = [h for h in new_scraped_houses if h["link"] not in existing_links]
    
    print(f"Trovati {len(houses_to_analyze)} nuovi annunci.")
    
    analyzed_houses = []
    for house in houses_to_analyze:
        result = analyze_house_with_ai(house, config)
        if result:
            analyzed_houses.append(result)
            
    all_houses = existing_houses + analyzed_houses
    
    output = {
        "last_update": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "houses": all_houses
    }
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
