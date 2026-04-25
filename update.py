import os
import json
import datetime
import google.generativeai as genai

# Configurazione API di Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# --- RICERCA DINAMICA DEL MODELLO (La tua soluzione) ---
modello_scelto = None
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        if 'flash' in m.name or 'pro' in m.name:
            # Estrae il nome pulito
            modello_scelto = m.name.replace("models/", "")
            break

if not modello_scelto:
    modello_scelto = [m.name.replace("models/", "") for m in genai.list_models() if 'generateContent' in m.supported_generation_methods][0]

print(f"Modello AI selezionato in automatico: {modello_scelto}")
model = genai.GenerativeModel(modello_scelto)
# -------------------------------------------------------

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

def get_real_estate_data():
    # Qui in futuro andrà inserito lo script di scraping o la lettura di un feed RSS.
    # Per il primo avvio, usiamo un annuncio di test per verificare che tutto funzioni.
    return [
        {
            "title": "Villetta bifamiliare da ristrutturare parzialmente",
            "price": "130.000 €",
            "location": "Crema, adiacenze quartiere Sabbioni",
            "description": "Villetta di 95mq su due livelli. Soggiorno, cucina, due bagni, due camere e balcone. Piccolo giardino privato sul fronte e box auto singolo.",
            "link": "https://esempio.it/casa-test-definitiva"
        }
    ]

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data.get("houses", [])
            except json.JSONDecodeError:
                return []
    return []

def analyze_house_with_ai(house, config):
    prompt = f"""
    Sei un consulente immobiliare esperto e analitico. Valuta questo annuncio immobiliare:
    Titolo: {house['title']}
    Prezzo: {house['price']}
    Posizione: {house['location']}
    Descrizione: {house['description']}

    I parametri, il budget e le esigenze del tuo cliente sono rigorosamente questi:
    {json.dumps(config, ensure_ascii=False, indent=2)}

    Valuta l'immobile tenendo conto della comodità logistica tra il lavoro e la zona della famiglia.
    Fornisci la tua risposta ESATTAMENTE in questo formato JSON (senza markdown o altro testo):
    {{
        "commento_ai": "Il tuo giudizio critico e oggettivo sulla casa.",
        "valutazione_prezzo": 8,
        "valutazione_match": 9,
        "prezzo_numerico": 130000,
        "consiglio_ribasso": "Consiglio un'offerta a X euro (-Y%)...",
        "sicurezza": 8,
        "tempo_percorrenza": "X min in auto per Trescore"
    }}
    """
    
    response = model.generate_content(prompt)
    
    try:
        testo_pulito = response.text.replace("```json", "").replace("```", "").strip()
        analisi = json.loads(testo_pulito)
        analisi["data_inserimento"] = datetime.datetime.now().strftime("%Y-%m-%d")
        return {**house, **analisi}
    except Exception as e:
        print(f"Errore di parsing AI: {e}")
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
        print(f"Analizzando: {house['title']}")
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
