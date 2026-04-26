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
    modello_scelto = "gemini-1.5-flash" # Fallback

print(f"Modello AI selezionato in automatico: {modello_scelto}")
model = genai.GenerativeModel(modello_scelto)
# ------------------------------------

DATA_FILE = "data.json"
CONFIG_FILE = "config.json"

def get_real_estate_data():
    # Simulazione di due annunci: uno CON FOTO REALE, uno SENZA (che userà il render AI)
    return [
        {
            "title": "Villetta bifamiliare a Trescore",
            "price": "140.000 €",
            "location": "Trescore Cremasco (CR)",
            "description": "Recente porzione di bifamiliare su due livelli di 98mq. Soggiorno, cucina abitabile, due camere, balcone vivibile e giardinetto privato recintato. Box auto singolo incluso.",
            # URL DI UNA FOTO REALE DI REPERTORIO
            "image_url": "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=600&q=80" 
        },
        {
            "title": "Porzione di rustico da ristrutturare",
            "price": "85.000 €",
            "location": "Capralba (vicino Crema)",
            "description": "In centro storico, porzione di rustico indipendente di 110mq su tre livelli, con travi a vista originali, caminetto in pietra. Include un cortile privato di 30mq. Da ristrutturare completamente.",
            # IMMAGINE VUOTA PER FORZARE IL RENDER AI
            "image_url": "" 
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

# --- NUOVA FUNZIONE PER SIMULARE UN RENDER AI ---
def simula_generazione_immagine_ai(house):
    # Costruiamo un prompt fotografico iper-dettagliato basato sulla descrizione
    # Nota: In un'app reale, questo prompt verrebbe inviato a DALL-E 3 o Stability AI
    prompt_fotografico = f"""photorealistic wide photo of a {house['description'].substring(0, 100)} located in {house['location']}, captured as a high-quality, professional real estate listing photograph in Cremona, Italy, with detailed textures and natural lighting"""
    
    # Per questa simulazione, dato che non possiamo chiamare API esterne,
    # restituiamo un'immagine ipotetica generata da un prompt perfetto.
    # In una versione live, qui verrebbe inserito l'URL restituito dall'API di generazione immagini.
    return "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&q=80" # Foto di prova (che contrassegneremo come render)

def analyze_house_with_ai(house, config):
    prompt = f"""
    Sei un consulente immobiliare. Valuta questo annuncio:
    Titolo: {house['title']} | Prezzo: {house['price']} | Posizione: {house['location']}
    Descrizione: {house['description']}

    I parametri del cliente sono:
    {json.dumps(config, ensure_ascii=False, indent=2)}

    Fornisci la risposta SOLO in JSON valido:
    {{
        "commento_ai": "Il tuo giudizio critico.",
        "valutazione_prezzo": 8,
        "valutazione_match": 9,
        "prezzo_numerico": 140000,
        "consiglio_ribasso": "Consiglio un'offerta a..."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        testo_pulito = response.text.replace("```json", "").replace("```", "").strip()
        analisi = json.loads(testo_pulito)
        analisi["data_inserimento"] = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # --- LOGICA DI RIPIEGO RENDER AI ---
        # Se non c'è una foto reale, generiamo il render AI
        if not house.get("image_url"):
            print(f"Nessuna foto trovata per {house['title']}, generazione render AI...")
            house["image_url"] = simula_generazione_immagine_ai(house)
            house["is_ai_render"] = True # Etichetta speciale
        else:
            house["is_ai_render"] = False # È una foto reale
            
        return {**house, **analisi}
    except Exception as e:
        print(f"Errore AI: {e}")
        return None

def main():
    config = load_config()
    existing_houses = load_existing_data()
    existing_titles = {h["title"] for h in existing_houses} # Usiamo il titolo per i duplicati in simulazione
    
    new_scraped_houses = get_real_estate_data()
    houses_to_analyze = [h for h in new_scraped_houses if h["title"] not in existing_titles]
    
    print(f"Trovati {len(houses_to_analyze)} nuovi annunci da analizzare.")
    
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
